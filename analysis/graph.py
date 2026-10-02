from __future__ import annotations

import json
import re
import sys
from importlib.metadata import packages_distributions
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from model.project import Project, RelationshipNode

EVIDENCE_LEVELS = ("DECLARED", "DETECTED", "INFERRED", "UNKNOWN")

# Keep graph construction focused on code owned by the project. Discovery
# already prunes these directories, but this second guard protects graphs built
# from cached, manually-created, or older Project objects that contain vendor
# entities.
_DEFAULT_IGNORED_SOURCE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    "site-packages",
    "dist-packages",
    "vendor",
    "vendors",
    "third_party",
    "third-party",
    "external",
    "deps",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "target",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".barkly-docs-site",
}


def _is_project_source_path(project: Project, value: str | Path | None) -> bool:
    """Return whether a source path belongs to the project, not a vendor tree.

    Relative paths are interpreted relative to ``project.root``. A path outside
    the project root is external. Pathless symbols are retained for backwards
    compatibility, but edges sourced from excluded files are removed below.
    """
    if value is None or not str(value).strip():
        return True

    raw = Path(str(value).replace("\\", "/"))
    root = Path(project.root).resolve() if project.root else None

    try:
        if raw.is_absolute():
            resolved = raw.resolve()
            if root is not None:
                relative = resolved.relative_to(root)
            else:
                relative = resolved
        else:
            relative = raw
    except (OSError, ValueError):
        return False

    ignored = {name.casefold() for name in _DEFAULT_IGNORED_SOURCE_DIRS}
    return not any(part.casefold() in ignored for part in relative.parts[:-1])


def _node_source_path(node: Any) -> str | None:
    """Read the source path from any project model node shape."""
    return (
        getattr(node, "source_file", None)
        or getattr(node, "path", None)
        or getattr(node, "file_path", None)
    )


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
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )
    _node_ids: set[str] = field(default_factory=set, init=False, repr=False)
    _edge_ids: set[str] = field(default_factory=set, init=False, repr=False)

    def add_node(self, node: GraphNode) -> None:
        # Seed indexes if callers initialized the public lists directly.
        if not self._node_ids and self.nodes:
            self._node_ids.update(existing.id for existing in self.nodes)
        if node.id in self._node_ids:
            return
        self.nodes.append(node)
        self._node_ids.add(node.id)

    def add_edge(self, edge: GraphEdge) -> None:
        if not self._edge_ids and self.edges:
            self._edge_ids.update(existing.id for existing in self.edges)
        if edge.id in self._edge_ids:
            return
        self.edges.append(edge)
        self._edge_ids.add(edge.id)

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
        return (
            candidate
            if "." in candidate or candidate.startswith("file:")
            else candidate
        )
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
        return detail.get(
            "message",
            "Import statement declares a dependency on another file or module.",
        )
    if kind == "contains":
        return detail.get(
            "message", "This node owns or defines the target symbol in the same file."
        )
    if kind == "calls":
        return detail.get(
            "message", "A static call expression directly invokes the target symbol."
        )
    if kind == "inherits":
        return detail.get(
            "message", "The class explicitly inherits from the target superclass."
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
            "message", "An endpoint or route resolves through this handler target."
        )
    return detail.get(
        "message", "Static source evidence captured by the project analysis pipeline."
    )


