import json
import re
from pathlib import Path

from model.project import FileNode, FunctionNode, Project, RelationshipNode
from rendering.html import RELATION_MAP_JS, render_project_website


def _project(tmp_path: Path) -> Project:
    project = Project(name="spider-demo", root=str(tmp_path))
    a = str(tmp_path / "a.py")
    b = str(tmp_path / "b.py")
    project.add_file(FileNode(path=a, language="Python"))
    project.add_file(FileNode(path=b, language="Python"))
    project.add_function(FunctionNode(name="alpha", path=a, language="Python", metadata={"qualified_name": "a.alpha"}))
    project.add_function(FunctionNode(name="beta", path=b, language="Python", metadata={"qualified_name": "b.beta"}))
    project.add_relationship(RelationshipNode(source="a.alpha", target="b.beta", kind="calls", source_file=a, source_location={"line": 4}, evidence="DETECTED"))
    return project


def test_relation_map_renders_real_svg_controls_and_accessible_alternative(tmp_path):
    output = tmp_path / "site"
    render_project_website(_project(tmp_path), output)
    html = (output / "relation-map.html").read_text(encoding="utf-8")

    assert '<svg id="relation-map-canvas"' in html
    assert 'id="relation-map-viewport"' in html
    assert 'id="relation-map-details-body"' in html
    assert 'id="relation-map-accessible-list"' in html
    assert 'id="relation-map-edge-kind"' in html
    assert 'id="relation-map-language"' in html
    assert 'id="relation-map-evidence"' in html
    assert 'data-graph-action="zoom-in"' in html
    assert 'data-graph-action="fit"' in html
    assert 'href="relationships.html"' in html
    assert 'relation-card-grid' not in html


def test_relation_map_embeds_complete_real_graph_and_escapes_script_breakout(tmp_path):
    project = _project(tmp_path)
    project.add_file(FileNode(path=str(tmp_path / "</script><script>alert(1)</script>.py"), language="Python"))
    output = tmp_path / "site"
    render_project_website(project, output)
    html = (output / "relation-map.html").read_text(encoding="utf-8")
    match = re.search(r'<script id="relation-map-data" type="application/json">(.*?)</script>', html, re.S)
    assert match
    payload = match.group(1)
    assert "</script><script>" not in payload
    data = json.loads(payload)
    ids = {node["id"] for node in data["nodes"]}
    assert "a.alpha" in ids
    assert "b.beta" in ids
    assert any(edge["source"] == "a.alpha" and edge["target"] == "b.beta" and edge["kind"] == "calls" for edge in data["edges"])
    assert len(ids) == len(data["nodes"])


def test_spider_script_supports_full_dataset_search_filters_selection_and_safe_dom():
    assert "nodes.filter(node => searchText(node).includes(state.search))" in RELATION_MAP_JS
    assert "edgePassesFilters" in RELATION_MAP_JS
    assert "nodePassesFilters" in RELATION_MAP_JS
    assert "selectNode" in RELATION_MAP_JS
    assert 'role: "button", tabindex: "0"' in RELATION_MAP_JS
    assert "previousSelections" in RELATION_MAP_JS
    assert "OVERVIEW_LIMIT = 90" in RELATION_MAP_JS
    assert "NEIGHBOR_LIMIT = 140" in RELATION_MAP_JS
    assert ".innerHTML" not in RELATION_MAP_JS
    assert "textContent" in RELATION_MAP_JS
