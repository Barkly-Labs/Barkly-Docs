
from __future__ import annotations

from bs4 import BeautifulSoup

from model.project import Project
import rendering.html as html_renderer


SINATRA_BADGES = """\
[![Gem Version](https://badge.fury.io/rb/sinatra.svg)](https://badge.fury.io/rb/sinatra)

[![Testing](https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg)](https://github.com/sinatra/sinatra/actions/workflows/test.yml)
"""


def _render(markdown: str) -> str:
    rendered = html_renderer._render_markdown_established(markdown)
    assert rendered is not None, "Established Markdown renderer is required by requirements-readme.txt"
    return rendered


def test_linked_image_badges_render_as_clickable_images():
    soup = BeautifulSoup(_render(SINATRA_BADGES), "html.parser")
    anchors = soup.find_all("a")
    assert [(a.get("href"), a.img.get("src"), a.img.get("alt")) for a in anchors] == [
        ("https://badge.fury.io/rb/sinatra", "https://badge.fury.io/rb/sinatra.svg", "Gem Version"),
        (
            "https://github.com/sinatra/sinatra/actions/workflows/test.yml",
            "https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg",
            "Testing",
        ),
    ]


def test_common_markdown_features_and_parenthesized_urls():
    markdown = """\
# Heading

A [link](https://example.com/a(b)) and ![image](https://example.com/img(a).png).

- one
- two

`inline` and *emphasis* and <i>italic text</i>.

```python
print("<safe>")
```
"""
    soup = BeautifulSoup(_render(markdown), "html.parser")
    assert soup.h1.get_text() == "Heading"
    assert soup.find("a", href="https://example.com/a(b)")
    assert soup.find("img", src="https://example.com/img(a).png", alt="image")
    assert [li.get_text() for li in soup.find_all("li")] == ["one", "two"]
    assert soup.find("code", string="inline")
    assert soup.find("em", string="emphasis")
    assert soup.find("i", string="italic text")
    assert 'print("<safe>")' in soup.find("pre").get_text()


def test_html_safety_empty_and_malformed_markdown():
    rendered = _render('<script>alert(1)</script><img src="javascript:bad" onerror="boom">')
    soup = BeautifulSoup(rendered, "html.parser")
    assert soup.find("script") is None
    assert soup.find(attrs={"onerror": True}) is None
    bad_img = soup.find("img")
    assert bad_img is not None
    assert bad_img.get("src") is None
    assert _render("").strip() == ""
    assert "[broken" in _render("[broken")


def test_badges_are_integrated_into_generated_index(tmp_path):
    project_dir = tmp_path / "sinatra-like"
    project_dir.mkdir()
    (project_dir / "README.md").write_text("# Sinatra-like\n\n" + SINATRA_BADGES, encoding="utf-8")
    output = tmp_path / "site"
    html_renderer.render_project_website(
        Project(name="Sinatra-like", root=str(project_dir.resolve())),
        output,
    )
    soup = BeautifulSoup((output / "index.html").read_text(encoding="utf-8"), "html.parser")
    readme = soup.select_one(".readme-content")
    assert readme is not None
    assert readme.find("a", href="https://badge.fury.io/rb/sinatra").find(
        "img", src="https://badge.fury.io/rb/sinatra.svg", alt="Gem Version"
    )
    assert readme.find(
        "a", href="https://github.com/sinatra/sinatra/actions/workflows/test.yml"
    ).find(
        "img",
        src="https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg",
        alt="Testing",
    )
    for section in (
        "Classes", "Functions", "Methods", "Modules", "Dependencies",
        "Relationships", "JSON", "Other project files",
    ):
        assert section in soup.get_text(" ", strip=True)
    assert (output / "relation-map.html").is_file()
    assert (output / "assets" / "relation-map.js").is_file()