def _build_symbol_index(
    project: Project,
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """Index known project symbols once so resolving thousands of imports is O(1)."""
    symbols: dict[str, str] = {}
    classes_by_name_path: dict[tuple[str, str], Any] = {}

    def add(name: str | None, identifier: str) -> None:
        normalized = _normalize_identifier(name)
        if normalized:
            # setdefault preserves the same first-match priority as the old scans.
            symbols.setdefault(normalized, identifier)

    for module in project.modules:
        if _is_project_source_path(project, _node_source_path(module)):
            add(module.name, f"module:{module.name}")
            add(module.path, f"module:{module.name}")
    for file in project.files:
        if _is_project_source_path(project, _node_source_path(file)):
            add(file.path, f"file:{file.path}")
    for class_node in project.classes:
        if _is_project_source_path(project, _node_source_path(class_node)):
            add(class_node.name, class_node.name)
            add(class_node.path, class_node.name)
            classes_by_name_path.setdefault(
                (class_node.name, class_node.path or ""), class_node
            )
    for function in project.functions:
        if _is_project_source_path(project, _node_source_path(function)):
            add(function.name, function.name)
            add(
                function.metadata.get("qualified_name"),
                str(function.metadata.get("qualified_name") or ""),
            )
    for method in project.methods:
        if _is_project_source_path(project, _node_source_path(method)):
            add(
                method.name,
                (
                    method.class_name + "." + method.name
                    if method.class_name
                    else method.name
                ),
            )
            add(
                method.metadata.get("qualified_name"),
                str(method.metadata.get("qualified_name") or ""),
            )
    for endpoint in project.endpoints:
        if _is_project_source_path(project, _node_source_path(endpoint)):
            add(endpoint.path, endpoint.handler or endpoint.path)
            add(endpoint.handler, endpoint.handler or endpoint.path)
    return symbols, classes_by_name_path


def _match_known_symbol(
    project: Project,
    name: str | None,
    *,
    path: str | None = None,
    symbol_index: dict[str, str] | None = None,
) -> str | None:
    if not name:
        return None
    normalized = _normalize_identifier(name)
    if not normalized:
        return None
    if symbol_index is None:
        symbol_index, _ = _build_symbol_index(project)
    match = symbol_index.get(normalized)
    if match is not None:
        return match
    if path:
        file_name = str(Path(path)).replace("\\", "/").rsplit("/", 1)[-1]
        if file_name == normalized:
            return f"file:{str(Path(path)).replace('\\', '/')}"
    return None


def _record_unresolved(
    edges: list[GraphEdge],
    known_identifiers: set[str],
    project: Project,
    *,
    source_file: str | None = None,
) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for edge in edges:
        if edge.source in known_identifiers and edge.target in known_identifiers:
            continue
        if edge.kind in {
            "calls",
            "inherits",
            "implements",
            "references",
            "routes_to",
            "imports",
        }:
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
        key=lambda item: (
            order.get(item.kind, 999),
            item.label.lower(),
            item.id.lower(),
        ),
    )


def _project_component_name(project: Project, value: str | Path | None) -> str | None:
    """Map a source path to a readable top-level project component."""
    if not value or not _is_project_source_path(project, str(value)):
        return None
    raw = Path(str(value).replace("\\", "/"))
    root = Path(project.root).resolve() if project.root else None
    try:
        relative = (
            raw.resolve().relative_to(root) if raw.is_absolute() and root else raw
        )
    except (OSError, ValueError):
        return None
    parts = [part for part in relative.parts if part not in {".", ""}]
    if not parts:
        return "Project root"
    # Treat common source containers as layout, not as components themselves.
    if (
        parts[0].casefold()
        in {"src", "source", "sources", "lib", "app", "apps", "packages"}
        and len(parts) > 1
    ):
        return parts[1]
    if len(parts) == 1:
        return "Project root"
    return parts[0]


