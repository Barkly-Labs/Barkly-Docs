"""
BARKLY DOCS
Relationship System

Provides the base relationship engine used by Barkly Docs.

The relationship system is intentionally language-neutral.

Readers discover facts.
The relationship system turns those facts into normalized
relationships between project objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .project import EVIDENCE_STATUS, Project, RelationshipNode


# ============================================================
# RELATIONSHIP KINDS
# ============================================================

RELATIONSHIP_KINDS = {
    "imports",
    "exports",
    "calls",
    "inherits",
    "implements",
    "uses",
    "contains",
    "defines",
    "renders",
    "routes_to",
    "documents",
    "tests",
    "depends_on",
    "configures",
    "references",
}


# ============================================================
# RELATIONSHIP RESULT
# ============================================================

@dataclass
class RelationshipResult:
    """
    Result of building relationships for a project.
    """

    relationships: list[RelationshipNode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.relationships)


# ============================================================
# RELATIONSHIP ENGINE
# ============================================================

class RelationshipEngine:
    """
    Builds and manages relationships between project objects.

    The engine does not parse source code itself.

    Language readers and analysis systems provide the facts.
    This engine normalizes those facts into RelationshipNode
    objects attached to the Project.
    """

    def __init__(self, project: Project):
        self.project = project

        # Used to prevent duplicate relationships.
        self._seen: set[tuple[str, str, str, str | None]] = set()

        # Fast indexes.
        self._outgoing: dict[str, list[RelationshipNode]] = {}
        self._incoming: dict[str, list[RelationshipNode]] = {}

    # ========================================================
    # ADD
    # ========================================================

    def add(
        self,
        source: str,
        target: str,
        kind: str,
        *,
        source_file: str | None = None,
        metadata: dict | None = None,
        source_location: dict | None = None,
        evidence: str = "DETECTED",
    ) -> RelationshipNode | None:
        """
        Add a relationship to the project.

        Duplicate relationships are ignored.

        Returns the created RelationshipNode, or None if the
        relationship was invalid or already existed.
        """

        source = self._normalize(source)
        target = self._normalize(target)
        kind = self._normalize(kind)

        if not source:
            self.project.warnings.append(
                "Relationship rejected: empty source."
            )
            return None

        if not target:
            self.project.warnings.append(
                f"Relationship rejected: empty target for {source!r}."
            )
            return None

        if not kind:
            self.project.warnings.append(
                f"Relationship rejected: empty kind for {source!r}."
            )
            return None

        if kind not in RELATIONSHIP_KINDS:
            self.project.warnings.append(
                f"Relationship kind not in supported set for {source!r} -> {target!r}: {kind!r}."
            )

        node = RelationshipNode(
            source=source,
            target=target,
            kind=kind,
            source_file=source_file,
            evidence=evidence,
            source_location=dict(source_location) if source_location is not None else None,
            metadata=dict(metadata or {}),
        )

        return self.store(node)

    def store(self, node: RelationshipNode) -> RelationshipNode | None:
        """Normalize and store a relationship through the engine."""

        source = self._normalize(node.source)
        target = self._normalize(node.target)
        kind = self._normalize(node.kind)

        if not source:
            self.project.warnings.append(
                "Relationship rejected: empty source."
            )
            return None

        if not target:
            self.project.warnings.append(
                f"Relationship rejected: empty target for {source!r}."
            )
            return None

        if not kind:
            self.project.warnings.append(
                f"Relationship rejected: empty kind for {source!r}."
            )
            return None

        node.source = source
        node.target = target
        node.kind = kind
        node.evidence = node.evidence if node.evidence in EVIDENCE_STATUS else "UNKNOWN"

        if node.source_location is not None:
            node.source_location = dict(node.source_location)

        if node.metadata is None:
            node.metadata = {}

        key = (
            node.source,
            node.target,
            node.kind,
            node.source_file,
        )

        if key in self._seen:
            return None

        self._seen.add(key)
        self.project.relationships.append(node)
        self._outgoing.setdefault(node.source, []).append(node)
        self._incoming.setdefault(node.target, []).append(node)

        return node

    # ========================================================
    # BULK ADD
    # ========================================================

    def add_many(
        self,
        relationships: Iterable[RelationshipNode],
    ) -> int:
        """
        Add multiple relationships.

        Returns the number of relationships actually added.
        """

        added = 0

        for relationship in relationships:
            result = self.add(
                relationship.source,
                relationship.target,
                relationship.kind,
                source_file=relationship.source_file,
                metadata=relationship.metadata,
                source_location=relationship.source_location,
                evidence=relationship.evidence,
            )

            if result is not None:
                added += 1

        return added

    # ========================================================
    # QUERY
    # ========================================================

    def outgoing(
        self,
        source: str,
        *,
        kind: str | None = None,
    ) -> list[RelationshipNode]:
        """
        Return relationships originating from an object.
        """

        relationships = self._outgoing.get(
            self._normalize(source),
            [],
        )

        if kind is None:
            return list(relationships)

        return [
            relationship
            for relationship in relationships
            if relationship.kind == kind
        ]

    def incoming(
        self,
        target: str,
        *,
        kind: str | None = None,
    ) -> list[RelationshipNode]:
        """
        Return relationships pointing to an object.
        """

        relationships = self._incoming.get(
            self._normalize(target),
            [],
        )

        if kind is None:
            return list(relationships)

        return [
            relationship
            for relationship in relationships
            if relationship.kind == kind
        ]

    def between(
        self,
        source: str,
        target: str,
        *,
        kind: str | None = None,
    ) -> list[RelationshipNode]:
        """
        Return relationships between two objects.
        """

        source = self._normalize(source)
        target = self._normalize(target)

        results = [
            relationship
            for relationship in self._outgoing.get(source, [])
            if relationship.target == target
        ]

        if kind is not None:
            results = [
                relationship
                for relationship in results
                if relationship.kind == kind
            ]

        return results

    # ========================================================
    # OBJECT RELATIONSHIPS
    # ========================================================

    def related(
        self,
        object_id: str,
    ) -> list[RelationshipNode]:
        """
        Return both incoming and outgoing relationships.
        """

        object_id = self._normalize(object_id)

        results = []
        results.extend(self._outgoing.get(object_id, []))
        results.extend(self._incoming.get(object_id, []))

        return results

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(self) -> list[str]:
        """
        Validate the current relationship set.

        Returns warnings rather than raising exceptions.
        """

        warnings: list[str] = []

        for relationship in self.project.relationships:
            if not relationship.source:
                warnings.append(
                    "Relationship has no source."
                )

            if not relationship.target:
                warnings.append(
                    "Relationship has no target."
                )

            if not relationship.kind:
                warnings.append(
                    "Relationship has no kind."
                )

            if relationship.evidence not in EVIDENCE_STATUS:
                warnings.append(
                    f"Relationship evidence is invalid for {relationship.kind!r}: {relationship.evidence!r}."
                )

            if relationship.source_location is not None and not isinstance(
                relationship.source_location,
                dict,
            ):
                warnings.append(
                    "Relationship source_location must be a dict when present."
                )

        return warnings

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(self) -> dict[str, int]:
        """
        Return deterministic relationship counts by kind.
        """

        counts: dict[str, int] = {}

        for relationship in self.project.relationships:
            counts[relationship.kind] = (
                counts.get(relationship.kind, 0) + 1
            )

        return dict(sorted(counts.items()))

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize(value: str | None) -> str:
        """
        Normalize relationship identifiers.
        """

        if value is None:
            return ""

        return str(value).strip()


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def build_relationships(
    project: Project,
    relationships: Iterable[RelationshipNode],
) -> RelationshipResult:
    """
    Build relationships for a project.
    """

    engine = RelationshipEngine(project)
    project.relationship_engine = engine

    added = engine.add_many(relationships)

    warnings = engine.validate()

    return RelationshipResult(
        relationships=list(project.relationships),
        warnings=warnings,
    )


# ============================================================
# RELATIONSHIP HELPERS
# ============================================================

def relationship(
    source: str,
    target: str,
    kind: str,
    *,
    source_file: str | None = None,
    metadata: dict | None = None,
    source_location: dict | None = None,
    evidence: str = "DETECTED",
) -> RelationshipNode:
    """
    Convenience constructor for readers and analysis systems.
    """

    return RelationshipNode(
        source=source,
        target=target,
        kind=kind,
        source_file=source_file,
        evidence=evidence,
        source_location=dict(source_location) if source_location is not None else None,
        metadata=dict(metadata or {}),
    )