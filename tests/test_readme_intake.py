from __future__ import annotations

from bs4 import BeautifulSoup

from analysis.discovery import ProjectDiscovery
from model.project import Project
from readers.markdown import MarkdownReader
from rendering.html import (
    _readme_candidates,
    _readme_path,
    render_project_website,
)


def _discover(root):
    return ProjectDiscovery([MarkdownReader()]).analyze(root, name="README fixture").project


def test_readme_variants_are_discovered_and_main_selection_is_deterministic(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "README.en.md").write_text("# English\n\nEnglish intro.\n", encoding="utf-8")
    (tmp_path / "Readme.md").write_text("# Main\n\nMain intro.\n", encoding="utf-8")
    (tmp_path / "docs" / "README.rst").write_text("Component\n=========\n\nNested docs.\n", encoding="utf-8")
    (tmp_path / "vendor" / "README.md").write_text("# Dependency\n", encoding="utf-8")

    project = _discover(tmp_path)
    docs = {node.metadata["relative_path"] for node in project.documentation}
    assert docs == {"Readme.md", "README.en.md", "docs/README.rst"}
    assert _readme_path(project).name == "Readme.md"
    assert [path.relative_to(tmp_path).as_posix() for path in _readme_candidates(project)] == [
        "Readme.md", "README.en.md", "docs/README.rst"
    ]


def test_markdown_reader_preserves_source_and_extracts_structure_and_semantics(tmp_path):
    readme = tmp_path / "README.markdown"
    source = """---
title: Demo
---
Demo Project
============

Human-first introduction.

## Quick Start

1. Install it.
2. Run it.

## Requirements

- Python

See [Guide][guide].

[guide]: docs/guide.md
"""
    readme.write_text(source, encoding="utf-8")
    project = _discover(tmp_path)
    node = project.documentation[0]

    assert node.documentation == source
    assert node.title == "Demo Project"
    assert node.kind == "markdown"
    assert "Quick Start" in node.headings
    assert "docs/guide.md" in node.links
    assert node.metadata["sections"]["installation"] == "1. Install it.\n2. Run it."
    assert node.metadata["sections"]["requirements"] == "- Python\n\nSee [Guide][guide].\n\n[guide]: docs/guide.md"


