from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.discovery import ProjectDiscovery
from model.project import (
    ClassNode,
    FileNode,
    FunctionNode,
    ImportNode,
    MethodNode,
    ModuleNode,
    Project,
    RelationshipNode,
)
from analysis.graph import build_relation_graph
from model.relationships import RelationshipEngine, RELATIONSHIP_KINDS
from rendering.html import render_project_website
from readers.java import JavaReader
from readers.javascript import JavaScriptReader
from readers.json import JSONReader
from readers.python import PythonReader
from readers.ruby import RubyReader
from readers.rust import RustReader


def test_project_discovery_finds_supported_files_and_skips_ignored_dirs(tmp_path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "app.py").write_text(
        "def hello():\n    return 'hi'\n", encoding="utf-8"
    )
    (source_dir / "ui.js").write_text(
        "export function run() { return 1; }\n", encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text("ignore me\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text(
        "console.log('ignore me')\n", encoding="utf-8"
    )
    (tmp_path / "docs-site").mkdir()
    (tmp_path / "docs-site" / "generated.py").write_text(
        "def generated(): pass\n", encoding="utf-8"
    )

    result = ProjectDiscovery(
        [PythonReader(), JavaScriptReader()],
    ).analyze(tmp_path, name="fixture")

    processed = {path.name for path in result.processed_files}
    assert {"app.py", "ui.js"}.issubset(processed)
    assert "notes.txt" not in processed
    assert not any(path.name == "pkg.js" for path in result.processed_files)
    assert not any(path.name == "generated.py" for path in result.processed_files)
    assert result.project.name == "fixture"


def test_readers_are_selected_for_the_right_file_types():
    readers = [
        PythonReader(),
        JavaScriptReader(),
        JavaReader(),
        RubyReader(),
        RustReader(),
        JSONReader(),
    ]

    by_extension = {
        ".py": PythonReader,
        ".js": JavaScriptReader,
        ".java": JavaReader,
        ".rb": RubyReader,
        ".rs": RustReader,
        ".json": JSONReader,
    }

    for extension, reader_type in by_extension.items():
        selected = next(
            reader for reader in readers if reader.can_read(Path(f"sample{extension}"))
        )
        assert isinstance(selected, reader_type)

    assert not PythonReader().can_read(Path("sample.txt"))


def test_project_summary_is_consistent():
    project = Project(name="demo", root="/tmp/demo")
    project.add_file(FileNode(path="/tmp/demo/app.py", language="Python"))
    project.add_module(
        ModuleNode(name="app", path="/tmp/demo/app.py", language="Python")
    )
    project.add_function(
        FunctionNode(name="hello", path="/tmp/demo/app.py", language="Python")
    )
    project.add_method(
        MethodNode(
            name="run", path="/tmp/demo/app.py", language="Python", class_name="Thing"
        )
    )
    project.add_class(
        ClassNode(name="Thing", path="/tmp/demo/app.py", language="Python")
    )

    summary = project.summary()
    assert summary["files"] == 1
    assert summary["modules"] == 1
    assert summary["functions"] == 1
    assert summary["methods"] == 1
    assert summary["classes"] == 1


def test_python_reader_extracts_functions_classes_and_variables(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text(
        """
VALUE = 7


def greet(name: str) -> str:
    \"\"\"Return a greeting.\"\"\"
    return f\"hello {name}\"


class Greeter:
    def format(self, name: str) -> str:
        return greet(name)
""".strip() + "\n",
        encoding="utf-8",
    )

    project = Project(name="demo", root=str(tmp_path))
    result = PythonReader().read(path, project)

    assert result.success is True
    assert not result.errors
    assert {function.name for function in project.functions} == {"greet"}
    assert {class_node.name for class_node in project.classes} == {"Greeter"}
    assert {method.name for method in project.methods} == {"format"}
    variable_names = {variable.name for variable in project.variables}
    assert "VALUE" in variable_names


def test_python_reader_uses_shared_project_deduplication_for_declared_symbols(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text(
        "def run():\n    return 7\n\nclass Worker:\n    def run(self):\n        return 7\n",
        encoding="utf-8",
    )

    project = Project(name="demo", root=str(tmp_path))
    reader = PythonReader()

    reader.read(path, project)
    reader.read(path, project)

    assert len(project.functions) == 1
    assert len(project.methods) == 1
    assert len(project.classes) == 1
    assert project.summary()["functions"] == 1
    assert project.summary()["methods"] == 1


def test_java_reader_keeps_constructor_and_method_counts_isolated_per_file(tmp_path):
    alpha = tmp_path / "Alpha.java"
    alpha.write_text(
        "public class Alpha {\n"
        "    public Alpha() {}\n"
        "    public int add(int value) {\n"
        "        return value + 1;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    beta = tmp_path / "Beta.java"
    beta.write_text(
        "public class Beta {\n"
        "    public Beta() {}\n"
        "    public void run() {}\n"
        "}\n",
        encoding="utf-8",
    )

    alpha_project = Project(name="alpha", root=str(tmp_path))
    JavaReader().read(alpha, alpha_project)
    assert alpha_project.summary()["classes"] == 1
    assert alpha_project.summary()["methods"] == 2
    assert {method.name for method in alpha_project.methods} == {"Alpha", "add"}

    beta_project = Project(name="beta", root=str(tmp_path))
    JavaReader().read(beta, beta_project)
    assert beta_project.summary()["classes"] == 1
    assert beta_project.summary()["methods"] == 2
    assert {method.name for method in beta_project.methods} == {"Beta", "run"}

    aggregate = Project(name="aggregate", root=str(tmp_path))
    JavaReader().read(alpha, aggregate)
    JavaReader().read(beta, aggregate)
    JavaReader().read(alpha, aggregate)

    assert aggregate.summary()["files"] == 2
    assert aggregate.summary()["classes"] == 2
    assert aggregate.summary()["methods"] == 4
    assert {method.name for method in aggregate.methods} == {
        "Alpha",
        "add",
        "Beta",
        "run",
    }


def test_supported_readers_do_not_crash_on_ordinary_source_files(tmp_path):
    cases = [
        (
            PythonReader(),
            "demo.py",
            "def double(value):\n    return value * 2\n",
        ),
        (
            JavaScriptReader(),
            "demo.js",
            "export function double(value) { return value * 2; }\n",
        ),
        (
            JavaReader(),
            "Demo.java",
            "public class Demo { public int doubleValue(int value) { return value * 2; } }\n",
        ),
        (
            RubyReader(),
            "demo.rb",
            "class Demo\n  def double(value)\n    value * 2\n  end\nend\n",
        ),
        (
            RustReader(),
            "demo.rs",
            "pub struct Demo { value: i32 }\n\nimpl Demo { pub fn double(&self) -> i32 { self.value * 2 } }\n",
        ),
    ]

    for reader, filename, source_text in cases:
        path = tmp_path / filename
        path.write_text(source_text, encoding="utf-8")
        result = reader.read(path, Project(name="demo", root=str(tmp_path)))
        assert result.success is True, (filename, result.errors)


def test_relationship_engine_adds_unique_relationships_with_provenance():
    project = Project(name="demo", root="/tmp/demo")
    engine = RelationshipEngine(project)

    relationship = engine.add(
        "module.alpha",
        "module.beta",
        "imports",
        source_file="module_alpha.py",
        source_location={"line": 12, "column": 1},
    )

    assert relationship is not None
    assert relationship.evidence == "DETECTED"
    assert relationship.source_location == {"line": 12, "column": 1}
    assert len(project.relationships) == 1
    assert engine.incoming("module.beta", kind="imports") == [relationship]

    duplicate = engine.add(
        "module.alpha",
        "module.beta",
        "imports",
        source_file="module_alpha.py",
    )
    assert duplicate is None
    assert len(project.relationships) == 1


def test_relationship_validation_handles_invalid_endpoints_and_evidence():
    project = Project(name="demo", root="/tmp/demo")
    engine = RelationshipEngine(project)

    assert engine.add("", "module.beta", "imports") is None
    assert engine.add("module.alpha", "", "imports") is None
    assert engine.add("module.alpha", "module.beta", "") is None

    relationship = RelationshipNode(
        source="module.alpha",
        target="module.beta",
        kind="imports",
        evidence="UNSUPPORTED",
        source_location={"line": 3},
    )
    project.add_relationship(relationship)
    assert relationship.evidence == "UNKNOWN"
    assert engine.validate() == []

    assert "imports" in RELATIONSHIP_KINDS


@pytest.mark.slow
def test_cli_runs_on_a_small_project_and_returns_zero(tmp_path):
    project_dir = tmp_path / "fixture"
    project_dir.mkdir()
    (project_dir / "example.py").write_text(
        "def run():\n    return 7\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            str(project_dir),
            "--name",
            "Fixture",
            "--generate-only",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "BARKLY DOCS" in result.stdout


def test_html_site_generation_renders_pages_and_relationships(tmp_path):
    project = Project(name="Widget", root=str(tmp_path))
    project.add_file(FileNode(path=str(tmp_path / "app.py"), language="Python"))
    project.add_function(
        FunctionNode(
            name="run",
            path=str(tmp_path / "app.py"),
            language="Python",
            parameters=["value"],
            return_type="int",
            documentation="Run a widget.",
        )
    )
    project.add_class(
        ClassNode(
            name="WidgetRunner",
            path=str(tmp_path / "app.py"),
            language="Python",
            methods=["run"],
        )
    )
    project.add_method(
        MethodNode(
            name="run",
            path=str(tmp_path / "app.py"),
            language="Python",
            class_name="WidgetRunner",
            parameters=["value"],
            return_type="int",
            documentation="Execute the widget runner.",
        )
    )
    project.add_relationship(
        RelationshipNode(
            source="WidgetRunner",
            target="run",
            kind="calls",
            source_file="app.py",
            evidence="DETECTED",
            source_location={"line": 7, "column": 3},
        )
    )

    output_dir = tmp_path / "site"
    created = render_project_website(project, output_dir)

    assert output_dir.joinpath("index.html").exists()
    assert output_dir.joinpath("entities.html").exists()
    assert output_dir.joinpath("relationships.html").exists()
    assert output_dir.joinpath("relation-map.html").exists()
    assert output_dir.joinpath("assets", "site.css").exists()
    assert output_dir.joinpath("assets", "relation-map.js").exists()

    index_html = output_dir.joinpath("index.html").read_text(encoding="utf-8")
    assert "Widget" in index_html
    assert "Project overview" in index_html
    assert "assets/site.css" in index_html

    entities_html = output_dir.joinpath("entities.html").read_text(encoding="utf-8")
    assert "Entity explorer" in entities_html
    assert (
        "Run a widget." in entities_html
        or "Execute the widget runner." in entities_html
    )

    relationships_html = output_dir.joinpath("relationships.html").read_text(
        encoding="utf-8"
    )
    assert "WidgetRunner" in relationships_html
    assert "DETECTED" in relationships_html
    assert "Relationship explorer" in relationships_html
    assert "calls" in relationships_html

    relation_map_html = output_dir.joinpath("relation-map.html").read_text(
        encoding="utf-8"
    )
    assert "Relation Map" in relation_map_html
    assert "relation-map-data" in relation_map_html
    assert "assets/relation-map.js" in relation_map_html
    assert "WidgetRunner" in relation_map_html
    assert not output_dir.joinpath("architecture", "workspace.dsl").exists()
    assert not output_dir.joinpath("architecture", "docker-compose.yml").exists()


def test_relation_graph_normalizes_scan_relationships_and_unresolved_refs():
    project = Project(name="graph-demo", root="/tmp/graph-demo")
    project.add_file(FileNode(path="/tmp/graph-demo/app.py", language="Python"))
    project.add_function(
        FunctionNode(name="main", path="/tmp/graph-demo/app.py", language="Python")
    )
    project.add_relationship(
        RelationshipNode(
            source="main",
            target="helper",
            kind="calls",
            source_file="/tmp/graph-demo/app.py",
            evidence="DETECTED",
            source_location={"line": 4},
        )
    )
    project.add_import(
        ImportNode(
            source_file="/tmp/graph-demo/app.py",
            target="missing.module",
            language="Python",
            names=["missing.module"],
        )
    )

    graph = build_relation_graph(project)

    assert any(edge.kind == "calls" for edge in graph.edges)
    assert any(edge.kind == "imports" for edge in graph.edges)
    assert graph.unresolved
    assert "relation_graph" in project.metadata
    assert "relation_graph_unresolved" in project.metadata


def test_project_counts_and_evidence_summary_remain_consistent():
    project = Project(name="demo", root="/tmp/demo")
    file_node = FileNode(path="/tmp/demo/app.py", language="Python")
    project.add_file(file_node)
    project.add_file(FileNode(path="/tmp/demo/app.py", language="Python"))
    project.add_module(
        ModuleNode(name="app", path="/tmp/demo/app.py", language="Python")
    )
    project.add_relationship(
        RelationshipNode(
            source="com.example.A",
            target="com.example.B",
            kind="inherits",
            source_file="app.java",
            evidence="DECLARED",
        )
    )
    project.add_relationship(
        RelationshipNode(
            source="caller",
            target="callee",
            kind="calls",
            source_file="app.py",
            evidence="DETECTED",
            source_location={"line": 10},
        )
    )
    project.add_relationship(
        RelationshipNode(
            source="caller",
            target="callee",
            kind="calls",
            source_file="app.py",
            evidence="DETECTED",
            source_location={"line": 11},
        )
    )

    assert len(project.files) == 1
    assert len(project.modules) == 1
    assert len(project.relationships) == 2
    calls = next(rel for rel in project.relationships if rel.kind == "calls")
    assert calls.metadata["occurrences"] == [{"line": 10}, {"line": 11}]
    assert project.evidence_summary()["DECLARED"] == 1
    assert project.evidence_summary()["DETECTED"] == 1


def test_html_renderer_escapes_special_characters_and_empty_project(tmp_path):
    project = Project(name="<script>alert('boom')</script>", root=str(tmp_path))
    output_dir = tmp_path / "safe-site"
    render_project_website(project, output_dir)
    html_content = output_dir.joinpath("index.html").read_text(encoding="utf-8")
    assert (
        "&lt;script&gt;alert('boom')&lt;/script&gt;" in html_content
        or "&lt;script&gt;alert(&#x27;boom&#x27;)&lt;/script&gt;" in html_content
    )

    empty_project = Project(name="Empty", root=str(tmp_path / "empty"))
    empty_dir = tmp_path / "empty-site"
    render_project_website(empty_project, empty_dir)
    empty_html = empty_dir.joinpath("index.html").read_text(encoding="utf-8")
    assert "Empty" in empty_html
    assert "No classes were discovered." in empty_html
    assert "No functions were discovered." in empty_html


def test_html_renderer_uses_accessible_structure_and_evidence_labels(tmp_path):
    project = Project(name="Example", root=str(tmp_path))
    project.add_relationship(
        RelationshipNode(source="a", target="b", kind="calls", evidence="DETECTED")
    )
    project.add_relationship(
        RelationshipNode(source="b", target="c", kind="uses", evidence="INFERRED")
    )
    project.add_relationship(
        RelationshipNode(source="c", target="d", kind="references", evidence="UNKNOWN")
    )
    render_project_website(project, tmp_path / "accessible-site")
    html_text = (tmp_path / "accessible-site" / "index.html").read_text(
        encoding="utf-8"
    )
    assert (
        '<a class="skip-link" href="#main-content">Skip to main content</a>'
        in html_text
    )
    assert "Evidence and limits" in html_text
    assert "DETECTED" in html_text
    assert "INFERRED" in html_text
    assert "UNKNOWN" in html_text
    assert '<nav class="site-nav" aria-label="Main navigation">' in html_text


@pytest.mark.slow
def test_cli_can_generate_html_site(tmp_path):
    project_dir = tmp_path / "fixture"
    project_dir.mkdir()
    (project_dir / "example.py").write_text(
        "def run():\n    return 7\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "site-output"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            str(project_dir),
            "--name",
            "Fixture",
            "--output",
            str(output_dir),
            "--generate-only",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_dir.joinpath("index.html").exists()
    assert "HTML WEBSITE" in result.stdout


def test_cli_parser_supports_preview_flags():
    cli_main = importlib.import_module("cli.main")
    parser = cli_main.build_parser()
    args = parser.parse_args(
        [
            ".",
            "--serve",
            "--output",
            "site-output",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
        ]
    )

    assert args.serve is True
    assert args.output == Path("site-output")
    assert args.host == "127.0.0.1"
    assert args.port == 8123

    generate_only = parser.parse_args([".", "--generate-only"])
    assert generate_only.generate_only is True


def test_preview_page_validation_requires_index_file(tmp_path):
    cli_main = importlib.import_module("cli.main")

    with pytest.raises(FileNotFoundError):
        cli_main.validate_preview_landing_page(tmp_path / "missing")

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    assert cli_main.validate_preview_landing_page(site_dir) == site_dir / "index.html"


def test_build_preview_server_uses_localhost_and_port(monkeypatch, tmp_path):
    cli_main = importlib.import_module("cli.main")

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text(
        "<html><body>ok</body></html>", encoding="utf-8"
    )

    captured = {}

    class FakeHTTPServer:
        def __init__(self, server_address, handler):
            captured["server_address"] = server_address
            captured["handler"] = handler

        def server_close(self):
            captured["closed"] = True

    monkeypatch.setattr(cli_main, "ThreadingHTTPServer", FakeHTTPServer)
    server = cli_main.build_preview_server(site_dir, host="127.0.0.1", port=8123)

    assert isinstance(server, FakeHTTPServer)
    assert captured["server_address"] == ("127.0.0.1", 8123)


def test_relation_graph_connects_path_qualified_classes_to_all_methods(tmp_path):
    source = tmp_path / "tools.py"
    source.write_text(
        "class Tool:\n"
        "    def first(self):\n"
        "        return self.second()\n"
        "    def second(self):\n"
        "        return 1\n",
        encoding="utf-8",
    )
    project = Project(name="fixture", root=str(tmp_path))
    PythonReader().read(source, project)
    graph = build_relation_graph(
        project, view="relation_map", max_nodes=None, max_edges=None
    )

    class_id = f"Tool@{source}"
    method_ids = {f"Tool.first", "Tool.second"}
    edge_pairs = {(edge.source, edge.target, edge.kind) for edge in graph.edges}

    assert (class_id, "Tool.first", "contains") in edge_pairs
    assert (class_id, "Tool.second", "contains") in edge_pairs
    assert ("Tool.first", "Tool.second", "calls") in edge_pairs


def test_cli_no_longer_exposes_removed_structurizr_launcher():
    cli_main = importlib.import_module("cli.main")
    assert not hasattr(cli_main, "start_structurizr")
