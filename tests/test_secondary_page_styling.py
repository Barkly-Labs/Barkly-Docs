from rendering.html import CSS

def test_secondary_pages_reuse_index_design_tokens_and_controls():
    assert '/* Secondary pages use the same surfaces' in CSS
    assert '.subpage-header {' in CSS
    assert '.entity-explorer-tools, .relation-map-toolbar' in CSS
    assert 'background:rgba(15,15,16,.94)' in CSS
    assert 'box-shadow:0 10px 30px var(--shadow)' in CSS
    assert '.relation-map-filter-grid select' in CSS
    assert 'border-color:rgba(255,107,157,.55)' in CSS

def test_spider_map_keeps_responsive_layout_and_explorer_rules():
    assert '@media (max-width: 980px)' in CSS
    assert 'grid-template-columns: 1fr;' in CSS
    assert '@media (max-width: 600px)' in CSS
    assert '.entity-explorer-item[hidden] { display: none !important; }' in CSS


def test_generated_pages_load_the_same_emitted_stylesheet(tmp_path):
    """Regression: verify the generator output, not just the CSS constant."""
    from model.project import Project
    from rendering.html import render_project_website

    project = Project(name="Style fixture", root=str(tmp_path))
    render_project_website(project, tmp_path)

    emitted_css = (tmp_path / "assets" / "site.css").read_text(encoding="utf-8")
    assert emitted_css == CSS
    for filename in ("index.html", "entities.html", "relationships.html", "relation-map.html"):
        page = (tmp_path / filename).read_text(encoding="utf-8")
        assert '<link rel="stylesheet" href="assets/site.css" />' in page
        assert 'class="site-header"' in page
        assert 'class="site-nav"' in page
        assert '<main id="main-content" class="container">' in page

    assert 'class="subpage-header"' in (tmp_path / "entities.html").read_text(encoding="utf-8")
    assert 'data-entity-explorer' in (tmp_path / "entities.html").read_text(encoding="utf-8")
    assert 'class="subpage-header"' in (tmp_path / "relationships.html").read_text(encoding="utf-8")
    assert 'data-relationship-explorer' in (tmp_path / "relationships.html").read_text(encoding="utf-8")
    relation_map = (tmp_path / "relation-map.html").read_text(encoding="utf-8")
    assert 'class="subpage-header"' in relation_map
    assert 'id="relation-map-shell"' in relation_map
