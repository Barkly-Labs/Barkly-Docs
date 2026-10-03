"""Static Python project dependency manifest reader for Barkly Docs."""
from __future__ import annotations

import ast
import configparser
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

from model.project import DependencyNode, FileNode, Project
from .base import LanguageReader, ReaderResult

_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_REQ_SPLIT_RE = re.compile(r"\s*(===|==|~=|!=|<=|>=|<|>)\s*")


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _line_of(text: str, needle: str) -> int | None:
    for i, line in enumerate(text.splitlines(), 1):
        if needle and needle in line:
            return i
    return None


def _requirement_parts(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    editable = False
    if raw.startswith(("-e ", "--editable ")):
        editable = True
        raw = raw.split(None, 1)[1].strip()
    marker = None
    if ";" in raw:
        raw, marker = (part.strip() for part in raw.split(";", 1))
    source_type = "registry"
    original = raw
    if " @ " in raw:
        left, location = raw.split(" @ ", 1)
        name = left.strip()
        version = None
        source_type = "git" if location.startswith("git+") else ("url" if "://" in location else "path")
        return {"name": name, "version": version, "marker": marker, "source_type": source_type, "source_value": location, "editable": editable, "declaration": original}
    if raw.startswith(("git+", "http://", "https://", "file:", "./", "../", "/")):
        egg = re.search(r"[#&]egg=([^&]+)", raw)
        name = egg.group(1) if egg else raw.rsplit("/", 1)[-1].removesuffix(".git")
        source_type = "git" if raw.startswith("git+") else ("url" if "://" in raw else "path")
        return {"name": name, "version": None, "marker": marker, "source_type": source_type, "source_value": raw, "editable": editable, "declaration": original}
    match = _NAME_RE.match(raw)
    name = match.group(1) if match else raw
    tail = raw[match.end():].strip() if match else ""
    version = tail or None
    return {"name": name, "version": version, "marker": marker, "source_type": source_type, "source_value": None, "editable": editable, "declaration": original}


class PythonDependencyReader(LanguageReader):
    language = "Python dependencies"
    extensions = ()
    version = "0.1.0"

    _NAMES = {"pyproject.toml", "requirements.txt", "setup.cfg", "setup.py", "pipfile", "pipfile.lock", "poetry.lock", "environment.yml", "environment.yaml"}

    def can_read(self, path: Path) -> bool:
        name = path.name.casefold()
        return name in self._NAMES or (name.startswith("requirements") and path.suffix.casefold() == ".txt") or (name.startswith("constraints") and path.suffix.casefold() == ".txt")

    def read(self, path: Path, project: Project) -> ReaderResult:
        path = Path(path)
        warnings: list[str] = []
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            return ReaderResult(False, project, warnings, [f"Could not read dependency manifest {path}: {exc}"], {"path": str(path)})
        project.add_file(FileNode(path=str(path), language="Python dependency manifest", size=len(text.encode("utf-8")), metadata={"kind": "dependency_manifest"}))
        try:
            name = path.name.casefold()
            if name == "pyproject.toml": self._pyproject(path, text, project)
            elif name in {"pipfile", "poetry.lock"}: self._toml_manager(path, text, project, name)
            elif name == "pipfile.lock": self._pipfile_lock(path, text, project)
            elif name == "setup.cfg": self._setup_cfg(path, text, project)
            elif name == "setup.py": self._setup_py(path, text, project, warnings)
            elif name in {"environment.yml", "environment.yaml"}: self._environment(path, text, project, warnings)
            else: self._requirements(path, text, project, constraint=name.startswith("constraints"))
        except Exception as exc:
            warnings.append(f"Could not fully parse dependency manifest {path}: {exc}")
        return ReaderResult(True, project, warnings, [], {"language": self.language, "path": str(path)})

    def _add(self, project: Project, path: Path, raw: str, kind: str, *, line: int | None = None, group: str | None = None, locked: bool = False, direct: bool | None = True, constraint: bool = False, extra: dict[str, Any] | None = None) -> None:
        parts = _requirement_parts(raw)
        name = parts["name"].strip()
        if not name: return
        meta = {"language": "Python", "dependency_scope": "external_python", "evidence": "DECLARED", "original_name": name, "normalized_name": normalize_distribution_name(name), "declaration": parts["declaration"], "line": line, "group": group, "marker": parts["marker"], "source_type": parts["source_type"], "source_value": parts["source_value"], "editable": parts["editable"], "locked": locked, "direct": direct, "constraint": constraint}
        if extra: meta.update(extra)
        identity = (str(path), normalize_distribution_name(name), parts["version"], kind, group, constraint, locked)
        for existing in project.dependencies:
            em = existing.metadata or {}
            if (existing.source, em.get("normalized_name"), existing.version, existing.kind, em.get("group"), bool(em.get("constraint")), bool(em.get("locked"))) == identity:
                return
        project.add_dependency(DependencyNode(name=name, source=str(path), version=parts["version"], kind=kind, metadata=meta))

    def _pyproject(self, path: Path, text: str, project: Project) -> None:
        if tomllib is None: raise RuntimeError("tomllib is unavailable")
        data = tomllib.loads(text)
        p = data.get("project", {})
        for raw in p.get("dependencies", []) or []: self._add(project, path, str(raw), "runtime", line=_line_of(text, str(raw)))
        for group, reqs in (p.get("optional-dependencies", {}) or {}).items():
            for raw in reqs or []: self._add(project, path, str(raw), "optional", line=_line_of(text, str(raw)), group=str(group))
        for raw in (data.get("build-system", {}) or {}).get("requires", []) or []: self._add(project, path, str(raw), "build-system", line=_line_of(text, str(raw)))
        groups = data.get("dependency-groups", {}) or {}
        for group, reqs in groups.items():
            for raw in reqs or []:
                if isinstance(raw, str): self._add(project, path, raw, "development", line=_line_of(text, raw), group=str(group))
        poetry = ((data.get("tool", {}) or {}).get("poetry", {}) or {})
        self._poetry_tables(path, text, project, poetry)
        pdm = ((data.get("tool", {}) or {}).get("pdm", {}) or {})
        for group, reqs in (pdm.get("dev-dependencies", {}) or {}).items():
            for raw in reqs or []: self._add(project, path, str(raw), "development", line=_line_of(text, str(raw)), group=str(group))

    def _poetry_tables(self, path: Path, text: str, project: Project, poetry: dict) -> None:
        for name, spec in (poetry.get("dependencies", {}) or {}).items():
            if name.casefold() == "python": continue
            self._add_table_spec(project, path, text, name, spec, "runtime", None)
        for name, spec in (poetry.get("dev-dependencies", {}) or {}).items(): self._add_table_spec(project, path, text, name, spec, "development", "dev")
        for group, body in (poetry.get("group", {}) or {}).items():
            for name, spec in (body.get("dependencies", {}) or {}).items(): self._add_table_spec(project, path, text, name, spec, "development", str(group))

    def _add_table_spec(self, project, path, text, name, spec, kind, group):
        version = spec if isinstance(spec, str) else (spec.get("version") if isinstance(spec, dict) else None)
        raw = f"{name}{version or ''}"
        extra = {}
        if isinstance(spec, dict):
            for key in ("git", "url", "path", "markers", "optional"):
                if key in spec: extra[key] = spec[key]
        self._add(project, path, raw, "optional" if extra.get("optional") else kind, line=_line_of(text, name), group=group, extra=extra)

    def _requirements(self, path: Path, text: str, project: Project, constraint=False) -> None:
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"): continue
            if stripped.startswith(("-r ", "--requirement ", "-c ", "--constraint ")):
                directive, include_name = stripped.split(None, 1)
                include = (path.parent / include_name.strip()).resolve()
                root = Path(project.root).resolve()
                try:
                    include.relative_to(root)
                except ValueError:
                    continue
                if include.is_file():
                    try:
                        included_text = include.read_text(encoding="utf-8-sig")
                    except (OSError, UnicodeError):
                        continue
                    self._requirements(include, included_text, project, constraint=directive in {"-c", "--constraint"})
                continue
            if stripped.startswith("-") and not stripped.startswith(("-e ", "--editable ")): continue
            self._add(project, path, stripped, "constraint" if constraint else "runtime", line=line_no, constraint=constraint)

    def _setup_cfg(self, path, text, project):
        cfg = configparser.ConfigParser(interpolation=None); cfg.read_string(text)
        if cfg.has_option("options", "install_requires"):
            for raw in cfg.get("options", "install_requires").splitlines():
                if raw.strip(): self._add(project, path, raw.strip(), "runtime", line=_line_of(text, raw.strip()))
        if cfg.has_section("options.extras_require"):
            for group, value in cfg.items("options.extras_require"):
                for raw in value.splitlines():
                    if raw.strip(): self._add(project, path, raw.strip(), "optional", line=_line_of(text, raw.strip()), group=group)

    def _setup_py(self, path, text, project, warnings):
        try: tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc: warnings.append(f"Could not parse setup.py {path}: {exc.msg}"); return
        literals = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try: literals[node.targets[0].id] = ast.literal_eval(node.value)
                except Exception: pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call): continue
            func = node.func
            if not ((isinstance(func, ast.Name) and func.id == "setup") or (isinstance(func, ast.Attribute) and func.attr == "setup")): continue
            for kw in node.keywords:
                value = literals.get(kw.value.id) if isinstance(kw.value, ast.Name) else None
                if value is None:
                    try: value = ast.literal_eval(kw.value)
                    except Exception:
                        if kw.arg in {"install_requires", "extras_require"}: warnings.append(f"Dynamic setup.py {kw.arg} at {path}:{getattr(kw.value, 'lineno', '?')} was not executed")
                        continue
                if kw.arg == "install_requires" and isinstance(value, (list, tuple)):
                    for raw in value: self._add(project, path, str(raw), "runtime", line=getattr(kw.value, "lineno", None))
                elif kw.arg == "extras_require" and isinstance(value, dict):
                    for group, reqs in value.items():
                        for raw in reqs or []: self._add(project, path, str(raw), "optional", line=getattr(kw.value, "lineno", None), group=str(group))

    def _toml_manager(self, path, text, project, name):
        if tomllib is None: raise RuntimeError("tomllib is unavailable")
        data = tomllib.loads(text)
        if name == "pipfile":
            for section, kind in (("packages", "runtime"), ("dev-packages", "development")):
                for dep, spec in (data.get(section, {}) or {}).items(): self._add_table_spec(project, path, text, dep, spec, kind, section)
        else:
            for pkg in data.get("package", []) or []:
                dep = pkg.get("name"); version = pkg.get("version")
                if dep: self._add(project, path, f"{dep}=={version}" if version else dep, "locked", line=_line_of(text, f'name = "{dep}"'), locked=True, direct=None)

    def _pipfile_lock(self, path, text, project):
        data = json.loads(text)
        for section, kind in (("default", "locked"), ("develop", "locked-development")):
            for dep, spec in (data.get(section, {}) or {}).items():
                version = spec.get("version") if isinstance(spec, dict) else str(spec)
                extra = {"hashes": spec.get("hashes", [])} if isinstance(spec, dict) else {}
                self._add(project, path, f"{dep}{version or ''}", kind, line=_line_of(text, f'"{dep}"'), locked=True, direct=None, extra=extra)

    def _environment(self, path, text, project, warnings):
        # Conservative YAML subset: dependencies list and nested pip list only.
        in_deps = False; in_pip = False; base_indent = 0
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped == "dependencies:": in_deps=True; in_pip=False; base_indent=len(line)-len(line.lstrip()); continue
            if not in_deps: continue
            indent=len(line)-len(line.lstrip())
            if stripped and indent <= base_indent and not stripped.startswith("-"): in_deps=False; in_pip=False; continue
            if re.match(r"^-\s+pip\s*:\s*$", stripped): in_pip=True; continue
            m=re.match(r"^-\s+(.+)$", stripped)
            if not m: continue
            raw=m.group(1).strip()
            if raw == "pip:": in_pip=True; continue
            if in_pip: self._add(project, path, raw, "environment", line=line_no, group="pip", extra={"environment_manager":"pip"})
            else:
                # conda's name=version syntax is retained rather than pretending it is PEP 508.
                parts=raw.split("=",1); dep=parts[0].strip(); ver=("=="+parts[1].strip()) if len(parts)>1 and parts[1].strip() else ""
                self._add(project, path, dep+ver, "environment", line=line_no, group="conda", extra={"environment_manager":"conda"})


