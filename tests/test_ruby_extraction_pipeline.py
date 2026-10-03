from pathlib import Path

from analysis.discovery import ProjectDiscovery
from analysis.graph import build_relation_graph
from readers.ruby import RubyReader
from rendering.html import render_project_website


def test_ruby_modules_classes_methods_locations_and_docs_survive_pipeline(tmp_path: Path):
    source = tmp_path / "lib" / "demo.rb"
    source.parent.mkdir()
    source.write_text(
        "# Demo namespace.\n"
        "module Demo\n"
        "  # Formats a name.\n"
        "  def format(name = 'world')\n"
        "    name\n"
        "  end\n\n"
        "  class Worker\n"
        "    # Runs one unit of work.\n"
        "    def run(value, flag: true)\n"
        "      value\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    result = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path, name="ruby-fixture")
    assert not result.errors
    project = result.project

    demo = next(module for module in project.modules if module.name == "Demo")
    worker = next(cls for cls in project.classes if cls.name == "Worker")
    format_method = next(method for method in project.methods if method.name == "format")
    run_method = next(method for method in project.methods if method.name == "run")

    assert demo.documentation == "Demo namespace."
    assert worker.metadata["parent"] == "Demo"
    assert format_method.class_name == "Demo"
    assert format_method.metadata["owner_kind"] == "module"
    assert format_method.documentation == "Formats a name."
    assert format_method.parameters == ["name = 'world'"]
    assert (format_method.line_start, format_method.line_end) == (4, 6)
    assert run_method.class_name == "Worker"
    assert run_method.documentation == "Runs one unit of work."
    assert run_method.parameters == ["value", "flag: true"]
    assert (run_method.line_start, run_method.line_end) == (10, 12)

    graph = build_relation_graph(project, view="detail", max_nodes=None, max_edges=None)
    assert any(node.id == "Demo.format" and node.kind == "method" for node in graph.nodes)
    assert any(node.id == "Worker.run" and node.kind == "method" for node in graph.nodes)

    out = tmp_path / "docs"
    render_project_website(project, out)
    entities = (out / "entities.html").read_text(encoding="utf-8")
    relationships = (out / "relationships.html").read_text(encoding="utf-8")
    relation_map = (out / "relation-map.html").read_text(encoding="utf-8")
    assert "Formats a name." in entities
    assert "Runs one unit of work." in entities
    assert "Demo.format" in relation_map
    assert "Worker.run" in relation_map
    assert "contains" in relationships


def test_ruby_module_extraction_does_not_duplicate_nested_class_methods(tmp_path: Path):
    source = tmp_path / "nested.rb"
    source.write_text(
        "module Outer\n"
        "  def module_method\n"
        "  end\n"
        "  class Inner\n"
        "    def class_method\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    project = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path).project
    owners = [(method.name, method.class_name) for method in project.methods]
    assert owners.count(("module_method", "Outer")) == 1
    assert owners.count(("class_method", "Inner")) == 1
    assert ("class_method", "Outer") not in owners


def test_ruby_class_and_singleton_methods_keep_ownership_parameters_and_locations(tmp_path: Path):
    source = tmp_path / "ownership.rb"
    source.write_text(
        "module Outer\n"
        "  module Inner\n"
        "    class Worker\n"
        "      # Instance docs.\n"
        "      def perform item, count = 1, flag: true, *rest, **options, &block\n"
        "        item\n"
        "      end\n"
        "\n"
        "      # Builder docs.\n"
        "      def self.build(name:)\n"
        "        new\n"
        "      end\n"
        "\n"
        "      class << self\n"
        "        # Config docs.\n"
        "        def configure(level: :info)\n"
        "          level\n"
        "        end\n"
        "      end\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    project = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path).project
    methods = {method.name: method for method in project.methods}

    perform = methods["perform"]
    assert perform.class_name == "Worker"
    assert perform.metadata["qualified_name"] == "Outer::Inner::Worker.perform"
    assert perform.metadata["singleton"] is False
    assert perform.documentation == "Instance docs."
    assert perform.parameters == [
        "item", "count = 1", "flag: true", "*rest", "**options", "&block"
    ]
    assert (perform.line_start, perform.line_end) == (5, 7)

    build = methods["build"]
    assert build.class_name == "Worker"
    assert build.metadata["qualified_name"] == "Outer::Inner::Worker.build"
    assert build.metadata["singleton"] is True
    assert build.metadata["receiver"] == "self"
    assert build.documentation == "Builder docs."
    assert (build.line_start, build.line_end) == (10, 12)

    configure = methods["configure"]
    assert configure.class_name == "Worker"
    assert configure.metadata["qualified_name"] == "Outer::Inner::Worker.configure"
    assert configure.metadata["singleton"] is True
    assert configure.metadata["receiver"] == "self"
    assert configure.documentation == "Config docs."
    assert (configure.line_start, configure.line_end) == (16, 18)

    owners = [(method.name, method.class_name) for method in project.methods]
    assert owners.count(("perform", "Worker")) == 1
    assert owners.count(("build", "Worker")) == 1
    assert owners.count(("configure", "Worker")) == 1
    assert ("perform", "Inner") not in owners
    assert ("configure", "Outer") not in owners

    graph = build_relation_graph(project, view="detail", max_nodes=None, max_edges=None)
    node_ids = {node.id for node in graph.nodes}
    assert "Outer::Inner::Worker.perform" in node_ids
    assert "Outer::Inner::Worker.build" in node_ids
    assert "Outer::Inner::Worker.configure" in node_ids

    out = tmp_path / "docs"
    render_project_website(project, out)
    entities = (out / "entities.html").read_text(encoding="utf-8")
    relation_map = (out / "relation-map.html").read_text(encoding="utf-8")
    assert "Instance docs." in entities
    assert "Builder docs." in entities
    assert "Config docs." in entities
    assert "Outer::Inner::Worker.perform" in relation_map
    assert "Outer::Inner::Worker.configure" in relation_map


def test_ruby_module_methods_do_not_absorb_nested_module_or_class_methods(tmp_path: Path):
    source = tmp_path / "nested_owners.rb"
    source.write_text(
        "module Outer\n"
        "  def outer_method\n  end\n"
        "  module Inner\n"
        "    def inner_method\n    end\n"
        "    class Worker\n"
        "      def work\n      end\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    project = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path).project
    owners = [(method.name, method.class_name) for method in project.methods]
    assert owners.count(("outer_method", "Outer")) == 1
    assert owners.count(("inner_method", "Inner")) == 1
    assert owners.count(("work", "Worker")) == 1
    assert ("inner_method", "Outer") not in owners
    assert ("work", "Outer") not in owners
    assert ("work", "Inner") not in owners

    inner = next(method for method in project.methods if method.name == "inner_method")
    work = next(method for method in project.methods if method.name == "work")
    assert inner.metadata["qualified_name"] == "Outer::Inner.inner_method"
    assert work.metadata["qualified_name"] == "Outer::Inner::Worker.work"


def test_ruby_empty_and_partial_input_is_handled_conservatively(tmp_path: Path):
    empty = tmp_path / "empty.rb"
    empty.write_text("", encoding="utf-8")
    partial = tmp_path / "partial.rb"
    partial.write_text("class Partial\n  def unfinished(value)\n    value\n", encoding="utf-8")

    result = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path)
    assert not result.errors
    unfinished = next(method for method in result.project.methods if method.name == "unfinished")
    assert unfinished.class_name == "Partial"
    assert unfinished.parameters == ["value"]
    assert unfinished.line_start == 2
    assert unfinished.line_end == 3


def test_ruby_yard_documentation_is_structured_and_rendered(tmp_path: Path):
    source = tmp_path / "documented.rb"
    source.write_text(
        "# File overview for maintainers.\n"
        "# This explains the source file.\n"
        "\n"
        "# Public API namespace.\n"
        "module PublicApi\n"
        "  # Handles a request.\n"
        "  # @param name [String] caller name\n"
        "  # @param options [Hash] request options\n"
        "  # @return [String, nil] rendered greeting\n"
        "  # @raise [ArgumentError] when name is empty\n"
        "  # @deprecated Use #greet instead.\n"
        "  def hello(name, options = {})\n"
        "    name\n"
        "  end\n"
        "\n"
        "  # Worker documentation.\n"
        "  class Worker\n"
        "    # Builds a worker.\n"
        "    # @return [Worker] a worker instance\n"
        "    def self.build\n"
        "      new\n"
        "    end\n"
        "\n"
        "    def undocumented(value)\n"
        "      # ordinary implementation comment\n"
        "      value\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    project = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path).project
    public_api = next(item for item in project.modules if item.name == "PublicApi")
    worker = next(item for item in project.classes if item.name == "Worker")
    hello = next(item for item in project.methods if item.name == "hello")
    build = next(item for item in project.methods if item.name == "build")
    undocumented = next(item for item in project.methods if item.name == "undocumented")

    assert public_api.documentation == "Public API namespace."
    assert worker.documentation == "Worker documentation."
    assert hello.documentation.startswith("Handles a request.\n@param name [String]")
    assert hello.metadata["documentation_line_start"] == 6
    assert hello.metadata["documentation_line_end"] == 11
    assert hello.metadata["documentation_evidence"] == "DECLARED"
    assert hello.metadata["yard"] == {
        "params": [
            {"name": "name", "types": ["String"], "description": "caller name"},
            {"name": "options", "types": ["Hash"], "description": "request options"},
        ],
        "returns": [{"types": ["String", "nil"], "description": "rendered greeting"}],
        "raises": [{"types": ["ArgumentError"], "description": "when name is empty"}],
        "deprecated": ["Use #greet instead."],
    }
    assert build.metadata["yard"]["returns"][0]["types"] == ["Worker"]
    assert undocumented.documentation is None
    assert "ordinary implementation comment" not in str(undocumented.metadata)

    file_docs = [doc for doc in project.documentation if doc.kind == "ruby_file_documentation"]
    assert len(file_docs) == 1
    assert file_docs[0].documentation == "File overview for maintainers.\nThis explains the source file."
    assert file_docs[0].metadata["line_start"] == 1
    assert file_docs[0].metadata["line_end"] == 2
    assert file_docs[0].metadata["raw_text"].startswith("# File overview")

    out = tmp_path / "docs"
    render_project_website(project, out)
    entities = (out / "entities.html").read_text(encoding="utf-8")
    assert "Handles a request." in entities
    assert "@param name [String] caller name" in entities
    assert "@return [String, nil] rendered greeting" in entities
    assert "@raise [ArgumentError] when name is empty" in entities
    assert "@deprecated Use #greet instead." in entities
    assert "File overview for maintainers." in entities
    assert '<strong class="entity-row-name">File overview for maintainers.</strong>' in entities
    assert '<span>Ruby</span>' in entities
    assert f"{source}:1–2" in entities
    # The source preview may legitimately show implementation comments; they
    # must not become the method's documentation/search description.
    assert undocumented.documentation is None


def test_ruby_documentation_association_ignores_detached_and_malformed_tags(tmp_path: Path):
    source = tmp_path / "association.rb"
    source.write_text(
        "# Detached note that is not declaration documentation.\n"
        "\n"
        "module Example\n"
        "  # Correct method docs.\n"
        "  # @param malformed\n"
        "  # @return [String\n"
        "  def call(value)\n"
        "    value\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    project = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path).project
    example = next(item for item in project.modules if item.name == "Example")
    call = next(item for item in project.methods if item.name == "call")

    assert example.documentation is None
    assert call.documentation == "Correct method docs.\n@param malformed\n@return [String"
    assert call.metadata["yard"]["params"] == [
        {"name": "malformed", "types": [], "description": ""}
    ]
    assert "returns" not in call.metadata["yard"]
