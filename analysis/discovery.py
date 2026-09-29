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
    ) -> DiscoveryResult:
        """
        Discover and analyze a project.
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

        for path in self._discover_files(root):

            reader = self._find_reader(path)

            if reader is None:
                result.skipped_files.append(path)
                continue

            try:
                reader_result = reader.read(
                    path,
                    project,
                )

                result.reader_results.append(
                    reader_result
                )

                if reader_result.success:
                    result.processed_files.append(path)
                else:
                    result.errors.extend(
                        reader_result.errors
                    )

                result.warnings.extend(
                    reader_result.warnings
                )

            except Exception as exc:
                result.errors.append(
                    f"{path}: reader "
                    f"{reader.language} failed: {exc}"
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