def _collapse_to_project_overview(graph: RelationGraph) -> None:
    """Replace symbol-level graph contents with a component-level architecture map."""
    original_nodes = list(graph.nodes)
    original_edges = list(graph.edges)
    node_component: dict[str, str] = {}
    component_files: dict[str, set[str]] = {}
    component_node_counts: dict[str, dict[str, int]] = {}
    component_path: dict[str, str] = {}

    for node in original_nodes:
        source_path = node.source_file or node.path
        component = _project_component_name(graph.project, source_path)
        if component is None:
            continue
        node_component[node.id] = component
        component_files.setdefault(component, set())
        if source_path:
            component_files[component].add(str(source_path))
            component_path.setdefault(component, component)
        counts = component_node_counts.setdefault(component, {})
        counts[node.kind] = counts.get(node.kind, 0) + 1

    # Resolve imported module targets to their source component when possible.
    module_component: dict[str, str] = {}
    for module in graph.project.modules:
        component = _project_component_name(graph.project, _node_source_path(module))
        if component:
            module_component[module.name] = component
            module_component[f"module:{module.name}"] = component
            if module.path:
                module_component[module.path] = component
                module_component[f"file:{module.path}"] = component
    for file_node in graph.project.files:
        component = _project_component_name(graph.project, _node_source_path(file_node))
        if component:
            module_component[file_node.path] = component
            module_component[f"file:{file_node.path}"] = component

    # A component can exist even if it has no relationship edges.
    component_nodes: dict[str, GraphNode] = {}
    for name in sorted(component_node_counts, key=str.casefold):
        counts = component_node_counts[name]
        total = sum(counts.values())
        component_nodes[name] = GraphNode(
            id=f"component:{name}",
            label=name,
            kind="component",
            qualified_name=name,
            path=name,
            source_file=None,
            evidence="DETECTED",
            metadata={
                "project_level": True,
                "entity_count": total,
                "entity_types": counts,
                "file_count": len(component_files.get(name, set())),
                "internal_relationship_count": 0,
            },
        )

    grouped_edges: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in original_edges:
        source_component = node_component.get(edge.source)
        if source_component is None and edge.source_file:
            source_component = _project_component_name(graph.project, edge.source_file)
        target_component = node_component.get(edge.target) or module_component.get(
            edge.target
        )
        if target_component is None:
            # A target can be a path-qualified file or module identifier.
            candidate = edge.target.removeprefix("file:").removeprefix("module:")
            target_component = module_component.get(candidate)
            if target_component is None and "." in candidate:
                # A package import often names a submodule even when only its
                # parent package is represented as a scanned component.
                target_component = module_component.get(candidate.split(".", 1)[0])
                if target_component is None:
                    top_level = candidate.split(".", 1)[0]
                    if top_level in component_nodes:
                        target_component = top_level
            if target_component is None and ("/" in candidate or "\\" in candidate):
                target_component = _project_component_name(graph.project, candidate)
        if source_component is None:
            continue
        if target_component is None:
            # Do not turn third-party/unresolved libraries into project components.
            continue
        if source_component == target_component:
            node = component_nodes.get(source_component)
            if node:
                node.metadata["internal_relationship_count"] += 1
            continue
        key = (source_component, target_component)
        aggregate = grouped_edges.setdefault(
            key, {"count": 0, "kinds": set(), "evidence": set(), "examples": []}
        )
        aggregate["count"] += 1
        aggregate["kinds"].add(edge.kind)
        aggregate["evidence"].add(edge.evidence or "UNKNOWN")
        if len(aggregate["examples"]) < 3:
            aggregate["examples"].append(
                {"kind": edge.kind, "source": edge.source, "target": edge.target}
            )

    overview_edges: list[GraphEdge] = []
    for (source_name, target_name), aggregate in sorted(grouped_edges.items()):
        evidence = (
            "DECLARED"
            if "DECLARED" in aggregate["evidence"]
            else ("DETECTED" if "DETECTED" in aggregate["evidence"] else "INFERRED")
        )
        kinds = sorted(aggregate["kinds"])
        overview_edges.append(
            GraphEdge(
                id=f"component:{source_name}->component:{target_name}",
                source=f"component:{source_name}",
                target=f"component:{target_name}",
                kind="connects_to",
                label="connects to",
                source_file=None,
                evidence=evidence,
                explanation=f"{aggregate['count']} relationship(s) connect these project components.",
                metadata={
                    "relationship_count": aggregate["count"],
                    "relationship_kinds": kinds,
                    "examples": aggregate["examples"],
                },
            )
        )

    graph.nodes = list(component_nodes.values())
    graph.edges = overview_edges
    graph.unresolved = []
    graph._node_ids = {node.id for node in graph.nodes}
    graph._edge_ids = {edge.id for edge in graph.edges}
    graph.max_nodes = None
    graph.max_edges = None
    graph.warnings = [
        "Project overview groups files, modules, classes, and functions into top-level components. Detailed symbols remain available on the Entities and Relationships pages."
    ]


