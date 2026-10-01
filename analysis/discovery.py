"""
BARKLY DOCS
Project Discovery

Discovers source files in a project and sends each supported
file to the appropriate Barkly Docs language reader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from model.project import Project
from readers.base import LanguageReader, ReaderResult


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
    ) -> DiscoveryResult:
        """
        Discover and analyze a project.

        The optional event_logger and progress_callback let the CLI report
        real pipeline progress without changing the underlying analysis.
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

            # Snapshot project counts before the reader runs so file-level
            # counts can be computed reliably without mixing in other files.
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

                result.reader_results.append(
                    reader_result
                )

                duration_ms = int((__import__("time").perf_counter() - start_time) * 1000)

                if reader_result.success:
                    result.processed_files.append(path)
                    status = "complete"
                else:
                    result.errors.extend(
                        reader_result.errors
                    )
                    status = "failed" if reader_result.errors else "partial"

                result.warnings.extend(
                    reader_result.warnings
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

                # Compute per-file counts. Prefer explicit metadata supplied
                # by a reader (readers MAY provide file-level counts in
                # reader_result.metadata). Fall back to the delta between
                # project counts before/after the read. Also include the
                # project-level summary separately so logs can show both.
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
                    # Emit explicit per-file counts and the project-level
                    # aggregates together. The file=... field indicates the
                    # per-file scope; project totals are labeled as such so
                    # consumers don't misinterpret them.
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