from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Hashable

from model.project import Project


EVIDENCE_LEVELS = ("DECLARED", "DETECTED", "INFERRED", "UNKNOWN")
NODE_KIND_ORDER = (
    "file",
    "module",
    "class",
    "interface",
    "function",
    "method",
    "endpoint",
    "route",
    "variable",
    "component",
)

# Keep graph generation bounded so a burst of browser requests cannot create an
# unbounded number of CPU-heavy jobs. The web server can own/close this executor
# during application shutdown if it uses the async helper below.
_GRAPH_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="barkly-graph",
)

# Small process-local LRU cache. Caching is opt-in through an explicit cache_key
# so callers can tie cache validity to a scan/revision ID instead of relying on
# fragile guesses about whether a mutable Project has changed.
_GRAPH_CACHE_MAX_ENTRIES = 8
_GRAPH_CACHE: OrderedDict[tuple[str, str, Hashable, str, int | None, int | None], dict[str, Any]] = OrderedDict()
_GRAPH_CACHE_LOCK = RLock()


@dataclass
class GraphNode:
    id: str
    label: str
    kind: str
    qualified_name: str | None = None
    path: str | None = None
    source_file: str | None = None
    line: int | None = None
    evidence: str = "DECLARED"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    kind: str
    label: str
    source_file: str | None = None
    source_location: dict[str, Any] | None = None
    evidence: str = "DETECTED"
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationGraph:
    project: Project
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    view: str = "project_overview"
    max_nodes: int | None = 400
    max_edges: int | None = 400
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )
    # These sets make duplicate checks O(1) on average rather than scanning
    # the complete node/edge list for every insertion.
    _node_ids: set[str] = field(default_factory=set, repr=False)
    _edge_ids: set[str] = field(default_factory=set, repr=False)

    def add_node(self, node: GraphNode) -> None:
        if node.id in self._node_ids:
            return
        self._node_ids.add(node.id)
        self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.id in self._edge_ids:
            return
        self._edge_ids.add(edge.id)
        self.edges.append(edge)

    def summary(self) -> dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "unresolved": len(self.unresolved),
            "warnings": len(self.warnings),
        }

    def as_dict(self) -> dict[str, Any]:
        # Explicit serialization intentionally excludes the private ID sets.
        return {
            "project": self.project.name,
            "root": self.project.root,
            "view": self.view,
            "generated_at": self.generated_at,
            "max_nodes": self.max_nodes,
            "max_edges": self.max_edges,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "unresolved": list(self.unresolved),
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)


