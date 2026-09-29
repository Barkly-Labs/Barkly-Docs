"""
BARKLY DOCS
Base Reader System

Defines the common interface used by every Barkly Docs reader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from model.project import Project


# ============================================================
# READER RESULT
# ============================================================

@dataclass
class ReaderResult:
    """
    Result returned by a language reader.
    """

    success: bool

    project: Project | None = None

    warnings: list[str] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)


# ============================================================
# LANGUAGE READER
# ============================================================

class LanguageReader(ABC):
    """
    Base interface for all Barkly Docs language readers.

    A reader is responsible for statically analyzing source
    files and translating what it finds into the Barkly
    Project Model.
    """

    # Human-readable language name.
    language: str = ""

    # File extensions handled by this reader.
    extensions: tuple[str, ...] = ()

    # Reader version.
    version: str = "0.1.0"

    # --------------------------------------------------------
    # DETECTION
    # --------------------------------------------------------

    def can_read(self, path: Path) -> bool:
        """
        Return True when this reader can analyze the file.
        """

        return path.suffix.lower() in self.extensions

    # --------------------------------------------------------
    # READ
    # --------------------------------------------------------

    @abstractmethod
    def read(
        self,
        path: Path,
        project: Project,
    ) -> ReaderResult:
        """
        Analyze one source file and add its structure to
        the supplied Project.

        Readers MUST NOT execute the target project's code.
        """
        raise NotImplementedError

    # --------------------------------------------------------
    # SAFE READ
    # --------------------------------------------------------

    def read_text(self, path: Path) -> str:
        """
        Read source text without executing it.
        """

        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    def info(self) -> dict:
        """
        Return information about this reader.
        """

        return {
            "language": self.language,
            "extensions": list(self.extensions),
            "version": self.version,
        }