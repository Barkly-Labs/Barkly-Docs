from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.graph import build_relation_graph
from model.project import ClassNode, FileNode, MethodNode, Project, RelationshipNode
from rendering.html import render_project_website


def test_class_methods_are_connected_to_path_qualified_class_nodes(tmp_path):
    source = str(tmp_path / "tool.py")
    project = Project(name="demo", root=str(tmp_path))
    project.add_file(FileNode(path=source, language="Python"))
    project.add_class(ClassNode(name="Tool", path=source, methods=["first", "second"]))
    project.add_method(MethodNode(name="first", path=source, language="Python", class_name="Tool"))
    project.add_method(MethodNode(name="second", path=source, language="Python", class_name="Tool"))
    project.add_relationship(RelationshipNode(
        source="Tool.first", target="Tool.second", kind="calls", source_file=source,
        source_location={"line": 4}, evidence="DETECTED",
    ))

    graph = build_relation_graph(project, view="relation_map", max_nodes=None, max_edges=None)
    class_id = f"Tool@{source}"
    edges = {(edge.source, edge.target, edge.kind) for edge in graph.edges}

    assert (class_id, "Tool.first", "contains") in edges
    assert (class_id, "Tool.second", "contains") in edges
    assert ("Tool.first", "Tool.second", "calls") in edges
    assert all(edge.source in {node.id for node in graph.nodes} for edge in graph.edges if edge.kind == "contains")


def test_relation_map_includes_searchable_full_relationship_inventory(tmp_path):
    project = Project(name="demo", root=str(tmp_path))
    project.add_file(FileNode(path=str(tmp_path / "tool.py"), language="Python"))
    project.add_relationship(RelationshipNode(source="alpha", target="beta", kind="calls", evidence="DETECTED"))
    output = tmp_path / "site"

    render_project_website(project, output)
    html = (output / "relation-map.html").read_text(encoding="utf-8")
    js = (output / "assets" / "relation-map.js").read_text(encoding="utf-8")

    assert 'id="relationship-list-search"' in html
    assert 'id="relationship-list"' in html
    assert "filteredRelationships" in js
    assert "relationship-list-more" in html
