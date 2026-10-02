"""
BARKLY DOCS
Ruby Reader

Static structural reader for Ruby source files.

This reader does NOT execute Ruby code.

It translates Ruby source into the common Barkly Project Model:

    Ruby Source
        ↓
    RubyReader
        ↓
    Barkly Project Model
        ↓
    Documentation / Graph / Website

Supported file types:

    .rb
    .rake
    .gemspec
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from model.project import (
    ClassNode,
    DependencyNode,
    DocumentationNode,
    EndpointNode,
    FileNode,
    FunctionNode,
    ImportNode,
    MethodNode,
    ModuleNode,
    Project,
    RelationshipNode,
    VariableNode,
)

from readers.base import LanguageReader, ReaderResult


class RubyReader(LanguageReader):
    """
    Static structural reader for Ruby source files.
    """

    language = "Ruby"

    extensions = (
        ".rb",
        ".rake",
        ".gemspec",
    )

    version = "0.3.0"

    manifest_names = ("Gemfile", "Gemfile.lock")

    # ========================================================
    # REGEX
    # ========================================================

    _REQUIRE_RE = re.compile(
        r"""^\s*require\s+(?P<target>['"])(?P<name>.+?)(?P=target)\s*(?:#.*)?$"""
    )

    _REQUIRE_RELATIVE_RE = re.compile(
        r"""^\s*require_relative\s+(?P<target>['"])(?P<name>.+?)(?P=target)\s*(?:#.*)?$"""
    )

    _CLASS_RE = re.compile(
        r"""
        ^\s*
        class
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_:]*)
        (?:\s*<\s*(?P<superclass>[A-Za-z_][A-Za-z0-9_:]*(?:\s*::\s*[A-Za-z_][A-Za-z0-9_:]*)*))?
        (?:\s*;\s*)?
        $
        """,
        re.VERBOSE,
    )

    _MODULE_RE = re.compile(
        r"""
        ^\s*
        module
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_:]*)
        (?:\s*;\s*)?
        $
        """,
        re.VERBOSE,
    )

    # Ruby method names can include:
    #
    #   foo
    #   foo?
    #   foo!
    #   foo=
    #   foo?
    #   foo!
    #   initialize
    #   self.foo
    #   self.foo=
    #   <=>
    #   ==
    #   []
    #   []=
    #   +
    #   -
    #
    _METHOD_RE = re.compile(
        r"""
        ^\s*
        def
        \s+
        (?:
            (?P<receiver>
                self
                |
                [A-Za-z_][A-Za-z0-9_:]*
            )
            \.
        )?
        (?P<name>
            [A-Za-z_][A-Za-z0-9_!?=]*
            |
            <=>|==|!=|<=|>=|<|>|\+|-|\*|/|%|&
            |\[\]=|\[\]
            |\+@|-@|~
        )
        (?P<params>\s*\(.*\))?
        \s*
        $
        """,
        re.VERBOSE,
    )

    _INCLUDE_RE = re.compile(
        r"""
        ^\s*
        include
        \s+
        (?P<names>.+?)
        \s*
        $
        """,
        re.VERBOSE,
    )

    _EXTEND_RE = re.compile(
        r"""
        ^\s*
        extend
        \s+
        (?P<names>.+?)
        \s*
        $
        """,
        re.VERBOSE,
    )

    _ATTRIBUTE_RE = re.compile(
        r"""
        ^\s*
        (?P<kind>
            attr_reader
            |attr_writer
            |attr_accessor
        )
        \s+
        (?P<names>.+?)
        \s*
        $
        """,
        re.VERBOSE,
    )

    _CONSTANT_RE = re.compile(
        r"""
        ^\s*
        (?P<name>[A-Z][A-Za-z0-9_]*(?:\s*=\s*.+)?)
        \s*$
        """,
        re.VERBOSE,
    )

    _INSTANCE_VARIABLE_RE = re.compile(r"""(?<![A-Za-z0-9_])@[A-Za-z_][A-Za-z0-9_]*""")

    _CLASS_VARIABLE_RE = re.compile(r"""(?<![A-Za-z0-9_])@@[A-Za-z_][A-Za-z0-9_]*""")

    _LOCAL_VARIABLE_RE = re.compile(
        r"""
        \b
        [a-z_][A-Za-z0-9_]*
        \s*=
        """,
        re.VERBOSE,
    )

    _RUBYDOC_RE = re.compile(
        r"""
        ^\s*
        \#\#\#?
        (?:\s)?(?P<text>.*?)
        \s*$
        """,
        re.VERBOSE,
    )

    # Ruby keywords which introduce nested structures that
    # normally terminate with `end`.
    _BLOCK_OPENERS = {
        "if",
        "unless",
        "case",
        "begin",
        "while",
        "until",
        "for",
        "class",
        "module",
        "def",
    }

    # These keywords can open a block with `do`.
    _DO_BLOCK_RE = re.compile(
        r"""
        \b
        (?:do)
        (?:\s*\|.*?\|)?
        \s*$
        """,
        re.VERBOSE,
    )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def can_read(self, path: Path) -> bool:
        """Read Ruby source plus Bundler manifests with extensionless names."""
        return path.name in self.manifest_names or super().can_read(path)

    def read(
        self,
        path: Path,
        project: Project,
    ) -> ReaderResult:
        """
        Analyze one Ruby source file.

        The source is treated as data only.
        Ruby code is never imported or executed.
        """

        warnings: list[str] = []
        errors: list[str] = []

        try:
            source = self.read_text(path)
        except Exception as exc:
            return ReaderResult(
                success=False,
                project=project,
                warnings=warnings,
                errors=[f"{path}: unable to read Ruby source: {exc}"],
                metadata={
                    "language": self.language,
                    "version": self.version,
                },
            )

        if path.name in self.manifest_names:
            return self._read_dependency_manifest(path, source, project)
        if path.suffix.lower() == ".gemspec":
            self._read_dependency_manifest(path, source, project, add_file=False)

        try:
            # ------------------------------------------------
            # FILE
            # ------------------------------------------------

            file_node = FileNode(
                path=str(path),
                language=self.language,
                size=len(source.encode("utf-8", errors="replace")),
                metadata={
                    "reader": self.__class__.__name__,
                    "reader_version": self.version,
                },
            )

            project.add_file(file_node)

            # ------------------------------------------------
            # FILE MODULE
            # ------------------------------------------------

            module_name = self._module_name(path)

            file_module = ModuleNode(
                name=module_name,
                path=str(path),
                language=self.language,
                metadata={
                    "kind": "ruby_file",
                },
            )

            project.add_module(file_module)

            file_node.modules.append(module_name)

            # ------------------------------------------------
            # IMPORTS
            # ------------------------------------------------

            imports = self._extract_imports(
                source,
                path,
                project,
                file_module,
            )

            # ------------------------------------------------
            # STRUCTURES
            # ------------------------------------------------

            structures = self._scan_structures(source)

            classes = [item for item in structures if item["kind"] == "class"]

            modules = [item for item in structures if item["kind"] == "module"]

            # ------------------------------------------------
            # MODULE NODES
            # ------------------------------------------------

            for structure in modules:
                name = structure["name"]

                node = ModuleNode(
                    name=name,
                    path=str(path),
                    language=self.language,
                    documentation=structure.get("documentation"),
                    metadata={
                        "ruby_kind": "module",
                        "line_start": structure["line_start"],
                        "line_end": structure["line_end"],
                        "parent": structure.get("parent"),
                    },
                )

                project.add_module(node)

            # ------------------------------------------------
            # CLASSES
            # ------------------------------------------------

            for structure in classes:
                class_name = structure["name"]

                methods = self._extract_methods(
                    structure["body"],
                    structure["body_start"],
                    class_name,
                )

                method_names = [method["name"] for method in methods]

                includes = self._extract_includes(structure["body"])

                extends = self._extract_extends(structure["body"])

                attributes = self._extract_attributes(structure["body"])

                class_node = ClassNode(
                    name=class_name,
                    path=str(path),
                    language=self.language,
                    bases=self._class_bases(structure),
                    methods=method_names,
                    attributes=attributes,
                    documentation=structure.get("documentation"),
                    line_start=structure["line_start"],
                    line_end=structure["line_end"],
                    metadata={
                        "ruby_kind": "class",
                        "superclass": structure.get("superclass"),
                        "includes": includes,
                        "extends": extends,
                        "parent": structure.get("parent"),
                    },
                )

                project.add_class(class_node)

                file_node.classes.append(class_name)
                file_module.classes.append(class_name)

                # --------------------------------------------
                # INHERITANCE
                # --------------------------------------------

                for base in self._class_bases(structure):
                    project.add_relationship(
                        RelationshipNode(
                            source=class_name,
                            target=base,
                            kind="inherits",
                            source_file=str(path),
                        )
                    )

                # --------------------------------------------
                # INCLUDE
                # --------------------------------------------

                for include_name in includes:
                    project.add_relationship(
                        RelationshipNode(
                            source=class_name,
                            target=include_name,
                            kind="includes",
                            source_file=str(path),
                        )
                    )

                # --------------------------------------------
                # EXTEND
                # --------------------------------------------

                for extend_name in extends:
                    project.add_relationship(
                        RelationshipNode(
                            source=class_name,
                            target=extend_name,
                            kind="extends",
                            source_file=str(path),
                        )
                    )

                # --------------------------------------------
                # METHODS
                # --------------------------------------------

                for method in methods:
                    method_node = MethodNode(
                        name=method["name"],
                        path=str(path),
                        language=self.language,
                        parameters=self._parse_parameters(method.get("params", "")),
                        documentation=method.get("documentation"),
                        line_start=method["line_start"],
                        line_end=method["line_end"],
                        class_name=class_name,
                        metadata={
                            "ruby_kind": "method",
                            "visibility": method.get(
                                "visibility",
                                "public",
                            ),
                            "singleton": method.get(
                                "singleton",
                                False,
                            ),
                            "receiver": method.get("receiver"),
                        },
                    )

                    project.add_method(method_node)

                    project.add_relationship(
                        RelationshipNode(
                            source=class_name,
                            target=method["name"],
                            kind="contains",
                            source_file=str(path),
                        )
                    )

            # ------------------------------------------------
            # TOP-LEVEL METHODS
            # ------------------------------------------------

            top_level_methods = self._extract_top_level_methods(source)

            for function in top_level_methods:
                function_node = FunctionNode(
                    name=function["name"],
                    path=str(path),
                    language=self.language,
                    parameters=self._parse_parameters(function.get("params", "")),
                    documentation=function.get("documentation"),
                    line_start=function["line_start"],
                    line_end=function["line_end"],
                    metadata={
                        "ruby_kind": "top_level_method",
                        "visibility": function.get(
                            "visibility",
                            "public",
                        ),
                        "singleton": function.get(
                            "singleton",
                            False,
                        ),
                    },
                )

                project.add_function(function_node)

                file_node.functions.append(function["name"])

                file_module.functions.append(function["name"])

            # ------------------------------------------------
            # HTTP ENDPOINTS
            # ------------------------------------------------

            endpoints = self._extract_endpoints(
                source,
                path,
                project,
                structures,
            )

            # ------------------------------------------------
            # VARIABLES / CONSTANTS
            # ------------------------------------------------

            self._extract_variables(
                source,
                path,
                project,
            )

            # ------------------------------------------------
            # DOCUMENTATION
            # ------------------------------------------------

            self._extract_documentation(
                source,
                path,
                project,
            )

            # ------------------------------------------------
            # FILE METADATA
            # ------------------------------------------------

            file_node.metadata.update(
                {
                    "ruby_version": "unknown",
                    "classes": [structure["name"] for structure in classes],
                    "modules": [structure["name"] for structure in modules],
                    "imports": [item["name"] for item in imports],
                    "parser": "static-ruby-structural-scanner",
                }
            )

            return ReaderResult(
                success=True,
                project=project,
                warnings=warnings,
                errors=errors,
                metadata={
                    "language": self.language,
                    "version": self.version,
                    "parser": "static-ruby-structural-scanner",
                    "static_analysis": True,
                    "ruby_version": "unknown",
                    "classes": len(classes),
                    "modules": len(modules),
                    "top_level_functions": len(top_level_methods),
                    "endpoints": len(endpoints),
                },
            )

        except Exception as exc:
            errors.append(f"{path}: Ruby structural analysis failed: {exc}")

            return ReaderResult(
                success=False,
                project=project,
                warnings=warnings,
                errors=errors,
                metadata={
                    "language": self.language,
                    "version": self.version,
                },
            )

    _GEM_DECLARATION_RE = re.compile(
        r'''^\s*gem\s+['\"](?P<name>[^'\"]+)['\"](?P<rest>.*)$'''
    )
    _GEMSPEC_DEPENDENCY_RE = re.compile(
        r'''^\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)?(?P<kind>add_dependency|add_runtime_dependency|add_development_dependency)\s*(?:\(\s*)?['\"](?P<name>[^'\"]+)['\"](?P<rest>.*)$'''
    )
    _VERSION_RE = re.compile(r'''['\"](?P<version>(?:[~><=!\s]*\d[^'\"]*))['\"]''')

    def _read_dependency_manifest(self, path: Path, source: str, project: Project, *, add_file: bool = True) -> ReaderResult:
        """Extract declared Ruby gem dependencies without executing Bundler/Ruby code."""
        if add_file:
            file_node = FileNode(
                path=str(path), language="Ruby", size=len(source.encode("utf-8", errors="replace")),
                metadata={"reader": self.__class__.__name__, "reader_version": self.version, "kind": "ruby_dependency_manifest"},
            )
            project.add_file(file_node)
        found = 0
        if path.name == "Gemfile.lock":
            in_specs = False
            for line_number, line in enumerate(source.splitlines(), start=1):
                if line == "  specs:":
                    in_specs = True
                    continue
                if in_specs and line and not line.startswith("    "):
                    in_specs = False
                if not in_specs:
                    continue
                match = re.match(r"^    ([A-Za-z0-9_.-]+) \(([^)]+)\)\s*$", line)
                if match:
                    self._add_gem_dependency(project, path, match.group(1), match.group(2), "locked", line_number, "Gemfile.lock")
                    found += 1
        else:
            pattern = self._GEM_DECLARATION_RE if path.name == "Gemfile" else self._GEMSPEC_DEPENDENCY_RE
            for line_number, line in enumerate(source.splitlines(), start=1):
                stripped = self._strip_ruby_comment(line).strip()
                match = pattern.match(stripped)
                if not match:
                    continue
                kind = "runtime"
                if path.suffix.lower() == ".gemspec" and match.groupdict().get("kind") == "add_development_dependency":
                    kind = "development"
                version_match = self._VERSION_RE.search(match.group("rest") or "")
                version = version_match.group("version").strip() if version_match else None
                self._add_gem_dependency(project, path, match.group("name"), version, kind, line_number, path.name)
                found += 1
        return ReaderResult(success=True, project=project, metadata={"language": self.language, "version": self.version, "dependencies": found})

    def _add_gem_dependency(self, project: Project, path: Path, name: str, version: str | None, kind: str, line: int, source_kind: str) -> None:
        identity = (name, str(path), line, source_kind)
        if not any((d.name, d.source, (d.metadata or {}).get("line"), (d.metadata or {}).get("manifest")) == identity for d in project.dependencies):
            project.add_dependency(DependencyNode(
                name=name, source=str(path), version=version, kind=kind,
                metadata={"language": "Ruby", "manifest": source_kind, "line": line, "dependency_scope": "external_gem", "evidence": "DECLARED"},
            ))
        project.add_relationship(RelationshipNode(
            source=str(path), target=name, kind="depends_on", source_file=str(path),
            source_location={"line": line}, evidence="DECLARED",
            metadata={"language": "Ruby", "dependency_scope": "external_gem", "manifest": source_kind, "version": version, "dependency_kind": kind},
        ))

    # ========================================================
    # STRUCTURE SCANNER
    # ========================================================

    def _scan_structures(
        self,
        source: str,
    ) -> list[dict[str, Any]]:
        """
        Scan Ruby class/module structures.

        The important difference from the previous scanner is
        that `end` is matched against a complete Ruby nesting
        stack rather than assuming every `end` closes a class
        or module.

        Example:

            class Bot
              def start
                if ready?
                  run
                end
              end
            end

        produces:

            class Bot
                def start
                    if
        """

        lines = source.splitlines(keepends=True)

        structures: list[dict[str, Any]] = []

        stack: list[dict[str, Any]] = []

        offsets: list[int] = []

        offset = 0

        for line in lines:
            offsets.append(offset)
            offset += len(line)

        total_length = len(source)

        for index, raw_line in enumerate(lines):
            line_start_offset = offsets[index]
            line_end_offset = (
                offsets[index + 1] if index + 1 < len(offsets) else total_length
            )

            stripped = self._strip_ruby_comment(raw_line).strip()

            if not stripped:
                continue

            # ------------------------------------------------
            # CLASS
            # ------------------------------------------------

            class_match = self._CLASS_RE.match(stripped)

            if class_match:
                name = class_match.group("name")

                structure = {
                    "kind": "class",
                    "name": name,
                    "superclass": class_match.group("superclass"),
                    "line_start": index + 1,
                    "line_end": None,
                    "offset": line_start_offset,
                    "body_start": line_end_offset,
                    "body": "",
                    "parent": self._nearest_namespace(stack),
                    "documentation": self._documentation_before(
                        lines,
                        index,
                    ),
                }

                stack.append(
                    {
                        "kind": "class",
                        "structure": structure,
                        "start_offset": line_start_offset,
                    }
                )

                continue

            # ------------------------------------------------
            # MODULE
            # ------------------------------------------------

            module_match = self._MODULE_RE.match(stripped)

            if module_match:
                name = module_match.group("name")

                structure = {
                    "kind": "module",
                    "name": name,
                    "superclass": None,
                    "line_start": index + 1,
                    "line_end": None,
                    "offset": line_start_offset,
                    "body_start": line_end_offset,
                    "body": "",
                    "parent": self._nearest_namespace(stack),
                    "documentation": self._documentation_before(
                        lines,
                        index,
                    ),
                }

                stack.append(
                    {
                        "kind": "module",
                        "structure": structure,
                        "start_offset": line_start_offset,
                    }
                )

                continue

            # ------------------------------------------------
            # METHOD
            # ------------------------------------------------

            method_match = self._METHOD_RE.match(stripped)

            if method_match:
                stack.append(
                    {
                        "kind": "def",
                        "start_offset": line_start_offset,
                    }
                )

                continue

            # ------------------------------------------------
            # OPENING STRUCTURES
            # ------------------------------------------------

            if self._opens_end_structure(stripped):
                stack.append(
                    {
                        "kind": self._opening_kind(stripped),
                        "start_offset": line_start_offset,
                    }
                )

                continue

            # ------------------------------------------------
            # END
            # ------------------------------------------------

            if self._is_end_line(stripped):
                self._close_stack_structure(
                    stack,
                    line_end_offset,
                    index + 1,
                    source,
                    structures,
                )

                continue

        # ----------------------------------------------------
        # CLOSE UNFINISHED STRUCTURES
        # ----------------------------------------------------

        while stack:
            entry = stack.pop()

            if entry["kind"] not in {
                "class",
                "module",
            }:
                continue

            structure = entry["structure"]

            structure["line_end"] = len(lines)

            structure["body"] = source[structure["body_start"] :]

            structures.append(structure)

        # Preserve source order.
        structures.sort(
            key=lambda item: (
                item["line_start"],
                item["line_end"] or item["line_start"],
            )
        )

        return structures

    def _close_stack_structure(
        self,
        stack: list[dict[str, Any]],
        end_offset: int,
        end_line: int,
        source: str,
        structures: list[dict[str, Any]],
    ) -> None:
        """
        Close the most recent Ruby nesting structure.

        Only classes and modules become Project Model
        structures. Other entries merely protect namespace
        boundaries from premature closure.
        """

        if not stack:
            return

        entry = stack.pop()

        if entry["kind"] not in {
            "class",
            "module",
        }:
            return

        structure = entry["structure"]

        structure["line_end"] = end_line

        structure["body"] = source[structure["body_start"] : end_offset]

        structures.append(structure)

    # ========================================================
    # RUBY NESTING
    # ========================================================

    def _opens_end_structure(
        self,
        stripped: str,
    ) -> bool:
        """
        Return True when a Ruby line opens a structure that
        normally requires `end`.
        """

        if self._METHOD_RE.match(stripped):
            return True

        if self._CLASS_RE.match(stripped):
            return True

        if self._MODULE_RE.match(stripped):
            return True

        if re.match(
            r"^(if|unless|case|begin|while|until|for)\b",
            stripped,
        ):
            return True

        if re.search(
            r"\bdo(?:\s*\|.*?\|)?\s*$",
            stripped,
        ):
            return True

        return False

    def _opening_kind(
        self,
        stripped: str,
    ) -> str:
        """
        Determine the kind of a generic Ruby nesting opener.
        """

        if re.match(r"^if\b", stripped):
            return "if"

        if re.match(r"^unless\b", stripped):
            return "unless"

        if re.match(r"^case\b", stripped):
            return "case"

        if re.match(r"^begin\b", stripped):
            return "begin"

        if re.match(r"^while\b", stripped):
            return "while"

        if re.match(r"^until\b", stripped):
            return "until"

        if re.match(r"^for\b", stripped):
            return "for"

        if re.search(
            r"\bdo(?:\s*\|.*?\|)?\s*$",
            stripped,
        ):
            return "do"

        return "block"

    def _nearest_namespace(
        self,
        stack: list[dict[str, Any]],
    ) -> str | None:
        """
        Return the nearest class/module namespace.
        """

        for entry in reversed(stack):
            if entry["kind"] in {
                "class",
                "module",
            }:
                return entry["structure"]["name"]

        return None

    # ========================================================
    # METHODS
    # ========================================================

    def _extract_methods(
        self,
        body: str,
        body_start_offset: int,
        class_name: str,
    ) -> list[dict[str, Any]]:
        """
        Extract methods from a class/module body.

        Uses the same Ruby nesting model so internal `end`
        statements do not prematurely terminate methods.
        """

        lines = body.splitlines(keepends=True)

        methods: list[dict[str, Any]] = []

        stack: list[dict[str, Any]] = []

        visibility = "public"

        offsets: list[int] = []

        offset = body_start_offset

        for line in lines:
            offsets.append(offset)
            offset += len(line)

        for index, raw_line in enumerate(lines):
            stripped = self._strip_ruby_comment(raw_line).strip()

            if not stripped:
                continue

            # ------------------------------------------------
            # VISIBILITY
            # ------------------------------------------------

            if stripped in {
                "public",
                "private",
                "protected",
            }:
                visibility = stripped
                continue

            method_match = self._METHOD_RE.match(stripped)

            if method_match:
                stack.append(
                    {
                        "kind": "def",
                        "method": {
                            "name": method_match.group("name"),
                            "params": (method_match.group("params") or ""),
                            "receiver": (method_match.group("receiver")),
                            "singleton": bool(method_match.group("receiver")),
                            "line_start": self._line_number_from_offset(
                                body,
                                offsets[index],
                            ),
                            "line_end": None,
                            "visibility": visibility,
                            "documentation": self._documentation_before(
                                lines,
                                index,
                            ),
                            "class_name": class_name,
                        },
                    }
                )

                continue

            if self._opens_end_structure(stripped):
                stack.append(
                    {
                        "kind": self._opening_kind(stripped),
                    }
                )

                continue

            if self._is_end_line(stripped):
                if not stack:
                    continue

                entry = stack.pop()

                if entry["kind"] == "def":
                    method = entry["method"]

                    method["line_end"] = self._line_number_from_offset(
                        body,
                        offsets[index] + len(raw_line),
                    )

                    methods.append(method)

        # Handle unterminated methods conservatively.
        while stack:
            entry = stack.pop()

            if entry["kind"] != "def":
                continue

            method = entry["method"]

            method["line_end"] = self._line_number_from_offset(
                body,
                len(body),
            )

            methods.append(method)

        methods.sort(
            key=lambda item: (
                item["line_start"],
                item["line_end"] or item["line_start"],
            )
        )

        return methods

    def _extract_top_level_methods(
        self,
        source: str,
    ) -> list[dict[str, Any]]:
        """
        Extract top-level Ruby methods.

        Methods nested inside classes/modules are excluded.
        """

        lines = source.splitlines(keepends=True)

        methods: list[dict[str, Any]] = []

        stack: list[str] = []

        visibility = "public"

        offsets: list[int] = []

        offset = 0

        for line in lines:
            offsets.append(offset)
            offset += len(line)

        for index, raw_line in enumerate(lines):
            stripped = self._strip_ruby_comment(raw_line).strip()

            if not stripped:
                continue

            if stripped in {
                "public",
                "private",
                "protected",
            }:
                visibility = stripped
                continue

            method_match = self._METHOD_RE.match(stripped)

            if method_match:
                if not any(
                    item
                    in {
                        "class",
                        "module",
                    }
                    for item in stack
                ):
                    stack.append("def")

                    methods.append(
                        {
                            "name": method_match.group("name"),
                            "params": (method_match.group("params") or ""),
                            "receiver": (method_match.group("receiver")),
                            "singleton": bool(method_match.group("receiver")),
                            "line_start": index + 1,
                            "line_end": None,
                            "visibility": visibility,
                            "documentation": self._documentation_before(
                                lines,
                                index,
                            ),
                        }
                    )

                else:
                    stack.append("def")

                continue

            if self._CLASS_RE.match(stripped):
                stack.append("class")
                continue

            if self._MODULE_RE.match(stripped):
                stack.append("module")
                continue

            if self._opens_end_structure(stripped):
                stack.append(self._opening_kind(stripped))
                continue

            if self._is_end_line(stripped):
                if not stack:
                    continue

                closed = stack.pop()

                if closed == "def":
                    # Find the most recent unfinished top-level
                    # method and close it.
                    for method in reversed(methods):
                        if method["line_end"] is None:
                            method["line_end"] = index + 1
                            break

        # Conservative close for unfinished methods.
        for method in methods:
            if method["line_end"] is None:
                method["line_end"] = len(lines)

        return methods

    # ========================================================
    # HTTP ENDPOINTS
    # ========================================================

    _HTTP_ROUTE_METHODS = {
        "get", "post", "put", "patch", "delete", "options", "head",
        "connect", "trace", "link", "unlink",
    }

    def _extract_endpoints(
        self,
        source: str,
        path: Path,
        project: Project,
        structures: list[dict[str, Any]],
    ) -> list[EndpointNode]:
        """Extract statically identifiable Sinatra route declarations.

        Detection is intentionally framework-gated: a method named ``get`` is
        not considered HTTP routing unless this file declares Sinatra usage or
        the declaration is enclosed by a Sinatra application class.
        """
        lines = source.splitlines()
        endpoints: list[EndpointNode] = []
        # Only `require "sinatra"` enables the classic top-level DSL.
        # `require "sinatra/base"` alone does not, so those files require a
        # declaration inside a Sinatra::Base/Application subclass.
        file_uses_sinatra = bool(
            re.search(
                r"^\s*require\s+['\"]sinatra['\"]\s*(?:#.*)?$",
                source,
                re.MULTILINE,
            )
        )

        for index, raw_line in enumerate(lines):
            stripped = self._strip_ruby_comment(raw_line).strip()
            match = re.match(
                r"^(get|post|put|patch|delete|options|head|connect|trace|link|unlink)\b(.*)$",
                stripped,
                re.IGNORECASE,
            )
            if not match:
                continue

            method = match.group(1).upper()
            enclosing = self._endpoint_enclosing_structure(index + 1, structures)
            superclass = str((enclosing or {}).get("superclass") or "")
            enclosing_is_sinatra = "Sinatra::" in superclass
            if not file_uses_sinatra and not enclosing_is_sinatra:
                continue

            statement, end_index = self._collect_route_statement(lines, index)
            declaration = self._strip_ruby_comment(statement).strip()
            route_match = re.match(
                r"^(?:get|post|put|patch|delete|options|head|connect|trace|link|unlink)\b\s*(.*)$",
                declaration,
                re.IGNORECASE | re.DOTALL,
            )
            if not route_match:
                continue

            path_value, remainder = self._parse_route_first_argument(route_match.group(1))
            if path_value is None:
                continue

            line_number = index + 1
            enclosing_name = (enclosing or {}).get("name")
            endpoint_id = f"{method} {path_value}@{path}:{line_number}"
            documentation = self._documentation_before(lines, index)
            metadata = {
                "id": endpoint_id,
                "framework": "Sinatra",
                "line": line_number,
                "line_end": end_index + 1,
                "enclosing": enclosing_name,
                "handler_kind": "route_block",
                "evidence": "DETECTED",
                "declaration": declaration,
            }
            options = remainder.strip().rstrip("{").strip()
            options = re.sub(r"\bdo\s*(?:\|.*?\|)?\s*$", "", options).strip()
            if options.startswith(","):
                options = options[1:].strip()
            if options:
                metadata["route_options"] = options

            endpoint = EndpointNode(
                path=path_value,
                method=method,
                source_file=str(path),
                handler=None,
                documentation=documentation,
                metadata=metadata,
            )
            project.add_endpoint(endpoint)
            endpoints.append(endpoint)

            if enclosing_name:
                project.add_relationship(
                    RelationshipNode(
                        source=enclosing_name,
                        target=endpoint_id,
                        kind="contains",
                        source_file=str(path),
                        source_location={"line": line_number},
                        evidence="DETECTED",
                        metadata={"framework": "Sinatra"},
                    )
                )

        return endpoints

    def _endpoint_enclosing_structure(
        self,
        line_number: int,
        structures: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        candidates = [
            item for item in structures
            if item.get("line_start")
            and item.get("line_end")
            and int(item["line_start"]) <= line_number <= int(item["line_end"])
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: int(item.get("line_start") or 0))

    def _collect_route_statement(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[str, int]:
        """Collect a possibly multiline route declaration without its body."""
        parts: list[str] = []
        paren_depth = 0
        quote: str | None = None
        escaped = False
        for index in range(start_index, min(len(lines), start_index + 20)):
            line = self._strip_ruby_comment(lines[index])
            parts.append(line.strip())
            for char in line:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if quote:
                    if char == quote:
                        quote = None
                    continue
                if char in {"'", '"'}:
                    quote = char
                elif char == "(":
                    paren_depth += 1
                elif char == ")" and paren_depth:
                    paren_depth -= 1
            joined = " ".join(parts)
            if paren_depth == 0 and (
                re.search(r"\bdo(?:\s*\|.*?\|)?\s*$", joined)
                or joined.rstrip().endswith("{")
                or index == start_index
            ):
                return joined, index
        return " ".join(parts), min(len(lines) - 1, start_index + len(parts) - 1)

    def _parse_route_first_argument(self, value: str) -> tuple[str | None, str]:
        """Return the first statically readable route pattern and remaining options."""
        text = value.strip()
        if text.startswith("("):
            text = text[1:].lstrip()

        if not text:
            return None, ""

        if text[0] in {"'", '"'}:
            quote = text[0]
            escaped = False
            chars: list[str] = []
            for index, char in enumerate(text[1:], start=1):
                if escaped:
                    chars.append(char)
                    escaped = False
                    continue
                if char == "\\":
                    chars.append(char)
                    escaped = True
                    continue
                if char == quote:
                    return "".join(chars), text[index + 1:].lstrip(" )")
                chars.append(char)
            return None, text

        if text.startswith("%r{"):
            end = text.find("}", 3)
            if end != -1:
                return text[: end + 1], text[end + 1:].lstrip(" )")

        if text.startswith("/"):
            escaped = False
            for index, char in enumerate(text[1:], start=1):
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                elif char == "/":
                    return text[: index + 1], text[index + 1:].lstrip(" )")

        # Dynamic expressions are intentionally unresolved rather than guessed.
        return None, text

    # ========================================================
    # IMPORTS
    # ========================================================

    def _extract_imports(
        self,
        source: str,
        path: Path,
        project: Project,
        file_module: ModuleNode,
    ) -> list[dict[str, str]]:
        """
        Extract require / require_relative statements.
        """

        imports: list[dict[str, str]] = []

        for line in source.splitlines():
            stripped = self._strip_ruby_comment(line).strip()

            if not stripped:
                continue

            match = self._REQUIRE_RELATIVE_RE.match(stripped)

            if match:
                name = match.group("name")

                imports.append(
                    {
                        "name": name,
                        "kind": "require_relative",
                    }
                )

                project.add_import(
                    ImportNode(
                        source_file=str(path),
                        target=name,
                        language=self.language,
                        metadata={"ruby_kind": "require_relative", "dependency_scope": "internal_project"},
                    )
                )

                project.add_relationship(
                    RelationshipNode(
                        source=str(path),
                        target=name,
                        kind="imports",
                        source_file=str(path),
                    )
                )

                file_module.imports.append(name)

                continue

            match = self._REQUIRE_RE.match(stripped)

            if match:
                name = match.group("name")

                imports.append(
                    {
                        "name": name,
                        "kind": "require",
                    }
                )

                project.add_import(
                    ImportNode(
                        source_file=str(path),
                        target=name,
                        language=self.language,
                        metadata={"ruby_kind": "require", "dependency_scope": "unclassified"},
                    )
                )

                project.add_relationship(
                    RelationshipNode(
                        source=str(path),
                        target=name,
                        kind="imports",
                        source_file=str(path),
                    )
                )

                file_module.imports.append(name)

        return imports

    # ========================================================
    # INCLUDES / EXTENDS
    # ========================================================

    def _extract_includes(
        self,
        body: str,
    ) -> list[str]:
        """
        Extract Ruby include declarations.
        """

        names: list[str] = []

        for line in body.splitlines():
            stripped = self._strip_ruby_comment(line).strip()

            match = self._INCLUDE_RE.match(stripped)

            if not match:
                continue

            names.extend(self._split_symbol_list(match.group("names")))

        return names

    def _extract_extends(
        self,
        body: str,
    ) -> list[str]:
        """
        Extract Ruby extend declarations.
        """

        names: list[str] = []

        for line in body.splitlines():
            stripped = self._strip_ruby_comment(line).strip()

            match = self._EXTEND_RE.match(stripped)

            if not match:
                continue

            names.extend(self._split_symbol_list(match.group("names")))

        return names

    # ========================================================
    # ATTRIBUTES
    # ========================================================

    def _extract_attributes(
        self,
        body: str,
    ) -> list[str]:
        """
        Extract attr_reader / attr_writer / attr_accessor.
        """

        attributes: list[str] = []

        for line in body.splitlines():
            stripped = self._strip_ruby_comment(line).strip()

            match = self._ATTRIBUTE_RE.match(stripped)

            if not match:
                continue

            kind = match.group("kind")

            for name in self._split_symbol_list(match.group("names")):
                attributes.append(f"{kind}:{name}")

        return attributes

    # ========================================================
    # VARIABLES
    # ========================================================

    def _extract_variables(
        self,
        source: str,
        path: Path,
        project: Project,
    ) -> None:
        """
        Extract meaningful Ruby variables and constants.

        This intentionally remains static and conservative.
        """

        seen: set[tuple[str, str]] = set()

        for line_number, raw_line in enumerate(
            source.splitlines(),
            start=1,
        ):
            line = self._strip_ruby_comment(raw_line)

            # --------------------------------------------
            # CONSTANTS
            # --------------------------------------------

            constant_match = re.match(
                r"""
                ^\s*
                (?P<name>
                    [A-Z][A-Za-z0-9_]*
                    (?:\s*=\s*(?P<value>.*))?
                )
                \s*$
                """,
                line,
                re.VERBOSE,
            )

            if constant_match:
                name = constant_match.group("name")

                if "=" in name:
                    name, value = name.split(
                        "=",
                        1,
                    )

                    name = name.strip()
                    value = value.strip()
                else:
                    value = None

                key = ("constant", name)

                if key not in seen:
                    seen.add(key)

                    project.add_variable(
                        VariableNode(
                            name=name,
                            path=str(path),
                            language=self.language,
                            value=value,
                            constant=True,
                            line=line_number,
                            metadata={"ruby_kind": "constant"},
                        )
                    )

            # --------------------------------------------
            # INSTANCE VARIABLES
            # --------------------------------------------

            for match in self._INSTANCE_VARIABLE_RE.finditer(line):
                name = match.group(0)

                key = (
                    "instance_variable",
                    name,
                )

                if key in seen:
                    continue

                seen.add(key)

                project.add_variable(
                    VariableNode(
                        name=name,
                        path=str(path),
                        language=self.language,
                        constant=False,
                        line=line_number,
                        metadata={"ruby_kind": "instance_variable"},
                    )
                )

            # --------------------------------------------
            # CLASS VARIABLES
            # --------------------------------------------

            for match in self._CLASS_VARIABLE_RE.finditer(line):
                name = match.group(0)

                key = (
                    "class_variable",
                    name,
                )

                if key in seen:
                    continue

                seen.add(key)

                project.add_variable(
                    VariableNode(
                        name=name,
                        path=str(path),
                        language=self.language,
                        constant=False,
                        line=line_number,
                        metadata={"ruby_kind": "class_variable"},
                    )
                )

            # --------------------------------------------
            # LOCAL ASSIGNMENTS
            # --------------------------------------------

            for match in self._LOCAL_VARIABLE_RE.finditer(line):
                name = (
                    match.group(0)
                    .split(
                        "=",
                        1,
                    )[0]
                    .strip()
                )

                if name in {
                    "if",
                    "unless",
                    "while",
                    "until",
                    "case",
                    "when",
                    "return",
                    "yield",
                    "next",
                    "break",
                    "redo",
                    "retry",
                    "def",
                    "class",
                    "module",
                    "begin",
                    "end",
                }:
                    continue

                key = (
                    "local_variable",
                    name,
                )

                if key in seen:
                    continue

                seen.add(key)

                project.add_variable(
                    VariableNode(
                        name=name,
                        path=str(path),
                        language=self.language,
                        constant=False,
                        line=line_number,
                        metadata={"ruby_kind": "local_variable"},
                    )
                )

    # ========================================================
    # DOCUMENTATION
    # ========================================================

    def _extract_documentation(
        self,
        source: str,
        path: Path,
        project: Project,
    ) -> None:
        """
        Extract Ruby documentation comments.
        """

        lines = source.splitlines()

        current: list[str] = []

        start_line: int | None = None

        for index, line in enumerate(
            lines,
            start=1,
        ):
            match = self._RUBYDOC_RE.match(line)

            if match:
                if start_line is None:
                    start_line = index

                current.append(match.group("text").strip())

                continue

            if current:
                text = "\n".join(current).strip()

                if text:
                    project.add_documentation(
                        DocumentationNode(
                            title=self._documentation_title(text),
                            path=str(path),
                            kind="ruby_comment",
                            headings=[self._documentation_title(text)],
                            metadata={
                                "line_start": start_line,
                                "line_end": index - 1,
                                "language": self.language,
                            },
                        )
                    )

                current = []
                start_line = None

        if current:
            text = "\n".join(current).strip()

            if text:
                project.add_documentation(
                    DocumentationNode(
                        title=self._documentation_title(text),
                        path=str(path),
                        kind="ruby_comment",
                        headings=[self._documentation_title(text)],
                        metadata={
                            "line_start": start_line,
                            "line_end": len(lines),
                            "language": self.language,
                        },
                    )
                )

    # ========================================================
    # HELPERS
    # ========================================================

    def _module_name(
        self,
        path: Path,
    ) -> str:
        """
        Convert a Ruby filename into a logical module name.
        """

        return path.stem

    def _class_bases(
        self,
        structure: dict[str, Any],
    ) -> list[str]:
        """
        Return class inheritance information.
        """

        superclass = structure.get("superclass")

        if not superclass:
            return []

        return [superclass.strip()]

    def _parse_parameters(
        self,
        params: str,
    ) -> list[str]:
        """
        Parse a Ruby parameter list conservatively.
        """

        if not params:
            return []

        value = params.strip()

        if value.startswith("(") and value.endswith(")"):
            value = value[1:-1]

        if not value.strip():
            return []

        result: list[str] = []

        current: list[str] = []

        depth = 0

        quote: str | None = None

        escaped = False

        for char in value:
            if escaped:
                current.append(char)
                escaped = False
                continue

            if char == "\\":
                current.append(char)
                escaped = True
                continue

            if quote:
                current.append(char)

                if char == quote:
                    quote = None

                continue

            if char in {
                "'",
                '"',
                "`",
            }:
                quote = char
                current.append(char)
                continue

            if char in "([{":
                depth += 1
                current.append(char)
                continue

            if char in ")]}":
                depth = max(
                    0,
                    depth - 1,
                )
                current.append(char)
                continue

            if char == "," and depth == 0:
                item = "".join(current).strip()

                if item:
                    result.append(item)

                current = []
                continue

            current.append(char)

        item = "".join(current).strip()

        if item:
            result.append(item)

        return result

    def _split_symbol_list(
        self,
        value: str,
    ) -> list[str]:
        """
        Split Ruby include/extend/attribute arguments.
        """

        result: list[str] = []

        for item in value.split(","):
            item = item.strip()

            if not item:
                continue

            item = item.lstrip(":")

            if (item.startswith('"') and item.endswith('"')) or (
                item.startswith("'") and item.endswith("'")
            ):
                item = item[1:-1]

            result.append(item)

        return result

    def _strip_constant_name(
        self,
        value: str,
    ) -> str:
        return value.split(
            "=",
            1,
        )[0].strip()

    def _documentation_before(
        self,
        lines: list[str],
        index: int,
    ) -> str | None:
        """
        Return contiguous documentation comments directly
        preceding a declaration.
        """

        docs: list[str] = []

        cursor = index - 1

        while cursor >= 0:
            line = lines[cursor].strip()

            if not line:
                if docs:
                    break

                cursor -= 1
                continue

            if line.startswith("#"):
                text = line[1:].strip()

                # Avoid treating normal comments as structured
                # documentation unless they actually contain text.
                if text:
                    docs.append(text)

                cursor -= 1
                continue

            break

        if not docs:
            return None

        docs.reverse()

        return "\n".join(docs).strip()

    def _documentation_title(
        self,
        text: str,
    ) -> str:
        """
        Generate a deterministic documentation title.
        """

        first_line = text.splitlines()[0].strip()

        if not first_line:
            return "Ruby Documentation"

        return first_line[:120]

    def _line_number_from_offset(
        self,
        text: str,
        offset: int,
    ) -> int:
        """
        Convert a character offset into a 1-based line number.
        """

        offset = max(
            0,
            min(
                offset,
                len(text),
            ),
        )

        return (
            text.count(
                "\n",
                0,
                offset,
            )
            + 1
        )

    def _line_number(
        self,
        source: str,
        offset: int,
    ) -> int:
        """
        Compatibility helper for offset-based callers.
        """

        return self._line_number_from_offset(
            source,
            offset,
        )

    def _is_end_line(
        self,
        stripped: str,
    ) -> bool:
        """
        Determine whether a line closes a Ruby nesting block.
        """

        return bool(
            re.match(
                r"^end\b",
                stripped,
            )
        )

    def _strip_ruby_comment(
        self,
        line: str,
    ) -> str:
        """
        Strip a Ruby # comment while attempting to preserve
        # characters inside quoted strings.
        """

        result: list[str] = []

        quote: str | None = None

        escaped = False

        for char in line:
            if escaped:
                result.append(char)
                escaped = False
                continue

            if char == "\\":
                result.append(char)
                escaped = True
                continue

            if quote:
                result.append(char)

                if char == quote:
                    quote = None

                continue

            if char in {
                "'",
                '"',
                "`",
            }:
                quote = char
                result.append(char)
                continue

            if char == "#":
                break

            result.append(char)

        return "".join(result)
