from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentBlock:
    kind: str
    text: str = ""
    level: int | None = None
    items: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Document:
    title: str
    document_type: str = "technical"
    version: str | None = None
    source: str | None = None
    blocks: list[DocumentBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "document_type": self.document_type,
            "version": self.version,
            "source": self.source,
            "metadata": self.metadata,
            "blocks": [
                {
                    "kind": b.kind,
                    "text": b.text,
                    "level": b.level,
                    "items": b.items,
                    "rows": b.rows,
                }
                for b in self.blocks
            ],
        }
