from model.project import Project
import rendering.html as renderer


def test_readme_parser_preserves_safe_html_without_optional_markdown_libs(tmp_path, monkeypatch):
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'logo.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding='utf-8')
    (tmp_path / 'README.md').write_text(
        '# Demo\n\n<p align="center"><img src="docs/logo.svg" alt="Demo" onerror="alert(1)"><br>'
        '<a href="https://example.com">Project link</a></p>\n\n'
        '## Installation\n\n**Safe** text.\n<script>alert("bad")</script>\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(renderer, 'MarkdownIt', None)
    monkeypatch.setattr(renderer, 'bleach', None)
    project = Project(name='Demo', root=str(tmp_path))
    out = tmp_path / 'site'
    renderer.render_project_website(project, out)
    page = (out / 'index.html').read_text(encoding='utf-8')

    readme = page.split('<div class="readme-content">', 1)[1].split('</article>', 1)[0]
    assert '&lt;p align=' not in readme
    assert '<img src="assets/readme/docs/logo.svg" alt="Demo">' in readme
    assert '<a href="https://example.com">Project link</a>' in readme
    assert 'onerror=' not in readme
    assert '<script>' not in readme
    assert '<strong>Safe</strong>' in readme
    assert (out / 'assets' / 'readme' / 'docs' / 'logo.svg').exists()


def test_existing_main_page_sections_and_order_are_preserved(tmp_path):
    (tmp_path / 'README.md').write_text('# Demo\n\nREADME body.\n', encoding='utf-8')
    project = Project(name='Demo', root=str(tmp_path))
    out = tmp_path / 'site'
    renderer.render_project_website(project, out)
    page = (out / 'index.html').read_text(encoding='utf-8')

    expected = ['Classes', 'Functions', 'Methods', 'Modules', 'Dependencies', 'Relationships', 'JSON', 'Other project files']
    positions = [page.index(f'<h2>{title}</h2>') for title in expected]
    assert positions == sorted(positions)
    assert 'Project documentation context' not in page
