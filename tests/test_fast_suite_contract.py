from __future__ import annotations

from pathlib import Path

import pytest

from analysis.discovery import ProjectDiscovery
from analysis.graph import build_relation_graph
from model.project import FileNode, FunctionNode, Project, RelationshipNode
from readers.java import JavaReader
from readers.javascript import JavaScriptReader
from readers.json import JSONReader
from readers.python import PythonReader
from readers.ruby import RubyReader
from readers.rust import RustReader
from rendering.html import render_project_website


@pytest.mark.parametrize(
    ("reader", "filename", "source", "language"),
    [
        (PythonReader(), "app.py", "import os\n\ndef run():\n    return 1\n", "Python"),
        (JavaScriptReader(), "app.js", "import x from './x.js';\nexport function run(){ return x; }\n", "JavaScript"),
        (JavaReader(), "App.java", "import java.util.List;\nclass App { void run() {} }\n", "Java"),
        (RubyReader(), "app.rb", "require 'json'\nclass App\n  def run; 1; end\nend\n", "Ruby"),
        (RustReader(), "app.rs", "use std::fmt;\nfn run() -> i32 { 1 }\n", "Rust"),
        (JSONReader(), "app.json", '{"name":"demo","enabled":true}\n', "JSON"),
    ],
)
def test_registered_readers_parse_tiny_valid_files(tmp_path, reader, filename, source, language):
    path = tmp_path / filename
    path.write_text(source, encoding="utf-8")
    project = Project(name="fixture", root=str(tmp_path))
    result = reader.read(path, project)
    assert result.success, f"{reader.__class__.__name__} failed {filename}: {result.errors}"
    assert any(Path(item.path).name == filename for item in project.files)
    assert any(item.language == language for item in project.files)


def test_project_relationship_preserves_direction_type_and_metadata():
    project = Project(name="fixture", root="/tmp/fixture")
    rel = RelationshipNode(
        source="caller",
        target="callee",
        kind="calls",
        evidence="DETECTED",
        source_location={"line": 7},
        metadata={"symbol": "callee"},
    )
    project.add_relationship(rel)
    stored = project.relationships[0]
    assert (stored.source, stored.target, stored.kind) == ("caller", "callee", "calls")
    assert stored.source_location == {"line": 7}
    assert stored.metadata["symbol"] == "callee"


def test_graph_keeps_unresolved_relationship_as_evidence():
    project = Project(name="fixture", root="/tmp/fixture")
    project.add_function(FunctionNode(name="caller", path="/tmp/fixture/app.py", language="Python"))
    project.add_relationship(RelationshipNode(source="caller", target="missing", kind="calls", evidence="DETECTED"))
    graph = build_relation_graph(project, max_edges=None)
    matching = [edge for edge in graph.edges if edge.kind == "calls" and edge.label == "calls"]
    assert matching, "detected call disappeared before graph construction"
    assert any(edge.target for edge in matching)


def test_renderer_escapes_source_derived_relationship_text(tmp_path):
    project = Project(name="<unsafe>", root=str(tmp_path))
    project.add_relationship(RelationshipNode(source="<caller>", target="target&name", kind="calls", evidence="DETECTED"))
    out = tmp_path / "site"
    render_project_website(project, out)
    html = (out / "relationships.html").read_text(encoding="utf-8")
    assert "&lt;caller&gt;" in html
    assert "target&amp;name" in html
    assert "<caller>" not in html


def test_tiny_end_to_end_discovery_and_render(tmp_path):
    (tmp_path / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("from helper import helper\n\ndef run():\n    return helper()\n", encoding="utf-8")
    result = ProjectDiscovery([PythonReader()]).analyze(tmp_path, name="Tiny E2E", parallel=False)
    assert not result.errors
    assert {f.name for f in result.project.functions} >= {"helper", "run"}
    out = tmp_path / "generated"
    render_project_website(result.project, out)
    for filename in ("index.html", "entities.html", "relationships.html", "relation-map.html"):
        assert (out / filename).is_file(), f"missing generated {filename}"
    assert "run" in (out / "entities.html").read_text(encoding="utf-8")
