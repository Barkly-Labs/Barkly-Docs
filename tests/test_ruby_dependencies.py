from pathlib import Path

from analysis.discovery import ProjectDiscovery
from analysis.graph import build_relation_graph
from model.project import Project
from readers.ruby import RubyReader
from rendering.html import render_project_website


def _scan(root: Path) -> Project:
    return ProjectDiscovery(readers=[RubyReader()]).analyze(root).project


def test_ruby_manifests_and_requires_survive_full_pipeline(tmp_path: Path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "Gemfile").write_text("gem 'rack', '~> 3.0'\ngem 'rspec', group: :test\n", encoding="utf-8")
    (tmp_path / "demo.gemspec").write_text(
        "Gem::Specification.new do |spec|\n"
        "  spec.add_dependency 'thor', '>= 1.0'\n"
        "  spec.add_development_dependency 'rake', '~> 13.0'\n"
        "end\n", encoding="utf-8")
    (tmp_path / "Gemfile.lock").write_text(
        "GEM\n  specs:\n    rack (3.0.8)\n    rspec (3.13.0)\n\nDEPENDENCIES\n  rack (~> 3.0)\n  rspec\n",
        encoding="utf-8",
    )
    (tmp_path / "lib" / "helper.rb").write_text("module Helper\nend\n", encoding="utf-8")
    (tmp_path / "app.rb").write_text(
        "require 'json'\nrequire 'rack'\nrequire_relative 'lib/helper'\n", encoding="utf-8"
    )

    project = _scan(tmp_path)
    dependencies = {(d.name, d.kind, d.metadata.get("manifest")) for d in project.dependencies}
    assert ("rack", "runtime", "Gemfile") in dependencies
    assert ("thor", "runtime", "demo.gemspec") in dependencies
    assert ("rake", "development", "demo.gemspec") in dependencies
    assert ("rack", "locked", "Gemfile.lock") in dependencies

    graph = build_relation_graph(project, view="detail", max_nodes=None, max_edges=None)
    app_imports = [i for i in project.imports if Path(i.source_file).name == "app.rb"]
    scopes = {i.target: i.metadata.get("dependency_scope") for i in app_imports}
    assert scopes["json"] == "standard_library"
    assert scopes["rack"] == "external_gem"
    assert scopes["lib/helper"] == "internal_project"

    assert any(n.id == "dependency:ruby:rack" and n.kind == "dependency" for n in graph.nodes)
    assert any(e.kind == "imports" and e.target == "dependency:ruby:rack" for e in graph.edges)
    assert not any(e.kind == "imports" and e.target == "json" for e in graph.edges)
    assert any(e.kind == "imports" and "helper" in e.target for e in graph.edges)
    assert any(e.kind == "depends_on" and e.target == "dependency:ruby:rack" for e in graph.edges)

    out = tmp_path / "docs"
    render_project_website(project, out)
    index = (out / "index.html").read_text(encoding="utf-8")
    relationships = (out / "relationships.html").read_text(encoding="utf-8")
    assert "rack" in index
    assert "depends_on" in relationships
    assert "external_gem" in relationships


def test_ruby_dependency_negative_cases_do_not_invent_dependencies(tmp_path: Path):
    (tmp_path / "Gemfile").write_text(
        "# gem 'commented-out'\nsource 'https://example.invalid'\n",
        encoding="utf-8",
    )
    (tmp_path / "app.rb").write_text(
        "# require 'fake'\ntext = \"require 'also_fake'\"\nrequire 'set'\n",
        encoding="utf-8",
    )
    project = _scan(tmp_path)
    assert not project.dependencies
    assert [i.target for i in project.imports] == ["set"]
    graph = build_relation_graph(project, view="detail", max_nodes=None, max_edges=None)
    assert project.imports[0].metadata.get("dependency_scope") == "standard_library"
    assert not any(e.kind in {"imports", "depends_on"} and e.target in {"set", "fake", "also_fake"} for e in graph.edges)
