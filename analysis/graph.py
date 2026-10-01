from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model.project import Project, RelationshipNode


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
    max_nodes: int | None = None
    max_edges: int | None = None
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def add_node(self, node: GraphNode) -> None:
        if any(existing.id == node.id for existing in self.nodes):
            return
        self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        if any(existing.id == edge.id for existing in self.edges):
            return
        self.edges.append(edge)

    def summary(self) -> dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "unresolved": len(self.unresolved),
            "warnings": len(self.warnings),
        }

    def as_dict(self) -> dict[str, Any]:
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


def _build_qualified_name(project: Project, *, value: str | None, path: str | None = None, kind: str = "symbol") -> str:
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


def _relationship_explanation(kind: str, detail: dict[str, Any] | None = None) -> str:
    detail = detail or {}
    if kind == "imports":
        return detail.get("message", "Import statement declares a dependency on another file or module.")
    if kind == "contains":
        return detail.get("message", "This node owns or defines the target symbol in the same file.")
    if kind == "calls":
        return detail.get("message", "A static call expression directly invokes the target symbol.")
    if kind == "inherits":
        return detail.get("message", "The class explicitly inherits from the target superclass.")
    if kind == "implements":
        return detail.get("message", "The class explicitly implements the target interface or contract.")
    if kind == "references":
        return detail.get("message", "The symbol references another symbol without an explicit call or inheritance link.")
    if kind == "routes_to":
        return detail.get("message", "An endpoint or route resolves through this handler target.")
    return detail.get("message", "Static source evidence captured by the project analysis pipeline.")


def _match_known_symbol(project: Project, name: str | None, *, path: str | None = None) -> str | None:
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
            return class_node.name
        if class_node.path == normalized:
            return class_node.name
    for function in project.functions:
        if function.name == normalized:
            return function.name
        if function.metadata.get("qualified_name") == normalized:
            return str(function.metadata.get("qualified_name"))
    for method in project.methods:
        if method.name == normalized:
            return method.class_name + "." + method.name if method.class_name else method.name
        if method.metadata.get("qualified_name") == normalized:
            return str(method.metadata.get("qualified_name"))
    for endpoint in project.endpoints:
        if endpoint.path == normalized or endpoint.handler == normalized:
            return endpoint.handler or endpoint.path
    if path:
        file_name = str(Path(path)).replace("\\", "/").rsplit("/", 1)[-1]
        if file_name == normalized:
            return f"file:{str(Path(path)).replace('\\', '/')}"
    return None


def _record_unresolved(edges: list[GraphEdge], known_identifiers: set[str], project: Project, *, source_file: str | None = None) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for edge in edges:
        if edge.source in known_identifiers and edge.target in known_identifiers:
            continue
        if edge.kind in {"calls", "inherits", "implements", "references", "routes_to", "imports"}:
            unresolved.append({
                "source": edge.source,
                "target": edge.target,
                "kind": edge.kind,
                "source_file": edge.source_file,
                "evidence": edge.evidence,
                "reason": "target symbol not found in the current scan",
                "explanation": edge.explanation,
            })
    return unresolved


def _sort_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
    order = {kind: index for index, kind in enumerate(NODE_KIND_ORDER)}
    return sorted(nodes, key=lambda item: (order.get(item.kind, 999), item.label.lower(), item.id.lower()))


def build_relation_graph(project: Project, *, view: str = "project_overview", max_nodes: int | None = 200, max_edges: int | None = 400) -> RelationGraph:
    graph = RelationGraph(project=project, view=view, max_nodes=max_nodes, max_edges=max_edges)

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

    for class_node in project.classes:
        class_id = class_node.name
        if class_node.path:
            class_id = f"{class_node.name}@{class_node.path}"
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
        interface_id = interface.name
        if interface.path:
            interface_id = f"{interface.name}@{interface.path}"
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
        function_id = function.name
        if function.metadata.get("qualified_name"):
            function_id = str(function.metadata.get("qualified_name"))
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
        method_id = method.name
        if method.class_name:
            method_id = f"{method.class_name}.{method.name}"
        if method.metadata.get("qualified_name"):
            method_id = str(method.metadata.get("qualified_name"))
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
            class_id = method.class_name
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
        source_id = _match_known_symbol(project, import_node.source_file) or import_node.source_file
        target_id = _match_known_symbol(project, import_node.target) or import_node.target
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
                metadata={"names": list(import_node.names), "alias": import_node.alias, "language": import_node.language},
            )
        )

    for relationship in project.relationships:
        source_id = _match_known_symbol(project, relationship.source, path=relationship.source_file) or relationship.source
        target_id = _match_known_symbol(project, relationship.target, path=relationship.source_file) or relationship.target
        kind = relationship.kind
        edge = GraphEdge(
            id=f"{source_id}->{target_id}:{kind}:{relationship.source_file or 'unknown'}:{relationship.source_location.get('line') if relationship.source_location else ''}",
            source=source_id,
            target=target_id,
            kind=kind,
            label=kind,
            source_file=relationship.source_file,
            source_location=(dict(relationship.source_location) if relationship.source_location else None),
            evidence=relationship.evidence if relationship.evidence in EVIDENCE_LEVELS else "UNKNOWN",
            explanation=_relationship_explanation(kind, {"line": relationship.source_location.get("line") if relationship.source_location else None, "source": relationship.source, "target": relationship.target, "message": relationship.metadata.get("reason") or relationship.metadata.get("explanation")}),
            metadata=dict(relationship.metadata),
        )
        graph.add_edge(edge)

    graph.nodes = _sort_nodes(graph.nodes)
    graph.edges = sorted(graph.edges, key=lambda edge: (edge.kind, edge.source, edge.target, edge.source_file or ""))
    graph.unresolved = _record_unresolved(graph.edges, set(known_identifiers), project)
    if graph.max_nodes is not None and len(graph.nodes) > graph.max_nodes:
        graph.warnings.append(f"Relation graph was limited to the first {graph.max_nodes} nodes to keep the view responsive.")
        graph.nodes = graph.nodes[: graph.max_nodes]
    if graph.max_edges is not None and len(graph.edges) > graph.max_edges:
        graph.warnings.append(f"Relation graph was limited to the first {graph.max_edges} edges to keep the view responsive.")
        graph.edges = graph.edges[: graph.max_edges]
    graph.unresolved = _record_unresolved(graph.edges, set(known_identifiers), project)
    project.metadata["relation_graph"] = graph.as_dict()
    project.metadata["relation_graph_unresolved"] = list(graph.unresolved)
    return graph