def test_mdx_is_static_and_untrusted_html_is_sanitized_in_generated_output(tmp_path):
    (tmp_path / "README.mdx").write_text(
        "# MDX Demo\n\nimport Thing from './Thing'\n\n<Thing />\n\n"
        "<img src=\"javascript:bad\" onerror=\"alert(1)\">\n\n"
        "[unsafe](javascript:alert(1))\n",
        encoding="utf-8",
    )
    project = _discover(tmp_path)
    out = tmp_path / "site"
    render_project_website(project, out)
    page = (out / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(page, "html.parser")

    assert project.documentation[0].kind == "mdx"
    readme = soup.select_one(".readme-content")
    assert readme is not None
    assert readme.find("script") is None
    assert readme.find(attrs={"onerror": True}) is None
    assert not any((tag.get("href") or "").startswith("javascript:") for tag in readme.find_all("a"))
    assert not any((tag.get("src") or "").startswith("javascript:") for tag in readme.find_all("img"))
    assert "import Thing" in readme.get_text(" ", strip=True)


def test_rst_and_plain_text_are_preserved_without_being_parsed_as_markdown(tmp_path):
    (tmp_path / "README.rst").write_text(
        "RST Project\n===========\n\nUsage\n-----\n\n**RST emphasis** and <script>bad()</script>\n",
        encoding="utf-8",
    )
    project = _discover(tmp_path)
    out = tmp_path / "rst-site"
    render_project_website(project, out)
    page = (out / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(page, "html.parser")
    pre = soup.select_one("pre.readme-rst")
    assert pre is not None
    assert "**RST emphasis**" in pre.get_text()
    assert pre.find("script") is None

    (tmp_path / "README.rst").unlink()
    (tmp_path / "README.txt").write_text("Plain README\n\n*not markdown*\n", encoding="utf-8")
    project = _discover(tmp_path)
    out = tmp_path / "txt-site"
    render_project_website(project, out)
    soup = BeautifulSoup((out / "index.html").read_text(encoding="utf-8"), "html.parser")
    assert "*not markdown*" in soup.select_one("pre.readme-plain").get_text()


def test_local_readme_assets_cannot_escape_project_root(tmp_path):
    outside = tmp_path.parent / "outside-readme-secret.png"
    outside.write_bytes(b"not really an image")
    (tmp_path / "README.md").write_text(
        "# Safe\n\n![outside](../outside-readme-secret.png)\n",
        encoding="utf-8",
    )
    project = _discover(tmp_path)
    out = tmp_path / "site"
    render_project_website(project, out)
    assert not list((out / "assets" / "readme").rglob("outside-readme-secret.png"))


def test_empty_and_missing_readmes_are_graceful(tmp_path):
    project = _discover(tmp_path)
    assert project.documentation == []
    out = tmp_path / "missing-site"
    render_project_website(project, out)
    assert "No README was found" in (out / "index.html").read_text(encoding="utf-8")

    (tmp_path / "README.md").write_text("", encoding="utf-8")
    project = _discover(tmp_path)
    assert len(project.documentation) == 1
    assert project.documentation[0].metadata["empty"] is True
    out = tmp_path / "empty-site"
    render_project_website(project, out)
    assert "README exists but is empty or could not be read" in (out / "index.html").read_text(encoding="utf-8")


def test_generated_markdown_has_heading_anchors_task_lists_and_all_readme_identities(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Demo\n\n## Usage Guide\n\n- [x] ready\n- [ ] pending\n\n[Jump](#usage-guide)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.en.md").write_text("# Demo English\n", encoding="utf-8")
    project = _discover(tmp_path)
    out = tmp_path / "site"
    render_project_website(project, out)
    soup = BeautifulSoup((out / "index.html").read_text(encoding="utf-8"), "html.parser")
    readme = soup.select_one(".readme-panel")
    assert readme.find("h2", id="usage-guide") is not None
    boxes = readme.select('input[type="checkbox"][disabled]')
    assert len(boxes) == 2
    assert boxes[0].has_attr("checked")
    assert not boxes[1].has_attr("checked")
    assert readme.find("a", href="#usage-guide") is not None
    source_text = readme.select_one(".readme-sources").get_text(" ", strip=True)
    assert "README.md" in source_text
    assert "README.en.md" in source_text


def test_semantic_interpretation_is_order_independent_and_preserves_unknown_sections(tmp_path):
    (tmp_path / "README.md").write_text(
        """# Odd Project

## Bootstrapping the workshop

Run `tool init` before anything else.

## Why this exists

Odd Project turns local sketches into reviewable artifacts.

## Things nobody named Features

- deterministic output
- offline operation

## Internals

Parser -> model -> renderer.
""",
        encoding="utf-8",
    )
    project = _discover(tmp_path)
    node = project.documentation[0]

    # Unknown terminology is preserved structurally even when it is not forced
    # into one of Barkly's optional semantic categories.
    titles = [section["title"] for section in node.metadata["structure"]]
    assert titles == [
        "Odd Project", "Bootstrapping the workshop", "Why this exists",
        "Things nobody named Features", "Internals",
    ]
    assert node.metadata["sections"]["architecture"] == "Parser -> model -> renderer."
    assert "installation" not in node.metadata["sections"]

    out = tmp_path / "site"
    render_project_website(project, out)
    generated = (out / "index.html").read_text(encoding="utf-8")
    assert "Bootstrapping the workshop" in generated
    assert "Things nobody named Features" in generated
    assert "deterministic output" in generated


def test_headingless_readme_uses_clear_prose_without_fabricating_sections(tmp_path):
    source = (
        "Tiny Tool converts local manifests into deterministic reports.\n\n"
        "Run it from your normal development shell.\n"
    )
    (tmp_path / "README.md").write_text(source, encoding="utf-8")
    project = _discover(tmp_path)
    node = project.documentation[0]

    assert node.documentation == source
    assert node.metadata["structure"] == []
    assert node.metadata["sections"] == {}
    assert node.metadata["overview"] == "Tiny Tool converts local manifests into deterministic reports."


def test_sinatra_style_badges_and_barkly_style_intro_use_same_general_interpreter(tmp_path):
    sinatra = tmp_path / "sinatra"
    barkly = tmp_path / "barkly"
    sinatra.mkdir()
    barkly.mkdir()
    (sinatra / "README.md").write_text(
        """# Sinatra

[![Gem Version](https://badge.fury.io/rb/sinatra.svg)](https://badge.fury.io/rb/sinatra)

Sinatra is a DSL for quickly creating web applications in Ruby with minimal effort.

## Usage

Create a route and run the application.
""",
        encoding="utf-8",
    )
    # Representative excerpt from Barkly Labs' repository README.  It keeps the
    # project's actual title/lead/status vocabulary without making the parser
    # depend on the rest of that evolving document.
    (barkly / "README.md").write_text(
        """# Barkly Docs

Human-centered documentation and knowledge infrastructure for Barkly Labs.

Barkly Docs is a static analysis project for turning source code and project artifacts into a common, structured understanding of a software system.

## Current status

The implementation in this repository is a work in progress.

## Supported CLI

The main command now runs the full local workflow.

## Design principles

1. Human first.
2. Documentation is infrastructure.
""",
        encoding="utf-8",
    )

    sinatra_project = _discover(sinatra)
    barkly_project = _discover(barkly)
    assert sinatra_project.documentation[0].metadata["overview"].startswith("Sinatra is a DSL")
    assert barkly_project.documentation[0].metadata["overview"] == (
        "Human-centered documentation and knowledge infrastructure for Barkly Labs."
    )
    assert sinatra_project.documentation[0].metadata["sections"]["usage"].startswith("Create a route")
    # Barkly-specific headings remain preserved even when they have no universal semantic label.
    barkly_titles = [item["title"] for item in barkly_project.documentation[0].metadata["structure"]]
    assert "Current status" in barkly_titles
    assert "Supported CLI" in barkly_titles
    assert "Design principles" in barkly_titles


def test_nested_setext_and_multilingual_sections_remain_available(tmp_path):
    (tmp_path / "README.md").write_text(
        """Universal Project
=================

A tool for mixed documentation styles.

Primeros pasos
--------------

Instala la herramienta.

### Deep Notes

Keep this unfamiliar nested section.
""",
        encoding="utf-8",
    )
    project = _discover(tmp_path)
    node = project.documentation[0]
    structure = node.metadata["structure"]
    assert [(item["title"], item["level"]) for item in structure] == [
        ("Universal Project", 1), ("Primeros pasos", 2), ("Deep Notes", 3)
    ]
    assert "Primeros pasos" in node.headings
    assert node.metadata["overview"] == "A tool for mixed documentation styles."
    assert "installation" not in node.metadata["sections"]