def build_relation_graph(
    project: Project,
    *,
    view: str = "relation_map",
    max_nodes: int | None = 200,
    max_edges: int | None = 400,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> RelationGraph:
    """Build the relation graph and optionally report real loop progress.

    The callback receives (stage_name, current_item, total_items). Updates are
    emitted at the beginning, every 25 items, and at completion of each stage.
    """
    graph = RelationGraph(
        project=project, view=view, max_nodes=max_nodes, max_edges=max_edges
    )

    def report_progress(stage: str, current: int, total: int) -> None:
        if progress_callback is not None:
            progress_callback(stage, current, total)

    def progress_items(stage: str, items: list[Any]):
        total = len(items)
        report_progress(stage, 0, total)
        for index, item in enumerate(items, start=1):
            yield item
            if index % 25 == 0 or index == total:
                report_progress(stage, index, total)

    known_identifiers: set[str] = set()
    symbol_index, classes_by_name_path = _build_symbol_index(project)

    for file in progress_items("files", project.files):
        if not _is_project_source_path(project, _node_source_path(file)):
            continue
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

    for module in progress_items("modules", project.modules):
        if not _is_project_source_path(project, _node_source_path(module)):
            continue
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

    for class_node in progress_items("classes", project.classes):
        if not _is_project_source_path(project, _node_source_path(class_node)):
            continue
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
            if not base_name or base_name not in symbol_index:
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

    for interface in progress_items("interfaces", project.interfaces):
        if not _is_project_source_path(project, _node_source_path(interface)):
            continue
        if not _is_project_source_path(project, _node_source_path(interface)):
            continue
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

    for function in progress_items("functions", project.functions):
        if not _is_project_source_path(project, _node_source_path(function)):
            continue
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

    for method in progress_items("methods", project.methods):
        if not _is_project_source_path(project, _node_source_path(method)):
            continue
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
            matching_class = classes_by_name_path.get(
                (method.class_name, method.path or "")
            ) or classes_by_name_path.get((method.class_name, ""))
            if matching_class is None and not method.path:
                matching_class = next(
                    (
                        item
                        for (name, _), item in classes_by_name_path.items()
                        if name == method.class_name
                    ),
                    None,
                )
            if matching_class is not None and matching_class.path:
                class_id = f"{matching_class.name}@{matching_class.path}"
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

    for endpoint in progress_items("endpoints", project.endpoints):
        if not _is_project_source_path(project, _node_source_path(endpoint)):
            continue
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
                    id=f"{endpoint_id}->{endpoint.handler}",
                    source=endpoint_id,
                    target=endpoint.handler,
                    kind="routes_to",
                    label="routes_to",
                    source_file=endpoint.source_file,
                    evidence="DETECTED",
                    explanation="The endpoint route resolves to the declared handler symbol.",
                )
            )

    # Import edges in the default project map are intentionally project-internal.
    # Third-party and standard-library imports remain available in the source
    # inventory, but should not become hundreds of dangling nodes in the map.
    project_module_names = {
        _normalize_identifier(module.name)
        for module in project.modules
        if _is_project_source_path(project, _node_source_path(module))
    }
    project_file_stems = {
        Path(str(file.path).replace("\\", "/")).stem
        for file in project.files
        if _is_project_source_path(project, _node_source_path(file))
    }
    project_file_paths = {
        str(file.path).replace("\\", "/")
        for file in project.files
        if _is_project_source_path(project, _node_source_path(file))
    }
    ignored_import_roots = {name.casefold() for name in _DEFAULT_IGNORED_SOURCE_DIRS}
    try:
        installed_import_roots = {name.casefold() for name in packages_distributions()}
    except Exception:
        installed_import_roots = set()
    stdlib_import_roots = {name.casefold() for name in sys.stdlib_module_names}

    def is_project_import_target(target: str | None) -> bool:
        normalized = _normalize_identifier(target)
        if not normalized:
            return False
        # Readers may report dotted Python names, slash paths, or file names.
        root_name = normalized.replace("\\", "/").split("/", 1)[0].split(".", 1)[0]
        folded_root = root_name.casefold()
        if folded_root in ignored_import_roots or folded_root in stdlib_import_roots:
            return False
        if normalized in symbol_index or normalized in project_module_names:
            return True
        if normalized.replace("\\", "/") in project_file_paths:
            return True
        if root_name in project_module_names or root_name in project_file_stems:
            return True
        # Installed third-party packages are external dependencies, not project
        # source nodes. Unknown names remain visible as unresolved evidence.
        return folded_root not in installed_import_roots

    import_total = len(project.imports)
    report_progress("imports", 0, import_total)
    for import_index, import_node in enumerate(project.imports, start=1):
        # Log the specific import before resolution, so a slow item is identifiable.
        if import_index == 1 or import_index % 25 == 0 or import_index == import_total:
            report_progress(
                f"import_item {import_node.source_file} -> {import_node.target}",
                import_index,
                import_total,
            )
        if not _is_project_source_path(project, import_node.source_file):
            continue
        source_id = (
            _match_known_symbol(
                project, import_node.source_file, symbol_index=symbol_index
            )
            or import_node.source_file
        )
        if not is_project_import_target(import_node.target):
            continue
        target_id = (
            _match_known_symbol(project, import_node.target, symbol_index=symbol_index)
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

    report_progress("imports", import_total, import_total)

    for relationship in progress_items("relationships", project.relationships):
        if not _is_project_source_path(project, relationship.source_file):
            continue
        source_id = (
            _match_known_symbol(
                project,
                relationship.source,
                path=relationship.source_file,
                symbol_index=symbol_index,
            )
            or relationship.source
        )
        target_id = (
            _match_known_symbol(
                project,
                relationship.target,
                path=relationship.source_file,
                symbol_index=symbol_index,
            )
            or relationship.target
        )
        kind = relationship.kind
        edge = GraphEdge(
            id=f"{source_id}->{target_id}:{kind}:{relationship.source_file or 'unknown'}:{relationship.source_location.get('line') if relationship.source_location else ''}",
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
                    "message": relationship.metadata.get("reason")
                    or relationship.metadata.get("explanation"),
                },
            ),
            metadata=dict(relationship.metadata),
        )
        graph.add_edge(edge)

    if view == "project_overview":
        _collapse_to_project_overview(graph)
    graph.nodes = _sort_nodes(graph.nodes)
    graph.edges = sorted(
        graph.edges,
        key=lambda edge: (edge.kind, edge.source, edge.target, edge.source_file or ""),
    )
    graph.unresolved = (
        _record_unresolved(graph.edges, set(known_identifiers), project)
        if view != "project_overview"
        else []
    )
    if graph.max_nodes is not None and len(graph.nodes) > graph.max_nodes:
        graph.warnings.append(
            f"Relation graph was limited to the first {graph.max_nodes} nodes to keep the view responsive."
        )
        graph.nodes = graph.nodes[: graph.max_nodes]
    if graph.max_edges is not None and len(graph.edges) > graph.max_edges:
        graph.warnings.append(
            f"Relation graph was limited to the first {graph.max_edges} edges to keep the view responsive."
        )
        graph.edges = graph.edges[: graph.max_edges]
    graph.unresolved = _record_unresolved(graph.edges, set(known_identifiers), project)
    project.metadata["relation_graph"] = graph.as_dict()
    project.metadata["relation_graph_unresolved"] = list(graph.unresolved)
    return graph
