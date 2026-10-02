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


def test_relation_map_uses_structurizr_project_level_workspace(tmp_path):
    project = Project(name="demo", root=str(tmp_path))
    project.add_file(FileNode(path=str(tmp_path / "src" / "frontend" / "app.py"), language="Python"))
    project.add_file(FileNode(path=str(tmp_path / "src" / "backend" / "api.py"), language="Python"))
    project.add_relationship(RelationshipNode(
        source="frontend.app", target="backend.api", kind="imports",
        source_file=str(tmp_path / "src" / "frontend" / "app.py"), evidence="DETECTED",
    ))
    output = tmp_path / "site"

    render_project_website(project, output)
    html = (output / "relation-map.html").read_text(encoding="utf-8")
    index_html = (output / "index.html").read_text(encoding="utf-8")
    relationships_html = (output / "relationships.html").read_text(encoding="utf-8")
    dsl = (output / "architecture" / "workspace.dsl").read_text(encoding="utf-8")
    compose = (output / "architecture" / "docker-compose.yml").read_text(encoding="utf-8")

    assert "Structurizr" in html
    assert "Structurizr project-level graph is displayed on the Project overview page" in html
    assert "<iframe" not in html
    assert "<iframe" in index_html
    assert "Project Architecture" in index_html
    assert "graph TD" in relationships_html
    assert 'container "frontend"' in dsl
    assert 'container "backend"' in dsl
    assert "project.frontend -> project.backend" in dsl
    assert "function" not in dsl.lower()
    assert "method" not in dsl.lower()
    assert "structurizr/lite" in compose
    assert '"${STRUCTURIZR_PORT:-8080}:8080"' in compose
    assert '"${BARKLY_DOCS_PORT:-8000}:80"' in compose
    dockerfile = (output / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM nginx:alpine" in dockerfile
    assert "EXPOSE 80" in dockerfile


def test_project_overview_collapses_symbols_into_components_and_hides_external_imports(tmp_path):
    from model.project import ImportNode, FunctionNode

    project = Project(name="overlay-demo", root=str(tmp_path))
    project.add_file(FileNode(path=str(tmp_path / "src" / "frontend" / "app.py"), language="Python"))
    project.add_file(FileNode(path=str(tmp_path / "src" / "backend" / "service.py"), language="Python"))
    project.add_function(FunctionNode(name="render", path=str(tmp_path / "src" / "frontend" / "app.py"), language="Python"))
    project.add_function(FunctionNode(name="serve", path=str(tmp_path / "src" / "backend" / "service.py"), language="Python"))
    project.add_import(ImportNode(source_file=str(tmp_path / "src" / "frontend" / "app.py"), target="backend.service", language="Python"))
    project.add_import(ImportNode(source_file=str(tmp_path / "src" / "frontend" / "app.py"), target="numpy", language="Python"))

    graph = build_relation_graph(project, view="project_overview", max_nodes=None, max_edges=None)

    assert {node.label for node in graph.nodes} == {"frontend", "backend"}
    assert all(node.kind == "component" for node in graph.nodes)
    assert all("render" not in node.label and "serve" not in node.label for node in graph.nodes)
    assert len(graph.edges) == 1
    assert graph.edges[0].source == "component:frontend"
    assert graph.edges[0].target == "component:backend"
    assert graph.edges[0].kind == "connects_to"
