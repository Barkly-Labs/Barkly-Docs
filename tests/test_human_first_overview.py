from pathlib import Path

from analysis.discovery import ProjectDiscovery
from readers.ruby import RubyReader
from rendering.html import render_project_website


def test_missing_readme_still_gets_source_backed_orientation_through_real_pipeline(tmp_path: Path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (tmp_path / "main.rb").write_text(
        "require_relative 'lib/worker'\n"
        "module Demo\n"
        "  # Starts one unit of work.\n"
        "  def self.start(name:)\n"
        "    name\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (lib / "worker.rb").write_text(
        "module Demo\n"
        "  class Worker\n"
        "    # Performs work.\n"
        "    def perform(value)\n"
        "      value\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    result = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path, name="No README fixture")
    assert not result.errors
    project = result.project
    assert not (tmp_path / "README.md").exists()
    assert any(module.name == "Demo" for module in project.modules)
    assert any(cls.name == "Worker" for cls in project.classes)
    assert any(rel.kind == "imports" for rel in project.relationships)

    output = tmp_path / "docs"
    render_project_website(project, output)
    index = (output / "index.html").read_text(encoding="utf-8")
    entities = (output / "entities.html").read_text(encoding="utf-8")
    relationships = (output / "relationships.html").read_text(encoding="utf-8")
    relation_map = (output / "relation-map.html").read_text(encoding="utf-8")

    assert "Source-backed orientation" in index
    assert "README not discovered" in index
    assert "conventional entry-point candidate" in index
    assert "main.rb" in index
    assert "modules: Demo" in index
    assert "classes: Worker" in index
    assert "does not imply that the target project was executed" in index
    assert "Starts one unit of work." in entities
    assert "Performs work." in entities
    assert "imports" in relationships
    assert "Worker.perform" in relation_map


def test_overview_does_not_invent_entry_points_or_dependencies(tmp_path: Path):
    (tmp_path / "utility.rb").write_text(
        "module Utility\n"
        "  def normalize(value)\n"
        "    value\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    project = ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path, name="Utility").project
    output = tmp_path / "docs"
    render_project_website(project, output)
    index = (output / "index.html").read_text(encoding="utf-8")

    assert "No conventional entry point, route, or endpoint was established" in index
    assert "No project dependencies were established" in index
    assert "modules: Utility" in index
    assert "Project purpose unknown." in index