def link_python_imports_to_dependencies(project: Project) -> None:
    """Annotate Python imports/dependencies using only project-local static evidence."""
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    declared: dict[str, list[DependencyNode]] = {}
    for dep in project.dependencies:
        meta = dep.metadata or {}
        if meta.get("dependency_scope") == "external_python" and not meta.get("constraint"):
            declared.setdefault(meta.get("normalized_name") or normalize_distribution_name(dep.name), []).append(dep)
    # Deliberately tiny evidence-backed aliases; no broad guessing.
    aliases = {"pyyaml": {"yaml"}, "pillow": {"pil"}, "beautifulsoup4": {"bs4"}, "scikit-learn": {"sklearn"}}
    import_hits: dict[str, set[str]] = {key:set() for key in declared}
    for imp in project.imports:
        if imp.language != "Python": continue
        target = (imp.target or "").lstrip(".").split(".",1)[0]
        if not target: continue
        if target in stdlib:
            imp.metadata["dependency_scope"] = "standard_library"; continue
        matches=[]
        norm=normalize_distribution_name(target)
        if norm in declared: matches=[norm]
        else:
            for dist, names in aliases.items():
                if target.casefold() in names and dist in declared: matches.append(dist)
        if len(matches)==1:
            dist=matches[0]; imp.metadata.update({"dependency_scope":"external_python", "declared_dependency": declared[dist][0].name, "dependency_match":"declared"}); import_hits[dist].add(target)
        else:
            imp.metadata.setdefault("dependency_scope", "unclassified")
    for norm, deps in declared.items():
        hits=sorted(import_hits.get(norm, set()))
        for dep in deps:
            dep.metadata["import_evidence"] = hits
            dep.metadata["import_observed"] = bool(hits)