def _normalize_identifier(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip().replace("\\", "/")
    if not cleaned:
        return ""
    return cleaned


def _display_name(value: str | None) -> str:
    if value is None:
        return "unknown"
    cleaned = value.strip().replace("\\", "/")
    if not cleaned:
        return "unknown"
    return cleaned.rsplit("/", 1)[-1] if "/" in cleaned else cleaned


def _build_qualified_name(
    project: Project,
    *,
    value: str | None,
    path: str | None = None,
    kind: str = "symbol",
) -> str:
    candidate = _normalize_identifier(value)
    if not candidate:
        return ""
    if kind == "file":
        return f"file:{candidate}"
    if kind == "module":
        return f"module:{candidate}"
    if kind == "class":
        return candidate if "." in candidate or candidate.startswith("file:") else candidate
    if kind == "method" and "." in candidate:
        return candidate
    if path:
        normalized_path = str(Path(path)).replace("\\", "/")
        if candidate == normalized_path.rsplit("/", 1)[-1]:
            return f"file:{normalized_path}"
    return candidate


def _relationship_explanation(
    kind: str, detail: dict[str, Any] | None = None
) -> str:
    detail = detail or {}
    if kind == "imports":
        return detail.get(
            "message",
            "Import statement declares a dependency on another file or module.",
        )
    if kind == "contains":
        return detail.get(
            "message",
            "This node owns or defines the target symbol in the same file.",
        )
    if kind == "calls":
        return detail.get(
            "message",
            "A static call expression directly invokes the target symbol.",
        )
    if kind == "inherits":
        return detail.get(
            "message",
            "The class explicitly inherits from the target superclass.",
        )
    if kind == "implements":
        return detail.get(
            "message",
            "The class explicitly implements the target interface or contract.",
        )
    if kind == "references":
        return detail.get(
            "message",
            "The symbol references another symbol without an explicit call or inheritance link.",
        )
    if kind == "routes_to":
        return detail.get(
            "message",
            "An endpoint or route resolves through this handler target.",
        )
    return detail.get(
        "message",
        "Static source evidence captured by the project analysis pipeline.",
    )


def _match_known_symbol(
    project: Project,
    name: str | None,
    *,
    path: str | None = None,
) -> str | None:
    """Compatibility resolver for callers that do not have a symbol index."""
    if not name:
        return None
    normalized = _normalize_identifier(name)
    if not normalized:
        return None

    for module in project.modules:
        if module.name == normalized or module.path == normalized:
            return f"module:{module.name}"
    for file in project.files:
        if file.path == normalized:
            return f"file:{file.path}"
    for class_node in project.classes:
        if class_node.name == normalized:
            return (
                f"{class_node.name}@{class_node.path}"
                if class_node.path
                else class_node.name
            )
        if class_node.path == normalized:
            return (
                f"{class_node.name}@{class_node.path}"
                if class_node.path
                else class_node.name
            )
    for function in project.functions:
        if function.name == normalized:
            return str(function.metadata.get("qualified_name") or function.name)
        if function.metadata.get("qualified_name") == normalized:
            return str(function.metadata.get("qualified_name"))
    for method in project.methods:
        method_id = (
            str(method.metadata.get("qualified_name"))
            if method.metadata.get("qualified_name")
            else (
                f"{method.class_name}.{method.name}"
                if method.class_name
                else method.name
            )
        )
        if method.name == normalized or method_id == normalized:
            return method_id
    for endpoint in project.endpoints:
        if endpoint.path == normalized or endpoint.handler == normalized:
            return endpoint.handler or endpoint.path
    if path:
        file_name = str(Path(path)).replace("\\", "/").rsplit("/", 1)[-1]
        if file_name == normalized:
            return f"file:{str(Path(path)).replace('\\', '/')}"
    return None


class _SymbolIndex:
    """Fast, path-aware symbol resolver built once per graph generation.

    Exact identifiers are preferred. Name-only identifiers preserve the
    original resolver's category precedence. When names are duplicated, the
    first match in the project's existing collection order is retained, while
    path-qualified IDs are also indexed for unambiguous lookups.
    """

    def __init__(self, project: Project) -> None:
        self.exact: dict[str, str] = {}
        self.by_name: dict[str, str] = {}
        self.file_ids: set[str] = set()

        def add_exact(key: str | None, value: str) -> None:
            if key:
                self.exact.setdefault(_normalize_identifier(key), value)

        def add_name(key: str | None, value: str) -> None:
            if key:
                self.by_name.setdefault(_normalize_identifier(key), value)

        # Match the original category precedence: modules, files, classes,
        # functions, methods, then endpoints.
        for module in project.modules:
            module_id = f"module:{module.name}"
            add_exact(module.name, module_id)
            add_exact(module.path, module_id)
            add_name(module.name, module_id)
            add_name(module.path, module_id)

        for file in project.files:
            file_id = f"file:{file.path}"
            self.file_ids.add(file_id)
            add_exact(file.path, file_id)
            add_name(file.path, file_id)

        for cls in project.classes:
            class_id = f"{cls.name}@{cls.path}" if cls.path else cls.name
            add_exact(cls.name, class_id)
            add_exact(cls.path, class_id)
            add_name(cls.name, class_id)
            add_name(cls.path, class_id)

        for function in project.functions:
            qualified = str(function.metadata.get("qualified_name") or function.name)
            add_exact(function.name, qualified)
            add_exact(qualified, qualified)
            add_name(function.name, qualified)
            add_name(qualified, qualified)

        for method in project.methods:
            qualified = str(
                method.metadata.get("qualified_name")
                or (
                    f"{method.class_name}.{method.name}"
                    if method.class_name
                    else method.name
                )
            )
            add_exact(qualified, qualified)
            add_exact(method.name, qualified)
            add_name(qualified, qualified)
            add_name(method.name, qualified)

        for endpoint in project.endpoints:
            endpoint_id = endpoint.handler or endpoint.path
            add_exact(endpoint.path, endpoint_id)
            add_exact(endpoint.handler, endpoint_id)
            add_name(endpoint.path, endpoint_id)
            add_name(endpoint.handler, endpoint_id)

    def resolve(self, name: str | None, *, path: str | None = None) -> str | None:
        if not name:
            return None
        normalized = _normalize_identifier(name)
        if not normalized:
            return None

        # Prefer an exact, unambiguous identifier.
        if normalized in self.exact:
            return self.exact[normalized]

        # A path-local file name can be resolved to its file node.
        if path:
            normalized_path = str(Path(path)).replace("\\", "/")
            file_name = normalized_path.rsplit("/", 1)[-1]
            if file_name == normalized:
                file_id = f"file:{normalized_path}"
                if file_id in self.file_ids:
                    return file_id

        return self.by_name.get(normalized)


def _record_unresolved(
    edges: list[GraphEdge],
    known_identifiers: set[str],
    project: Project,
    *,
    source_file: str | None = None,
) -> list[dict[str, Any]]:
    """Return relationships whose source or target is absent from the graph.

    `source_file` remains accepted for compatibility with existing callers.
    """
    del project, source_file  # retained in the signature for compatibility
    unresolved: list[dict[str, Any]] = []
    unresolved_kinds = {
        "calls",
        "inherits",
        "implements",
        "references",
        "routes_to",
        "imports",
    }
    for edge in edges:
        if edge.source in known_identifiers and edge.target in known_identifiers:
            continue
        if edge.kind in unresolved_kinds:
            unresolved.append(
                {
                    "source": edge.source,
                    "target": edge.target,
                    "kind": edge.kind,
                    "source_file": edge.source_file,
                    "evidence": edge.evidence,
                    "reason": "target symbol not found in the current scan",
                    "explanation": edge.explanation,
                }
            )
    return unresolved


def _sort_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
    order = {kind: index for index, kind in enumerate(NODE_KIND_ORDER)}
    return sorted(
        nodes,
        key=lambda item: (order.get(item.kind, 999), item.label.lower(), item.id.lower()),
    )


def build_relation_graph(
    project: Project,
    *,
    view: str = "project_overview",
    max_nodes: int | None = 400,
    max_edges: int | None = 400,
) -> RelationGraph:
    """Build a relationship graph using indexed lookups and constant-time dedupe."""
    graph = RelationGraph(
        project=project,
        view=view,
        max_nodes=max_nodes,
        max_edges=max_edges,
    )
    symbol_index = _SymbolIndex(project)
    known_identifiers: set[str] = set()

    for file in project.files:
        file_id = f"file:{file.path}"
        known_identifiers.add(file_id)
        graph.add_node(
            GraphNode(
                id=file_id,
                label=file.name,
                kind="file",
                qualified_name=file_id,
                path=file.path,
                source_file=file.path,
                line=None,
                evidence="DECLARED",
                metadata={"language": file.language or "unknown"},
            )
        )

    for module in project.modules:
        module_id = f"module:{module.name}"
        known_identifiers.add(module_id)
        graph.add_node(
            GraphNode(
                id=module_id,
                label=module.name,
                kind="module",
                qualified_name=module.name,
                path=module.path,
                source_file=module.path,
                evidence="DECLARED",
                metadata={"module_path": module.path},
            )
        )
        if module.path:
            graph.add_edge(
                GraphEdge(
                    id=f"{module_id}->file:{module.path}",
                    source=module_id,
                    target=f"file:{module.path}",
                    kind="contains",
                    label="contains",
                    source_file=module.path,
                    evidence="DECLARED",
                    explanation="The module is defined in this source file.",
                )
            )

    class_ids_by_name: dict[str, list[str]] = {}
    for class_node in project.classes:
        class_id = (
            f"{class_node.name}@{class_node.path}"
            if class_node.path
            else class_node.name
        )
        class_ids_by_name.setdefault(class_node.name, []).append(class_id)
        known_identifiers.add(class_id)
        graph.add_node(
            GraphNode(
                id=class_id,
                label=class_node.name,
                kind="class",
                qualified_name=class_node.name,
                path=class_node.path,
                source_file=class_node.path,
                line=class_node.line_start,
                evidence="DECLARED",
                metadata={"bases": list(class_node.bases)},
            )
        )
        if class_node.path:
            graph.add_edge(
                GraphEdge(
                    id=f"{class_id}->file:{class_node.path}",
                    source=class_id,
                    target=f"file:{class_node.path}",
                    kind="contains",
                    label="contains",
                    source_file=class_node.path,
                    evidence="DECLARED",
                    explanation="The class is defined in this file.",
                )
            )
        for method_name in class_node.methods:
            if method_name:
                method_id = f"{class_node.name}.{method_name}"
                known_identifiers.add(method_id)
                graph.add_node(
                    GraphNode(
                        id=method_id,
                        label=method_name,
                        kind="method",
                        qualified_name=method_id,
                        path=class_node.path,
                        source_file=class_node.path,
                        evidence="DECLARED",
                    )
                )
                graph.add_edge(
                    GraphEdge(
                        id=f"{class_id}->{method_id}",
                        source=class_id,
                        target=method_id,
                        kind="contains",
                        label="contains",
                        source_file=class_node.path,
                        evidence="DECLARED",
                        explanation="The class contains this method declaration.",
                    )
                )
        for base in class_node.bases:
            base_name = _normalize_identifier(base)
            if not base_name:
                continue
            graph.add_edge(
                GraphEdge(
                    id=f"{class_id}->{base_name}",
                    source=class_id,
                    target=base_name,
                    kind="inherits",
                    label="inherits",
                    source_file=class_node.path,
                    evidence="DECLARED",
                    explanation="The class explicitly inherits from this base class.",
                )
            )

    for interface in project.interfaces:
        interface_id = (
            f"{interface.name}@{interface.path}"
            if interface.path
            else interface.name
        )
        known_identifiers.add(interface_id)
        graph.add_node(
            GraphNode(
                id=interface_id,
                label=interface.name,
                kind="interface",
                qualified_name=interface.name,
                path=interface.path,
                source_file=interface.path,
                evidence="DECLARED",
            )
        )
        if interface.path:
            graph.add_edge(
                GraphEdge(
                    id=f"{interface_id}->file:{interface.path}",
                    source=interface_id,
                    target=f"file:{interface.path}",
                    kind="contains",
                    label="contains",
                    source_file=interface.path,
                    evidence="DECLARED",
                    explanation="The interface is declared in this file.",
                )
            )

    for function in project.functions:
        function_id = str(
            function.metadata.get("qualified_name") or function.name
        )
        known_identifiers.add(function_id)
        graph.add_node(
            GraphNode(
                id=function_id,
                label=function.name,
                kind="function",
                qualified_name=function_id,
                path=function.path,
                source_file=function.path,
                line=function.line_start,
                evidence="DECLARED",
            )
        )
        if function.path:
            graph.add_edge(
                GraphEdge(
                    id=f"{function_id}->file:{function.path}",
                    source=function_id,
                    target=f"file:{function.path}",
                    kind="contains",
                    label="contains",
                    source_file=function.path,
                    evidence="DECLARED",
                    explanation="The function is defined in this file.",
                )
            )

    for method in project.methods:
        method_id = (
            str(method.metadata.get("qualified_name"))
            if method.metadata.get("qualified_name")
            else (
                f"{method.class_name}.{method.name}"
                if method.class_name
                else method.name
            )
        )
        known_identifiers.add(method_id)
        graph.add_node(
            GraphNode(
                id=method_id,
                label=method.name,
                kind="method",
                qualified_name=method_id,
                path=method.path,
                source_file=method.path,
                line=method.line_start,
                evidence="DECLARED",
            )
        )
        if method.class_name:
            candidates = class_ids_by_name.get(method.class_name, [])
            class_id = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.endswith(f"@{method.path}")
                ),
                candidates[0] if candidates else method.class_name,
            )
            graph.add_edge(
                GraphEdge(
                    id=f"{class_id}->{method_id}",
                    source=class_id,
                    target=method_id,
                    kind="contains",
                    label="contains",
                    source_file=method.path,
                    evidence="DECLARED",
                    explanation="This method belongs to the class definition.",
                )
            )

    for endpoint in project.endpoints:
        endpoint_id = endpoint.handler or endpoint.path
        known_identifiers.add(endpoint_id)
        graph.add_node(
            GraphNode(
                id=endpoint_id,
                label=endpoint.handler or endpoint.path,
                kind="endpoint",
                qualified_name=endpoint.handler or endpoint.path,
                path=endpoint.source_file,
                source_file=endpoint.source_file,
                evidence="DECLARED",
                metadata={"method": endpoint.method, "path": endpoint.path},
            )
        )
        if endpoint.handler:
            graph.add_edge(
                GraphEdge(
                    id=f"{endpoint.path}->{endpoint.handler}",
                    source=endpoint.path,
                    target=endpoint.handler,
                    kind="routes_to",
                    label="routes_to",
                    source_file=endpoint.source_file,
                    evidence="DETECTED",
                    explanation="The endpoint route resolves to the declared handler symbol.",
                )
            )

    for import_node in project.imports:
        source_id = (
            symbol_index.resolve(import_node.source_file)
            or import_node.source_file
        )
        target_id = (
            symbol_index.resolve(import_node.target)
            or import_node.target
        )
        graph.add_edge(
            GraphEdge(
                id=f"{source_id}->{target_id}",
                source=source_id,
                target=target_id,
                kind="imports",
                label="imports",
                source_file=import_node.source_file,
                source_location={"line": import_node.metadata.get("line")},
                evidence="DECLARED",
                explanation="The source file imports this module or symbol.",
                metadata={
                    "names": list(import_node.names),
                    "alias": import_node.alias,
                    "language": import_node.language,
                },
            )
        )

    for relationship in project.relationships:
        source_id = (
            symbol_index.resolve(
                relationship.source, path=relationship.source_file
            )
            or relationship.source
        )
        target_id = (
            symbol_index.resolve(
                relationship.target, path=relationship.source_file
            )
            or relationship.target
        )
        kind = relationship.kind
        edge = GraphEdge(
            id=(
                f"{source_id}->{target_id}:{kind}:"
                f"{relationship.source_file or 'unknown'}:"
                f"{relationship.source_location.get('line') if relationship.source_location else ''}"
            ),
            source=source_id,
            target=target_id,
            kind=kind,
            label=kind,
            source_file=relationship.source_file,
            source_location=(
                dict(relationship.source_location)
                if relationship.source_location
                else None
            ),
            evidence=(
                relationship.evidence
                if relationship.evidence in EVIDENCE_LEVELS
                else "UNKNOWN"
            ),
            explanation=_relationship_explanation(
                kind,
                {
                    "line": (
                        relationship.source_location.get("line")
                        if relationship.source_location
                        else None
                    ),
                    "source": relationship.source,
                    "target": relationship.target,
                    "message": (
                        relationship.metadata.get("reason")
                        or relationship.metadata.get("explanation")
                    ),
                },
            ),
            metadata=dict(relationship.metadata),
        )
        graph.add_edge(edge)

    graph.nodes = _sort_nodes(graph.nodes)
    graph.edges = sorted(
        graph.edges,
        key=lambda edge: (
            edge.kind,
            edge.source,
            edge.target,
            edge.source_file or "",
        ),
    )

    # Compute unresolved relationships once, after the final displayed graph
    # has been limited. This preserves the original final-result behavior.
    if graph.max_nodes is not None and len(graph.nodes) > graph.max_nodes:
        graph.warnings.append(
            f"Relation graph was limited to the first {graph.max_nodes} nodes "
            "to keep the view responsive."
        )
        graph.nodes = graph.nodes[: graph.max_nodes]

    if graph.max_edges is not None and len(graph.edges) > graph.max_edges:
        graph.warnings.append(
            f"Relation graph was limited to the first {graph.max_edges} edges "
            "to keep the view responsive."
        )
        graph.edges = graph.edges[: graph.max_edges]

    displayed_ids = {node.id for node in graph.nodes}
    # Edges pointing at nodes omitted by the node limit should be considered
    # unresolved in this displayed view, as the renderer cannot draw them.
    graph.unresolved = _record_unresolved(
        graph.edges, displayed_ids, project
    )
    project.metadata["relation_graph"] = graph.as_dict()
    project.metadata["relation_graph_unresolved"] = list(graph.unresolved)
    return graph


