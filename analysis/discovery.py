"""
BARKLY DOCS
Project Discovery

Discovers source files in a project and sends each supported
file to the appropriate Barkly Docs language reader.
"""

from __future__ import annotations

import importlib
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from model.project import Project
from readers.base import LanguageReader, ReaderResult


_PROJECT_NODE_FIELDS = (
    "files",
    "modules",
    "components",
    "functions",
    "methods",
    "classes",
    "interfaces",
    "variables",
    "routes",
    "endpoints",
    "imports",
    "exports",
    "dependencies",
    "configurations",
    "tests",
    "documentation",
    "relationships",
)

_PROJECT_NODE_CLASSES = {
    "files": "FileNode",
    "modules": "ModuleNode",
    "components": "ComponentNode",
    "functions": "FunctionNode",
    "methods": "MethodNode",
    "classes": "ClassNode",
    "interfaces": "InterfaceNode",
    "variables": "VariableNode",
    "routes": "RouteNode",
    "endpoints": "EndpointNode",
    "imports": "ImportNode",
    "exports": "ExportNode",
    "dependencies": "DependencyNode",
    "configurations": "ConfigurationNode",
    "tests": "TestNode",
    "documentation": "DocumentationNode",
    "relationships": "RelationshipNode",
}

_PROJECT_ADDERS = {
    "files": "add_file",
    "modules": "add_module",
    "components": "add_component",
    "functions": "add_function",
    "methods": "add_method",
    "classes": "add_class",
    "interfaces": "add_interface",
    "variables": "add_variable",
    "routes": "add_route",
    "endpoints": "add_endpoint",
    "imports": "add_import",
    "exports": "add_export",
    "dependencies": "add_dependency",
    "configurations": "add_configuration",
    "tests": "add_test",
    "documentation": "add_documentation",
    "relationships": "add_relationship",
}


@dataclass(frozen=True)
class _WorkerTask:
    path: str
    project_name: str
    root: str
    reader_module: str
    reader_qualname: str


@dataclass
class _WorkerResult:
    path: str
    reader_name: str
    success: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    snapshot: dict[str, list[dict]] = field(default_factory=dict)


def _default_worker_count() -> int:
    return max(1, os.cpu_count() or 1)


def _instantiate_reader(reader_module: str, reader_qualname: str) -> LanguageReader:
    module = importlib.import_module(reader_module)
    target = module
    for part in reader_qualname.split("."):
        target = getattr(target, part)
    reader = target()
    if not isinstance(reader, LanguageReader):
        raise TypeError(f"Reader factory did not resolve to a LanguageReader: {reader_module}.{reader_qualname}")
    return reader


def _snapshot_project(project: Project) -> dict[str, list[dict]]:
    snapshot: dict[str, list[dict]] = {}
    for field_name in _PROJECT_NODE_FIELDS:
        items = list(getattr(project, field_name, []))
        snapshot[field_name] = [asdict(item) for item in items]
    return snapshot


def _deserialize_node(field_name: str, payload: dict):
    node_type_name = _PROJECT_NODE_CLASSES[field_name]
    module = importlib.import_module("model.project")
    node_type = getattr(module, node_type_name)
    return node_type(**payload)


def _read_worker_task(task: _WorkerTask) -> _WorkerResult:
    path = Path(task.path)
    try:
        reader = _instantiate_reader(task.reader_module, task.reader_qualname)
        project = Project(name=task.project_name, root=task.root)
        result = reader.read(path, project)
        return _WorkerResult(
            path=str(path),
            reader_name=reader.language,
            success=result.success,
            warnings=list(result.warnings),
            errors=list(result.errors),
            metadata=dict(result.metadata),
            snapshot=_snapshot_project(project),
        )
    except Exception as exc:
        return _WorkerResult(
            path=str(path),
            reader_name="unknown",
            success=False,
            warnings=[],
            errors=[f"{path}: worker failure: {exc}"],
            metadata={"path": str(path)},
            snapshot={},
        )


