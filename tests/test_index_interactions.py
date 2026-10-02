from __future__ import annotations

import re
from pathlib import Path

from model.project import ClassNode, FileNode, FunctionNode, Project, RelationshipNode
from rendering.html import render_project_website


def _project(tmp_path: Path) -> Project:
    project = Project(name="Index interactions", root=str(tmp_path))
    for i in range(14):
        project.add_function(FunctionNode(name=f"function_{i}", path=str(tmp_path / f"module_{i}.py"), language="Python"))
    project.add_class(ClassNode(name="Widget", path=str(tmp_path / "widget.py"), language="Python"))
    project.add_file(FileNode(path=str(tmp_path / "config.json"), language="JSON"))
    project.add_file(FileNode(path=str(tmp_path / "notes.txt"), language="Text"))
    project.add_relationship(RelationshipNode(source="function_0", target="function_1", kind="calls", evidence="DETECTED"))
    return project


def _index(tmp_path: Path) -> str:
    out = tmp_path / "site"
    render_project_website(_project(tmp_path), out)
    return (out / "index.html").read_text(encoding="utf-8")


def test_index_search_sections_have_scoped_accessible_controls(tmp_path):
    html = _index(tmp_path)
    expected = ["classes", "functions", "methods", "modules", "endpoints", "dependencies", "relationships", "json", "other-project-files"]
    for slug in expected:
        assert f'id="index-section-{slug}"' in html
        assert f'id="search-{slug}"' in html
        assert f'aria-controls="index-list-{slug}"' in html
    assert html.count('class="index-card-clear"') == len(expected)
    assert 'const items = results ? [...results.querySelectorAll(".entity-list > .entity-item")] : [];' in html
    assert 'document.querySelectorAll(".searchable-section").forEach(section =>' in html


def test_index_search_logic_preserves_section_scope_clear_and_empty_state(tmp_path):
    html = _index(tmp_path)
    assert 'searchableText(item).includes(q)' in html
    assert 'item.hidden = !match' in html
    assert 'input.value = "";' in html
    assert 'empty.hidden = matches !== 0;' in html
    assert 'class="index-no-results" role="status" hidden' in html
    assert 'body.classList.toggle("show-all", Boolean(q) || expanded);' in html
    assert 'clear.disabled = !q;' in html
    # No global entity query: filtering is rooted in each section's result container.
    assert 'document.querySelectorAll(".entity-list > .entity-item")' not in html


def test_index_show_more_and_disclosures_expose_accessible_state(tmp_path):
    html = _index(tmp_path)
    assert 'class="index-card-more" type="button"' in html
    assert 'aria-expanded="false"' in html
    assert 'more.setAttribute("aria-expanded", expanded ? "true" : "false")' in html
    assert 'details.addEventListener("toggle", syncDisclosure)' in html
    assert 'summary.setAttribute("aria-expanded", details.open ? "true" : "false")' in html
    assert 'summary.setAttribute("aria-controls", content.id)' in html


def test_index_ids_are_unique_and_nested_entity_disclosures_remain_intact(tmp_path):
    html = _index(tmp_path)
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids)), "generated index contains duplicate static IDs"
    assert html.count('class="entity-item entity-expandable"') >= 15
    assert 'class="entity-row-summary"' in html
    assert 'class="entity-expanded-view"' in html
    assert 'class="card documentation-card"' in html
    assert 'class="architecture-layer architecture-layer-1"' in html
