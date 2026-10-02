from __future__ import annotations

import time
from bs4 import BeautifulSoup

from model.project import ClassNode, FunctionNode, MethodNode, ModuleNode, Project
from rendering.entities_page import render_entities_page
from rendering.html import render_project_website


def _project(tmp_path):
    first = tmp_path / "alpha.py"
    second = tmp_path / "beta.py"
    first.write_text('class Widget:\n    """Primary widget."""\n    def run(self, value):\n        return value\n', encoding="utf-8")
    second.write_text('class Widget:\n    """Secondary widget."""\n    pass\n', encoding="utf-8")
    project = Project(name="Explorer Fixture", root=str(tmp_path))
    project.classes.extend([
        ClassNode(name="Widget", path=str(first), language="Python", methods=["run"], documentation="Primary widget.", line_start=1, line_end=4, metadata={"module":"alpha"}),
        ClassNode(name="Widget", path=str(second), language="Python", documentation="Secondary widget.", line_start=1, line_end=3, metadata={"module":"beta"}),
    ])
    project.methods.append(MethodNode(name="run", class_name="Widget", path=str(first), language="Python", parameters=["self", "value"], return_type="str", documentation="Return the supplied value.", line_start=3, line_end=4, metadata={"qualified_name":"alpha.Widget.run", "module":"alpha"}))
    project.functions.append(FunctionNode(name="helper", path=str(first), language="Python", parameters=["item"], documentation="Normalize an item.", line_start=1, metadata={"qualified_name":"alpha.helper", "module":"alpha"}))
    project.modules.append(ModuleNode(name="alpha", path=str(first), language="Python", documentation="Alpha module."))
    return project


def test_entities_page_has_searchable_data_for_name_path_type_and_fqn(tmp_path):
    soup = BeautifulSoup(render_entities_page(_project(tmp_path)), "html.parser")
    search = soup.find("input", {"type":"search", "id":"entity-search"})
    assert search is not None
    cards = soup.select(".entity-explorer-item")
    assert len(cards) == 5
    run = next(card for card in cards if card.select_one(".entity-row-name").get_text(strip=True) == "run")
    haystack = run["data-entity-search"]
    assert "run" in haystack
    assert "method" in haystack
    assert "alpha.py" in haystack
    assert "alpha.widget.run" in haystack
    assert "return the supplied value" in haystack
    assert "run(self, value) -> str" in haystack


def test_empty_query_no_results_and_clear_search_controls_are_present(tmp_path):
    soup = BeautifulSoup(render_entities_page(_project(tmp_path)), "html.parser")
    status = soup.select_one(".entity-search-status")
    assert status.get_text(" ", strip=True) == "5 entities"
    assert soup.select_one(".entity-search-empty").has_attr("hidden")
    clear = soup.select_one(".entity-search-clear")
    assert clear["aria-label"] == "Clear entity search"
    script = soup.find("script").string
    assert "input.value.trim().toLocaleLowerCase()" in script
    assert "item.hidden = !visible" in script
    assert "input.value = ''" in script


def test_disclosures_are_keyboard_accessible_buttons_with_stable_unique_ids(tmp_path):
    soup = BeautifulSoup(render_entities_page(_project(tmp_path)), "html.parser")
    cards = soup.select(".entity-explorer-item")
    ids = [card["id"] for card in cards]
    assert len(ids) == len(set(ids))
    for card in cards:
        button = card.select_one("button.entity-disclosure-button")
        assert button["type"] == "button"
        assert button["aria-expanded"] == "false"
        panel = soup.find(id=button["aria-controls"])
        assert panel is not None and panel.has_attr("hidden")
    script = soup.find("script").string
    assert "setAttribute('aria-expanded'" in script
    assert "panel.hidden = expanded" in script


def test_duplicate_names_remain_distinct_and_keep_source_context(tmp_path):
    soup = BeautifulSoup(render_entities_page(_project(tmp_path)), "html.parser")
    widgets = [card for card in soup.select(".entity-explorer-item") if card.select_one(".entity-row-name").get_text(strip=True) == "Widget"]
    assert len(widgets) == 2
    assert widgets[0]["id"] != widgets[1]["id"]
    paths = {card.select_one(".entity-explorer-meta span").get_text(strip=True) for card in widgets}
    assert str(tmp_path / "alpha.py") in paths
    assert str(tmp_path / "beta.py") in paths


def test_expanded_details_use_existing_description_signature_location_members_and_evidence(tmp_path):
    soup = BeautifulSoup(render_entities_page(_project(tmp_path)), "html.parser")
    run = next(card for card in soup.select(".entity-explorer-item") if card.select_one(".entity-row-name").get_text(strip=True) == "run")
    detail = run.select_one(".entity-expanded-view")
    text = detail.get_text(" ", strip=True)
    assert "Return the supplied value." in text
    assert "run(self, value) -> str" in text
    assert f"{tmp_path / 'alpha.py'}:3–4" in text
    assert "DETECTED" in text
    widget = next(card for card in soup.select(".entity-explorer-item") if "Primary widget." in card.get_text())
    assert "run" in widget.select_one(".entity-members").get_text()
    assert "Source preview" in widget.get_text()


def test_missing_description_is_neutral_not_invented(tmp_path):
    project = Project(name="No docs", root=str(tmp_path))
    project.functions.append(FunctionNode(name="plain", path="plain.py"))
    soup = BeautifulSoup(render_entities_page(project), "html.parser")
    assert "No description available yet." in soup.get_text()


def test_search_index_exists_even_while_details_are_collapsed(tmp_path):
    soup = BeautifulSoup(render_entities_page(_project(tmp_path)), "html.parser")
    helper = next(card for card in soup.select(".entity-explorer-item") if card.select_one(".entity-row-name").get_text(strip=True) == "helper")
    assert helper.select_one(".entity-expanded-view").has_attr("hidden")
    assert "normalize an item" in helper["data-entity-search"]


def test_large_collection_generation_is_linear_enough_for_static_page(tmp_path):
    project = Project(name="Large", root=str(tmp_path))
    project.functions = [FunctionNode(name=f"function_{i}", path=f"src/module_{i % 20}.py", documentation=f"Entity {i}") for i in range(2000)]
    started = time.perf_counter()
    page = render_entities_page(project)
    elapsed = time.perf_counter() - started
    assert page.count('class="entity-explorer-item entity-item"') == 2000
    assert elapsed < 3.0


def test_full_site_preserves_other_pages_and_relation_map(tmp_path):
    project = _project(tmp_path)
    (tmp_path / "README.md").write_text("# Explorer Fixture\n\nREADME remains visible.\n", encoding="utf-8")
    output = tmp_path / "site"
    render_project_website(project, output)
    entities = (output / "entities.html").read_text(encoding="utf-8")
    index = (output / "index.html").read_text(encoding="utf-8")
    assert "Search project entities" in entities
    assert "README remains visible." in index
    assert (output / "relationships.html").is_file()
    assert (output / "relation-map.html").is_file()
    assert (output / "assets" / "relation-map.js").is_file()