def _merge_worker_result(project: Project, result: _WorkerResult) -> ReaderResult:
    merged = ReaderResult(
        success=result.success,
        warnings=list(result.warnings),
        errors=list(result.errors),
        metadata=dict(result.metadata),
    )

    for field_name in _PROJECT_NODE_FIELDS:
        for payload in result.snapshot.get(field_name, []):
            node = _deserialize_node(field_name, payload)
            adder_name = _PROJECT_ADDERS[field_name]
            adder = getattr(project, adder_name)
            if field_name == "relationships":
                adder(node)
            else:
                adder(node)
    return merged


@dataclass
class DiscoveryResult:
    """
    Result of analyzing a project.
    """

    project: Project

    processed_files: list[Path] = field(default_factory=list)
    skipped_files: list[Path] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    reader_results: list[ReaderResult] = field(default_factory=list)


class ProjectDiscovery:
    """
    Discovers files and coordinates language readers.
    """

    DEFAULT_IGNORED_DIRECTORIES = {
        ".git",
        ".github",
        ".idea",
        ".vscode",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        "coverage",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    def __init__(
        self,
        readers: list[LanguageReader],
        ignored_directories: set[str] | None = None,
    ) -> None:
        self.readers = readers

        self.ignored_directories = (
            ignored_directories
            if ignored_directories is not None
            else set(self.DEFAULT_IGNORED_DIRECTORIES)
        )

    def analyze(
        self,
        root: Path,
        name: str | None = None,
        event_logger: object | None = None,
        progress_callback: callable | None = None,
        *,
        parallel: bool = False,
        workers: int | None = None,
    ) -> DiscoveryResult:
        """
        Discover and analyze a project.

        The optional event_logger and progress_callback let the CLI report
        real pipeline progress without changing the underlying analysis.
        The parallel flag enables process-based parsing for independent files.
        """

        root = root.resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Project path does not exist: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Project path is not a directory: {root}"
            )

        project = Project(
            name=name or root.name,
            root=str(root),
        )

        result = DiscoveryResult(
            project=project,
        )

        discovered_files = self._discover_files(root)
        total = len(discovered_files)

        if event_logger is not None:
            event_logger.stage_start(
                "discovery",
                discovered=total,
                root=str(root),
            )

        if parallel or (workers is not None and workers > 1):
            worker_count = max(1, workers or _default_worker_count())
            return self._analyze_parallel(
                root=root,
                project=project,
                discovered_files=discovered_files,
                total=total,
                event_logger=event_logger,
                progress_callback=progress_callback,
                worker_count=worker_count,
                result=result,
            )

        for index, path in enumerate(discovered_files, start=1):
            reader = self._find_reader(path)

            if reader is None:
                result.skipped_files.append(path)
                if progress_callback is not None:
                    progress_callback(
                        stage="discovery",
                        current=index,
                        total=total,
                        current_file=str(path),
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                        },
                    )
                if event_logger is not None:
                    event_logger.file_event(
                        path=path,
                        file_type="unknown",
                        reader_name="none",
                        status="skipped",
                        phase="discovery",
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                        },
                    )
                continue

            pre_counts = {
                "classes": len(project.classes),
                "functions": len(project.functions),
                "methods": len(project.methods),
                "relationships": len(project.relationships),
            }

            start_time = __import__("time").perf_counter()
            try:
                reader_result = reader.read(
                    path,
                    project,
                )

                result.reader_results.append(reader_result)

                duration_ms = int((__import__("time").perf_counter() - start_time) * 1000)

                if reader_result.success:
                    result.processed_files.append(path)
                    status = "complete"
                else:
                    result.errors.extend(reader_result.errors)
                    status = "failed" if reader_result.errors else "partial"

                result.warnings.extend(reader_result.warnings)

                if progress_callback is not None:
                    progress_callback(
                        stage="analysis",
                        current=index,
                        total=total,
                        current_file=str(path),
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                            "warnings": len(result.warnings),
                        },
                        reader=reader.language,
                    )

                post_counts = {
                    "classes": len(project.classes),
                    "functions": len(project.functions),
                    "methods": len(project.methods),
                    "relationships": len(project.relationships),
                }

                delta = {
                    key: post_counts[key] - pre_counts.get(key, 0)
                    for key in post_counts
                }

                per_file_counts = {
                    "classes": reader_result.metadata.get("classes")
                    if reader_result.metadata and "classes" in reader_result.metadata
                    else delta["classes"],
                    "functions": reader_result.metadata.get("functions")
                    if reader_result.metadata and "functions" in reader_result.metadata
                    else delta["functions"],
                    "methods": reader_result.metadata.get("methods")
                    if reader_result.metadata and "methods" in reader_result.metadata
                    else delta["methods"],
                    "relationships": reader_result.metadata.get("relationships")
                    if reader_result.metadata and "relationships" in reader_result.metadata
                    else delta["relationships"],
                }

                project_totals = project.summary()

                if event_logger is not None:
                    event_logger.file_event(
                        path=path,
                        file_type=path.suffix.lower(),
                        reader_name=reader.language,
                        status=status,
                        phase="analysis",
                        duration_ms=duration_ms,
                        counts={
                            "per_file": per_file_counts,
                            "project": project_totals,
                        },
                        message=(
                            "File analyzed successfully."
                            if status == "complete"
                            else "File analysis returned warnings or errors."
                        ),
                    )

            except Exception as exc:
                result.errors.append(
                    f"{path}: reader "
                    f"{reader.language} failed: {exc}"
                )
                if progress_callback is not None:
                    progress_callback(
                        stage="analysis",
                        current=index,
                        total=total,
                        current_file=str(path),
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                            "warnings": len(result.warnings),
                        },
                        reader=reader.language,
                    )
                if event_logger is not None:
                    event_logger.file_event(
                        path=path,
                        file_type=path.suffix.lower(),
                        reader_name=reader.language,
                        status="failed",
                        phase="analysis",
                        duration_ms=int((__import__("time").perf_counter() - start_time) * 1000),
                        error=str(exc),
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                        },
                    )

        if event_logger is not None:
            event_logger.stage_complete(
                "discovery",
                discovered=total,
                eligible=len(result.processed_files) + len(result.errors),
                processed=len(result.processed_files),
                skipped=len(result.skipped_files),
                failed=len(result.errors),
            )

        return result

    def _analyze_parallel(
        self,
        *,
        root: Path,
        project: Project,
        discovered_files: list[Path],
        total: int,
        event_logger: object | None,
        progress_callback: callable | None,
        worker_count: int,
        result: DiscoveryResult,
    ) -> DiscoveryResult:
        reader_specs = []
        for path in discovered_files:
            reader = self._find_reader(path)
            if reader is None:
                result.skipped_files.append(path)
                continue
            reader_specs.append(
                _WorkerTask(
                    path=str(path),
                    project_name=project.name,
                    root=str(root),
                    reader_module=reader.__class__.__module__,
                    reader_qualname=reader.__class__.__qualname__,
                )
            )

        worker_results: dict[str, _WorkerResult] = {}
        tasks = list(reader_specs)
        if tasks:
            chunksize = max(1, len(tasks) // (worker_count * 4) if worker_count > 0 else 1)
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                for entry in executor.map(_read_worker_task, tasks, chunksize=chunksize):
                    worker_results[entry.path] = entry

        for index, path in enumerate(discovered_files, start=1):
            reader = self._find_reader(path)
            if reader is None:
                if progress_callback is not None:
                    progress_callback(
                        stage="discovery",
                        current=index,
                        total=total,
                        current_file=str(path),
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                        },
                    )
                if event_logger is not None:
                    event_logger.file_event(
                        path=path,
                        file_type="unknown",
                        reader_name="none",
                        status="skipped",
                        phase="discovery",
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                        },
                    )
                continue

            worker_result = worker_results.get(str(path))
            if worker_result is None:
                msg = f"{path}: worker did not return a result."
                result.errors.append(msg)
                if progress_callback is not None:
                    progress_callback(
                        stage="analysis",
                        current=index,
                        total=total,
                        current_file=str(path),
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                            "warnings": len(result.warnings),
                        },
                        reader=reader.language,
                    )
                if event_logger is not None:
                    event_logger.file_event(
                        path=path,
                        file_type=path.suffix.lower(),
                        reader_name=reader.language,
                        status="failed",
                        phase="analysis",
                        duration_ms=0,
                        error=msg,
                        counts={
                            "processed": len(result.processed_files),
                            "skipped": len(result.skipped_files),
                            "failed": len(result.errors),
                        },
                    )
                continue

            pre_counts = {
                "classes": len(project.classes),
                "functions": len(project.functions),
                "methods": len(project.methods),
                "relationships": len(project.relationships),
            }
            start_time = __import__("time").perf_counter()
            reader_result = _merge_worker_result(project, worker_result)
            result.reader_results.append(reader_result)

            duration_ms = int((__import__("time").perf_counter() - start_time) * 1000)
            if reader_result.success:
                result.processed_files.append(path)
                status = "complete"
            else:
                result.errors.extend(reader_result.errors)
                status = "failed" if reader_result.errors else "partial"
            result.warnings.extend(reader_result.warnings)

            if progress_callback is not None:
                progress_callback(
                    stage="analysis",
                    current=index,
                    total=total,
                    current_file=str(path),
                    counts={
                        "processed": len(result.processed_files),
                        "skipped": len(result.skipped_files),
                        "failed": len(result.errors),
                        "warnings": len(result.warnings),
                    },
                    reader=reader.language,
                )

            post_counts = {
                "classes": len(project.classes),
                "functions": len(project.functions),
                "methods": len(project.methods),
                "relationships": len(project.relationships),
            }
            delta = {key: post_counts[key] - pre_counts.get(key, 0) for key in post_counts}
            per_file_counts = {
                "classes": reader_result.metadata.get("classes") if reader_result.metadata and "classes" in reader_result.metadata else delta["classes"],
                "functions": reader_result.metadata.get("functions") if reader_result.metadata and "functions" in reader_result.metadata else delta["functions"],
                "methods": reader_result.metadata.get("methods") if reader_result.metadata and "methods" in reader_result.metadata else delta["methods"],
                "relationships": reader_result.metadata.get("relationships") if reader_result.metadata and "relationships" in reader_result.metadata else delta["relationships"],
            }
            project_totals = project.summary()

            if event_logger is not None:
                event_logger.file_event(
                    path=path,
                    file_type=path.suffix.lower(),
                    reader_name=reader.language,
                    status=status,
                    phase="analysis",
                    duration_ms=duration_ms,
                    counts={
                        "per_file": per_file_counts,
                        "project": project_totals,
                    },
                    message=(
                        "File analyzed successfully." if status == "complete" else "File analysis returned warnings or errors."
                    ),
                )

        if event_logger is not None:
            event_logger.stage_complete(
                "discovery",
                discovered=total,
                eligible=len(result.processed_files) + len(result.errors),
                processed=len(result.processed_files),
                skipped=len(result.skipped_files),
                failed=len(result.errors),
            )

        return result

    def _discover_files(
        self,
        root: Path,
    ) -> list[Path]:
        """
        Recursively discover files while respecting
        ignored directories.
        """

        files: list[Path] = []

        for path in root.rglob("*"):

            if not path.is_file():
                continue

            if self._is_ignored(path, root):
                continue

            files.append(path)

        files.sort()

        return files

    def _is_ignored(
        self,
        path: Path,
        root: Path,
    ) -> bool:
        """
        Determine whether a path is inside an ignored directory.
        """

        try:
            relative = path.relative_to(root)
        except ValueError:
            return True

        return any(
            part in self.ignored_directories
            for part in relative.parts
        )

    def _find_reader(
        self,
        path: Path,
    ) -> LanguageReader | None:
        """
        Find the first reader capable of reading a file.
        """

        for reader in self.readers:
            if reader.can_read(path):
                return reader

        return None