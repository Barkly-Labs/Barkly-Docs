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


def decode_document_bytes(data: bytes) -> tuple[str, str]:
    """Decode repository documentation with a deterministic, non-lossy policy.

    BOMs are authoritative and are handled before UTF-8 detection so UTF-16/32
    source is never mistaken for Latin-1 mojibake.  UTF-8 is the normal path.
    Latin-1 is the final byte-preserving compatibility fallback; it never
    inserts replacement characters or guesses away source bytes.
    """
    bom_decoders = (
        (b"\xff\xfe\x00\x00", "utf-32-le", "utf-32-le-bom"),
        (b"\x00\x00\xfe\xff", "utf-32-be", "utf-32-be-bom"),
        (b"\xef\xbb\xbf", "utf-8-sig", "utf-8-sig"),
        (b"\xff\xfe", "utf-16", "utf-16-le-bom"),
        (b"\xfe\xff", "utf-16", "utf-16-be-bom"),
    )
    for bom, codec, label in bom_decoders:
        if data.startswith(bom):
            if codec.startswith("utf-32-"):
                return data[len(bom):].decode(codec), label
            return data.decode(codec), label
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1-fallback"

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
