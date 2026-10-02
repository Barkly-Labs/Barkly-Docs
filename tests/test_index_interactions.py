from __future__ import annotations

import re
from pathlib import Path

from model.project import ClassNode, FileNode, FunctionNode, Project, RelationshipNode
from rendering.html import render_project_website


def _project(tmp_path: Path) -> Project:
    project = Project(name="Index interactions", root=str(tmp_path))
    for i in range(8):
        project.add_function(FunctionNode(
            name=f"function_{i}",
            path=str(tmp_path / f"module_{i}.py"),
            language="Python",
            documentation=("needle beyond compact limit" if i == 7 else f"function description {i}"),
        ))
    project.add_class(ClassNode(name="Widget", path=str(tmp_path / "widget.py"), language="Python"))
    project.add_file(FileNode(path=str(tmp_path / "config.json"), language="JSON"))
    project.add_file(FileNode(path=str(tmp_path / "notes.txt"), language="Text"))
    project.add_relationship(RelationshipNode(source="function_0", target="function_1", kind="calls", evidence="DETECTED"))
    return project


def _index(tmp_path: Path) -> str:
    out = tmp_path / "site"
    render_project_website(_project(tmp_path), out)
    return (out / "index.html").read_text(encoding="utf-8")


def test_index_search_sections_keep_existing_cards_and_scoped_controls(tmp_path):
    html = _index(tmp_path)
    expected = ["classes", "functions", "methods", "modules", "endpoints", "dependencies", "relationships", "json", "other-project-files"]
    for slug in expected:
        assert f'id="index-section-{slug}"' in html
        assert f'id="search-{slug}"' in html
        assert f'id="index-list-{slug}"' in html
        assert f'aria-controls="index-list-{slug}"' in html
    assert 'class="index-section-card searchable-section"' in html
    assert 'class="card documentation-card"' in html
    assert 'class="architecture-layer architecture-layer-1"' in html


def test_index_search_uses_real_rendered_records_including_beyond_compact_limit(tmp_path):
    html = _index(tmp_path)
    assert 'function_7' in html
    assert 'needle beyond compact limit' in html
    assert 'const DEFAULT_VISIBLE = 5;' in html
    assert '.index-section-body .entity-item:nth-child(n+6)' in html
    assert 'const items = results ? [...results.querySelectorAll(".entity-list > .entity-item")] : [];' in html
    assert 'searchableText(item).includes(q)' in html
    assert 'body.classList.toggle("show-all", Boolean(q) || expanded);' in html


def test_index_search_hidden_state_cannot_be_overridden_by_card_layout_css(tmp_path):
    html = _index(tmp_path)
    assert '.index-section-body .entity-item[hidden]' in html
    assert 'display:none!important' in html


def test_index_search_clear_restores_compact_state_and_empty_state_recovers(tmp_path):
    html = _index(tmp_path)
    assert 'if (!q && hadQuery) expanded = false;' in html
    assert 'item.hidden = !match;' in html
    assert 'empty.hidden = matches !== 0;' in html
    assert 'class="index-no-results" role="status" hidden' in html
    assert 'more.hidden = !needsExpansion;' in html
    assert 'const norm = value => (value || "").toLowerCase().trim().replace(/\\s+/g, " ");' in html


def test_index_expand_controls_are_independent_and_accessible(tmp_path):
    html = _index(tmp_path)
    assert 'document.querySelectorAll(".searchable-section").forEach(section =>' in html
    assert 'let expanded = false;' in html
    assert 'more.setAttribute("aria-expanded", expanded ? "true" : "false")' in html
    assert 'more.textContent = expanded ? "Show less"' in html
    assert html.count('class="index-card-more" type="button" aria-expanded="false"') == 9


def test_index_ids_are_unique_and_nested_entity_actions_remain_intact(tmp_path):
    html = _index(tmp_path)
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids)), "generated index contains duplicate static IDs"
    assert 'class="entity-item entity-expandable"' in html
    assert 'class="entity-row-summary"' in html
    assert 'class="entity-expanded-view"' in html
