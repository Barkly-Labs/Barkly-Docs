from __future__ import annotations

from bs4 import BeautifulSoup

from model.project import Project, RelationshipNode
from rendering.relationships_page import render_relationships_page
from rendering.html import render_project_website


def _project(tmp_path):
    project = Project(name="Relationship Fixture", root=str(tmp_path))
    project.relationships.extend([
        RelationshipNode(source="api.create", target="services.save", kind="calls", source_file="src/api.py", evidence="DETECTED", source_location={"line": 12}, metadata={"symbol": "save"}),
        RelationshipNode(source="api.create", target="models.Item", kind="imports", source_file="src/api.py", evidence="DECLARED", source_location={"line": 2}, metadata={"import_text": "models.Item"}),
        RelationshipNode(source="web.route", target="api.create", kind="routes_to", source_file="src/routes.rb", evidence="DETECTED", source_location={"line": 8}),
    ])
    return project


def test_relationships_page_matches_entity_explorer_structure_and_searches_full_data(tmp_path):
    soup = BeautifulSoup(render_relationships_page(_project(tmp_path)), "html.parser")
    assert soup.select_one("[data-relationship-explorer]") is not None
    assert soup.select_one("#relationship-search") is not None
    assert soup.select_one("#relationship-kind-filter") is not None
    cards = soup.select(".relationship-explorer-item.entity-explorer-item")
    assert len(cards) == 3
    call = next(card for card in cards if card["data-relationship-kind"] == "calls")
    haystack = call["data-relationship-search"]
    assert "api.create" in haystack
    assert "services.save" in haystack
    assert "src/api.py" in haystack
    assert "save" in haystack


def test_search_filter_count_empty_state_and_clear_are_wired_together(tmp_path):
    soup = BeautifulSoup(render_relationships_page(_project(tmp_path)), "html.parser")
    assert soup.select_one(".relationship-search-status").get_text(" ", strip=True) == "3 relationships"
    assert soup.select_one(".relationship-search-empty").has_attr("hidden")
    clear = soup.select_one(".relationship-search-clear")
    assert clear["aria-label"] == "Clear relationship search"
    script = soup.find("script").string
    assert "queryMatches && kindMatches" in script
    assert "kind.addEventListener('change', update)" in script
    assert "input.value = ''" in script and "kind.value = ''" in script
    assert "item.hidden = !visible" in script


def test_relationship_disclosures_are_accessible_and_details_preserve_evidence(tmp_path):
    soup = BeautifulSoup(render_relationships_page(_project(tmp_path)), "html.parser")
    ids = [card["id"] for card in soup.select(".relationship-explorer-item")]
    assert len(ids) == len(set(ids))
    for card in soup.select(".relationship-explorer-item"):
        button = card.select_one("button.relationship-disclosure-button")
        assert button["type"] == "button"
        assert button["aria-expanded"] == "false"
        panel = soup.find(id=button["aria-controls"])
        assert panel is not None and panel.has_attr("hidden")
    text = soup.get_text(" ", strip=True)
    assert "DETECTED" in text and "DECLARED" in text
    assert "line 12" in text
    assert "models.Item" in text


def test_unresolved_relationship_text_is_preserved_not_hidden(tmp_path):
    project = Project(name="Unresolved", root=str(tmp_path))
    project.relationships.append(RelationshipNode(source="caller", target="unresolved:dynamic_target", kind="calls", evidence="UNKNOWN", metadata={"resolution": "unresolved"}))
    soup = BeautifulSoup(render_relationships_page(project), "html.parser")
    assert "unresolved:dynamic_target" in soup.get_text()
    assert "UNKNOWN" in soup.get_text()
    assert "unresolved" in soup.select_one(".relationship-explorer-item")["data-relationship-search"]


def test_empty_relationship_page_has_truthful_empty_state(tmp_path):
    soup = BeautifulSoup(render_relationships_page(Project(name="Empty", root=str(tmp_path))), "html.parser")
    assert "No relationships were discovered in the shared relationship model." in soup.get_text()
    assert soup.select_one(".relationship-search-status").get_text(" ", strip=True) == "0 relationships"


def test_generated_site_preserves_entities_and_relation_map(tmp_path):
    project = _project(tmp_path)
    output = tmp_path / "site"
    render_project_website(project, output)
    relationships = (output / "relationships.html").read_text(encoding="utf-8")
    entities = (output / "entities.html").read_text(encoding="utf-8")
    assert "Search project relationships" in relationships
    assert "relationship-kind-filter" in relationships
    assert "Open relationship map" in relationships
    assert "Search project entities" in entities
    assert (output / "relation-map.html").is_file()
    assert (output / "assets" / "relation-map.js").is_file()