def _graph_from_snapshot(project: Project, snapshot: dict[str, Any]) -> RelationGraph:
    """Create a fresh graph object from a cached, JSON-shaped snapshot."""
    graph = RelationGraph(
        project=project,
        view=snapshot["view"],
        max_nodes=snapshot["max_nodes"],
        max_edges=snapshot["max_edges"],
        generated_at=snapshot["generated_at"],
        nodes=[GraphNode(**node) for node in snapshot["nodes"]],
        edges=[GraphEdge(**edge) for edge in snapshot["edges"]],
        unresolved=list(snapshot["unresolved"]),
        warnings=list(snapshot["warnings"]),
    )
    graph._node_ids = {node.id for node in graph.nodes}
    graph._edge_ids = {edge.id for edge in graph.edges}
    return graph


def build_relation_graph_cached(
    project: Project,
    *,
    cache_key: Hashable | None = None,
    view: str = "project_overview",
    max_nodes: int | None = 400,
    max_edges: int | None = 400,
) -> RelationGraph:
    """Build or reuse a graph snapshot when the caller supplies a revision key.

    Use a stable scan/revision ID for ``cache_key`` and change it whenever the
    project's parsed contents change. Without a key, this deliberately falls
    back to a fresh build. A fresh RelationGraph is returned on cache hits so
    one request cannot mutate another request's cached graph object.
    """
    if cache_key is None:
        return build_relation_graph(
            project, view=view, max_nodes=max_nodes, max_edges=max_edges
        )

    key = (str(project.root), project.name, cache_key, view, max_nodes, max_edges)
    with _GRAPH_CACHE_LOCK:
        snapshot = _GRAPH_CACHE.get(key)
        if snapshot is not None:
            _GRAPH_CACHE.move_to_end(key)
            graph = _graph_from_snapshot(project, snapshot)
            project.metadata["relation_graph"] = graph.as_dict()
            project.metadata["relation_graph_unresolved"] = list(graph.unresolved)
            return graph

    graph = build_relation_graph(
        project, view=view, max_nodes=max_nodes, max_edges=max_edges
    )
    snapshot = graph.as_dict()
    with _GRAPH_CACHE_LOCK:
        # Another request may have completed the same build while this one ran.
        _GRAPH_CACHE[key] = snapshot
        _GRAPH_CACHE.move_to_end(key)
        while len(_GRAPH_CACHE) > _GRAPH_CACHE_MAX_ENTRIES:
            _GRAPH_CACHE.popitem(last=False)
    return graph


