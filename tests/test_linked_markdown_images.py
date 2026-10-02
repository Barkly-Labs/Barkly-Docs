
from __future__ import annotations
from bs4 import BeautifulSoup
from model.project import Project
import rendering.html as renderer

BADGES = """\
[![Gem Version](https://badge.fury.io/rb/sinatra.svg)](https://badge.fury.io/rb/sinatra)

[![Testing](https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg)](https://github.com/sinatra/sinatra/actions/workflows/test.yml)
"""

def _fallback(text: str) -> str:
    return renderer._render_markdown(text)

def test_sinatra_badges_render_as_distinct_linked_images_in_fallback():
    soup=BeautifulSoup(_fallback(BADGES),"html.parser")
    anchors=soup.find_all("a")
    assert [(a["href"],a.img["src"],a.img["alt"]) for a in anchors] == [
      ("https://badge.fury.io/rb/sinatra","https://badge.fury.io/rb/sinatra.svg","Gem Version"),
      ("https://github.com/sinatra/sinatra/actions/workflows/test.yml",
       "https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg","Testing"),
    ]
    assert "[![" not in soup.get_text()

def test_balanced_parentheses_nested_brackets_and_escapes():
    html=_fallback(
      r"[![a \[nested\] badge](https://example.com/img(a).svg)](https://example.com/go(test)) "
      r"[ordinary [nested]](https://example.com/a(b)) "
      r"![standalone](https://example.com/i(x).png)"
    )
    soup=BeautifulSoup(html,"html.parser")
    badge=soup.find("a",href="https://example.com/go(test)")
    assert badge.img["src"]=="https://example.com/img(a).svg"
    assert badge.img["alt"]=="a [nested] badge"
    assert soup.find("a",href="https://example.com/a(b)").get_text()=="ordinary [nested]"
    assert soup.find("img",src="https://example.com/i(x).png",alt="standalone")

def test_unsafe_destinations_are_not_activated_and_malformed_does_not_crash():
    html=_fallback("[x](javascript:alert(1)) ![x](data:text/html,bad) [broken")
    soup=BeautifulSoup(html,"html.parser")
    assert soup.find("a",href=True) is None
    assert soup.find("img",src=True) is None
    assert "[broken" in soup.get_text()

def test_existing_inline_markdown_remains():
    soup=BeautifulSoup(_fallback("**bold** *italic* `code` and <i>tag italic</i>"),"html.parser")
    assert soup.strong.get_text()=="bold"
    assert soup.em.get_text()=="italic"
    assert soup.code.get_text()=="code"
    assert soup.i.get_text()=="tag italic"

def test_generated_index_contains_clickable_badges(tmp_path, monkeypatch):
    # Force the compatibility fallback so this exercises the bug being fixed,
    # not markdown-it-py's already-correct parser.
    monkeypatch.setattr(renderer,"MarkdownIt",None)
    monkeypatch.setattr(renderer,"bleach",None)
    project_dir=tmp_path/"sinatra"
    project_dir.mkdir()
    (project_dir/"README.md").write_text("# Sinatra\n\n"+BADGES,encoding="utf-8")
    out=tmp_path/"site"
    renderer.render_project_website(Project(name="Sinatra",root=str(project_dir)),out)
    soup=BeautifulSoup((out/"index.html").read_text(encoding="utf-8"),"html.parser")
    readme=soup.select_one(".readme-content")
    assert readme.find("a",href="https://badge.fury.io/rb/sinatra").find(
      "img",src="https://badge.fury.io/rb/sinatra.svg",alt="Gem Version")
    assert readme.find("a",href="https://github.com/sinatra/sinatra/actions/workflows/test.yml").find(
      "img",src="https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg",alt="Testing")
    assert "[![Gem Version]" not in readme.get_text()
    assert (out/"relation-map.html").is_file()
    assert (out/"assets"/"relation-map.js").is_file()


def test_fenced_code_keeps_linked_image_markdown_literal():
    markdown = """\
```markdown
[![Gem Version](https://badge.fury.io/rb/sinatra.svg)](https://badge.fury.io/rb/sinatra)
```
"""
    soup = BeautifulSoup(_fallback(markdown), "html.parser")
    pre = soup.find("pre")
    assert pre is not None
    assert "[![Gem Version](https://badge.fury.io/rb/sinatra.svg)](https://badge.fury.io/rb/sinatra)" in pre.get_text()
    assert pre.find("a") is None
    assert pre.find("img") is None


def test_sinatra_badges_are_not_reused_as_readme_lead(tmp_path):
    source = (
        "# Sinatra\n\n"
        "[![Gem Version](https://badge.fury.io/rb/sinatra.svg)](https://badge.fury.io/rb/sinatra)\n\n"
        "[![Testing](https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg)](https://github.com/sinatra/sinatra/actions/workflows/test.yml)\n\n"
        "Sinatra is a DSL for quickly creating web applications in Ruby with minimal effort.\n"
    )
    project_dir = tmp_path / "sinatra"
    project_dir.mkdir()
    readme = project_dir / "README.md"
    readme.write_text(source, encoding="utf-8")
    project = Project(name="Sinatra", root=str(project_dir))

    # Source/file-reader stage is lossless.
    assert readme.read_text(encoding="utf-8") == source
    assert renderer._read_readme(project) == source

    # Asset rewriting must not alter remote badge Markdown.
    body = "\n".join(source.splitlines()[1:])
    assert renderer._rewrite_readme_asset_urls(project, body) == body

    # Badge-only media lines must not become escaped project prose.
    assert renderer._project_description(project).startswith("Sinatra is a DSL")

    output = tmp_path / "site"
    renderer.render_project_website(project, output)
    generated = (output / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(generated, "html.parser")
    panel = soup.select_one(".readme-panel")
    assert panel is not None
    lead = panel.select_one(".readme-lead")
    assert lead is not None
    assert "[![" not in lead.get_text()
    assert lead.get_text().startswith("Sinatra is a DSL")
    assert panel.find("a", href="https://badge.fury.io/rb/sinatra").find(
        "img", src="https://badge.fury.io/rb/sinatra.svg", alt="Gem Version"
    )
    assert panel.find(
        "a", href="https://github.com/sinatra/sinatra/actions/workflows/test.yml"
    ).find(
        "img",
        src="https://github.com/sinatra/sinatra/actions/workflows/test.yml/badge.svg",
        alt="Testing",
    )
