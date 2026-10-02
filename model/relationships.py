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
    Normalize and store relationships discovered by Barkly readers/analyzers.

    Duplicate call/reference sites are collapsed into one logical edge while
    their individual source locations remain available in metadata.
    """

    _KIND_ALIASES = {
        "import": "imports", "export": "exports", "call": "calls",
        "inherit": "inherits", "extends": "inherits",
        "implement": "implements", "use": "uses", "contain": "contains",
        "define": "defines", "render": "renders", "route": "routes_to",
        "routes": "routes_to", "route_to": "routes_to",
        "document": "documents", "test": "tests",
        "depend_on": "depends_on", "depends": "depends_on",
        "configure": "configures", "reference": "references",
    }

    def __init__(self, project: Project):
        self.project = project
        self._seen: dict[tuple[str, str, str, str | None], RelationshipNode] = {}
        self._outgoing: dict[str, list[RelationshipNode]] = {}
        self._incoming: dict[str, list[RelationshipNode]] = {}

        # Rebuild existing relationships through the same normalization path.
        existing = list(project.relationships)
        project.relationships.clear()
        for node in existing:
            self.store(node)

    def evidence_summary(self) -> dict[str, int]:
        counts = {label: 0 for label in EVIDENCE_STATUS}
        for relationship in self.project.relationships:
            key = self._normalize_evidence(relationship.evidence)
            counts[key] = counts.get(key, 0) + 1
        return counts

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
        return self.store(
            RelationshipNode(
                source=source,
                target=target,
                kind=kind,
                source_file=source_file,
                evidence=evidence,
                source_location=(
                    dict(source_location) if source_location is not None else None
                ),
                metadata=dict(metadata or {}),
            )
        )

    def store(self, node: RelationshipNode) -> RelationshipNode | None:
        source = self._normalize_identifier(node.source)
        target = self._normalize_identifier(node.target)
        kind = self._normalize_kind(node.kind)
        source_file = self._normalize_optional(node.source_file)

        if not source:
            self.project.warnings.append("Relationship rejected: empty source.")
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
                f"Relationship rejected: unsupported kind for "
                f"{source!r} -> {target!r}: {kind!r}."
            )
            return None

        node.source = source
        node.target = target
        node.kind = kind
        node.source_file = source_file
        node.evidence = self._normalize_evidence(node.evidence)
        node.source_location = self._normalize_location(node.source_location)
        node.metadata = dict(node.metadata or {})

        # Location is deliberately NOT part of the logical identity.
        key = (source, target, kind, source_file)
        existing = self._seen.get(key)
        if existing is not None:
            self._merge_duplicate(existing, node)
            return None

        self._record_occurrence(node, node.source_location)
        self._seen[key] = node
        self.project.relationships.append(node)
        self._outgoing.setdefault(source, []).append(node)
        self._incoming.setdefault(target, []).append(node)
        return node

    def _merge_duplicate(
        self,
        existing: RelationshipNode,
        incoming: RelationshipNode,
    ) -> None:
        self._record_occurrence(existing, incoming.source_location)

        for key, value in incoming.metadata.items():
            if key == "occurrences":
                continue
            if key not in existing.metadata:
                existing.metadata[key] = value
            elif existing.metadata[key] != value:
                variants = existing.metadata.setdefault("metadata_variants", {})
                values = variants.setdefault(key, [])
                for candidate in (existing.metadata[key], value):
                    if candidate not in values:
                        values.append(candidate)

        rank = {"UNKNOWN": 0, "INFERRED": 1, "DETECTED": 2, "DECLARED": 3}
        if rank[incoming.evidence] > rank[existing.evidence]:
            existing.evidence = incoming.evidence

        if existing.source_location is None and incoming.source_location is not None:
            existing.source_location = dict(incoming.source_location)

    @staticmethod
    def _record_occurrence(node: RelationshipNode, location: dict | None) -> None:
        if location is None:
            return
        occurrences = node.metadata.setdefault("occurrences", [])
        occurrence = {str(key): value for key, value in location.items()}
        if occurrence not in occurrences:
            occurrences.append(occurrence)

    def add_many(self, relationships: Iterable[RelationshipNode]) -> int:
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

    def outgoing(
        self, source: str, *, kind: str | None = None
    ) -> list[RelationshipNode]:
        relationships = self._outgoing.get(self._normalize_identifier(source), [])
        if kind is None:
            return list(relationships)
        normalized_kind = self._normalize_kind(kind)
        return [r for r in relationships if r.kind == normalized_kind]

    def incoming(
        self, target: str, *, kind: str | None = None
    ) -> list[RelationshipNode]:
        relationships = self._incoming.get(self._normalize_identifier(target), [])
        if kind is None:
            return list(relationships)
        normalized_kind = self._normalize_kind(kind)
        return [r for r in relationships if r.kind == normalized_kind]

    def between(
        self,
        source: str,
        target: str,
        *,
        kind: str | None = None,
    ) -> list[RelationshipNode]:
        source = self._normalize_identifier(source)
        target = self._normalize_identifier(target)
        results = [
            relationship
            for relationship in self._outgoing.get(source, [])
            if relationship.target == target
        ]
        if kind is not None:
            normalized_kind = self._normalize_kind(kind)
            results = [r for r in results if r.kind == normalized_kind]
        return results

    def related(self, object_id: str) -> list[RelationshipNode]:
        object_id = self._normalize_identifier(object_id)
        return (
            list(self._outgoing.get(object_id, []))
            + list(self._incoming.get(object_id, []))
        )

    def validate(self) -> list[str]:
        warnings: list[str] = []
        for relationship in self.project.relationships:
            if not relationship.source:
                warnings.append("Relationship has no source.")
            if not relationship.target:
                warnings.append("Relationship has no target.")
            if relationship.kind not in RELATIONSHIP_KINDS:
                warnings.append(
                    f"Unsupported relationship kind: {relationship.kind!r}."
                )
            if relationship.evidence not in EVIDENCE_STATUS:
                warnings.append(
                    f"Relationship evidence is invalid for "
                    f"{relationship.kind!r}: {relationship.evidence!r}."
                )
            if relationship.source_location is not None and not isinstance(
                relationship.source_location, dict
            ):
                warnings.append(
                    "Relationship source_location must be a dict when present."
                )
        return warnings

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for relationship in self.project.relationships:
            counts[relationship.kind] = counts.get(relationship.kind, 0) + 1
        return dict(sorted(counts.items()))

    @classmethod
    def _normalize_kind(cls, value: str | None) -> str:
        if value is None:
            return ""
        kind = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        return cls._KIND_ALIASES.get(kind, kind)

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        if value is None:
            return ""
        return " ".join(str(value).strip().split())

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @staticmethod
    def _normalize_location(value: dict | None) -> dict | None:
        if not isinstance(value, dict):
            return None
        normalized = {
            str(key): item
            for key, item in value.items()
            if item is not None and str(item).strip() != ""
        }
        return normalized or None

    @staticmethod
    def _normalize_evidence(value: str | None) -> str:
        evidence = str(value or "UNKNOWN").strip().upper()
        return evidence if evidence in EVIDENCE_STATUS else "UNKNOWN"

    # Keep compatibility with existing callers/tests.
    _normalize = _normalize_identifier

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