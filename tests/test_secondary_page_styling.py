from rendering.html import CSS

def test_secondary_pages_reuse_index_design_tokens_and_controls():
    assert '/* Secondary pages use the same surfaces' in CSS
    assert '.subpage-header {' in CSS
    assert '.entity-explorer-tools, .relation-map-toolbar' in CSS
    assert 'background:rgba(15,15,16,.94)' in CSS
    assert 'box-shadow:0 10px 30px var(--shadow)' in CSS
    assert '.relation-map-filter-grid select' in CSS
    assert 'border-color:rgba(255,107,157,.55)' in CSS
    assert '.entity-explorer-section.card { padding:28px; }' in CSS
    assert '#relation-map-shell > * { min-width: 0; }' in CSS
    assert '.entity-row-name { min-width: 0; overflow-wrap: anywhere;' in CSS
    assert '.relation-map-actions > button { flex:1 1 140px; }' in CSS
    assert '.relation-map-accessible button { max-width:100%; overflow-wrap:anywhere;' in CSS

def test_spider_map_keeps_responsive_layout_and_explorer_rules():
    assert '@media (max-width: 980px)' in CSS
    assert 'grid-template-columns: 1fr;' in CSS
    assert '@media (max-width: 600px)' in CSS
    assert '.entity-explorer-item[hidden] { display: none !important; }' in CSS

def test_generated_pages_share_emitted_stylesheet_and_shell(tmp_path):
    """Regression: generated pages must use the emitted shared shell and CSS."""
    from model.project import Project
    from rendering.html import render_project_website

    project = Project(name="Style fixture", root=str(tmp_path))
    render_project_website(project, tmp_path)

    emitted_css = (tmp_path / "assets" / "site.css").read_text(encoding="utf-8")
    assert emitted_css == CSS

    pages = {}
    for filename in ("index.html", "entities.html", "relationships.html", "relation-map.html"):
        page = (tmp_path / filename).read_text(encoding="utf-8")
        pages[filename] = page
        assert '<link rel="stylesheet" href="assets/site.css" />' in page
        assert 'class="site-header"' in page
        assert 'class="site-nav"' in page
        assert '<main id="main-content" class="container">' in page

    assert 'class="subpage-header card"' in pages["entities.html"]
    assert 'class="section entity-explorer-section card"' in pages["entities.html"]
    assert 'data-entity-explorer' in pages["entities.html"]
    assert 'class="subpage-header card"' in pages["relationships.html"]
    assert 'data-relationship-explorer' in pages["relationships.html"]
    assert 'class="subpage-header card"' in pages["relation-map.html"]
    assert 'id="relation-map-shell"' in pages["relation-map.html"]