def clear_relation_graph_cache(cache_key: Hashable | None = None) -> None:
    """Clear all cached graphs, or entries belonging to one scan/revision key."""
    with _GRAPH_CACHE_LOCK:
        if cache_key is None:
            _GRAPH_CACHE.clear()
            return
        for key in list(_GRAPH_CACHE):
            if key[2] == cache_key:
                del _GRAPH_CACHE[key]


async def build_relation_graph_async(
    project: Project,
    *,
    view: str = "project_overview",
    max_nodes: int | None = 400,
    max_edges: int | None = 400,
    cache_key: Hashable | None = None,
) -> RelationGraph:
    """Build a graph off the asyncio event loop for async web-server routes.

    Example in FastAPI:
        graph = await build_relation_graph_async(project, view="project_overview")
        return graph.as_dict()

    This prevents synchronous graph construction from blocking the event loop.
    It does not guarantee CPU speedup; indexing and deduplication are the main
    computation optimizations. Avoid concurrent builds that mutate the same
    Project instance because the graph result is written to project.metadata.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _GRAPH_EXECUTOR,
        lambda: build_relation_graph_cached(
            project,
            cache_key=cache_key,
            view=view,
            max_nodes=max_nodes,
            max_edges=max_edges,
        ),
    )


def shutdown_graph_executor(wait: bool = True) -> None:
    """Shut down the module-level graph executor during application shutdown."""
    _GRAPH_EXECUTOR.shutdown(wait=wait, cancel_futures=True)
