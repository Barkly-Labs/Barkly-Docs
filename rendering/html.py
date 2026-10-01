from __future__ import annotations

import html
import re
from pathlib import Path

from model.project import Project

CSS = """
:root {
  --bg: #0b0d12;
  --panel: #121822;
  --panel-alt: #171f2d;
  --line: #253246;
  --text: #edf4ff;
  --muted: #a4b3c9;
  --accent: #8dd3ff;
  --success: #7af0b6;
  --warning: #ffd166;
  --danger: #ff7b8c;
  --shadow: rgba(1, 5, 10, 0.25);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.skip-link {
  position: absolute;
  left: -9999px;
  top: auto;
}
.skip-link:focus {
  left: 16px;
  top: 16px;
  z-index: 40;
  background: var(--panel);
  border: 1px solid var(--line);
  color: var(--text);
  padding: 12px 14px;
  border-radius: 8px;
}
.container {
  max-width: 1180px;
  margin: 0 auto;
  padding: 32px 20px 64px;
}
header.site-header {
  background: linear-gradient(180deg, rgba(20, 28, 38, 0.95), rgba(14, 18, 25, 0.95));
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 10;
}
header.site-header .container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding-top: 16px;
  padding-bottom: 16px;
}
.brand {
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 10px;
}
.paw { width: 26px; height: 26px; display: inline-block; vertical-align: middle; }
nav.site-nav { display: flex; gap: 16px; flex-wrap: wrap; }
nav.site-nav a {
  color: var(--muted);
  font-size: 0.95rem;
  padding: 6px 8px;
  border-radius: 8px;
}
nav.site-nav a:hover, nav.site-nav a:focus-visible {
  color: var(--text);
  text-decoration: none;
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
nav.site-nav a.active { color: var(--text); background: rgba(141, 211, 255, 0.08); }
.hero {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 20px;
  margin-top: 32px;
}
.card {
  background: linear-gradient(180deg, var(--panel), var(--panel-alt));
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 10px 30px var(--shadow);
}
.hero-main { padding: 28px; }
.hero-main h1 {
  font-size: clamp(2rem, 2.8vw, 3rem);
  margin: 0 0 12px;
  letter-spacing: -0.04em;
}
.hero-main p {
  margin: 0;
  color: var(--muted);
  max-width: 60ch;
}
.kicker {
  display: inline-block;
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(110px, 1fr));
  gap: 12px;
  padding: 20px;
}
.metric {
  padding: 16px 14px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255,255,255,0.015);
}
.metric-label {
  display: block;
  color: var(--muted);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.metric-value { font-size: 1.75rem; font-weight: 700; }
.section { margin-top: 32px; }
.section h2 { font-size: 1.5rem; margin: 0 0 8px; }
.section-subtitle { color: var(--muted); margin-bottom: 18px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}
.tile {
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
}
.tile h3 { margin: 0 0 10px; font-size: 1rem; }
.tile p, .tile ul { margin: 0; color: var(--muted); }
.entity-list, .relationship-list { display: grid; gap: 12px; }
.entity-item, .relationship-item {
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
}
.entity-item h3, .relationship-item h3 { margin: 0 0 8px; font-size: 1.05rem; }
.meta {
  color: var(--muted);
  font-size: 0.9rem;
  margin-bottom: 8px;
}
.badge {
  display: inline-block;
  margin-right: 8px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--line);
  font-size: 0.74rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.badge.declared { background: rgba(122, 240, 182, 0.15); color: var(--success); }
.badge.detected { background: rgba(141, 211, 255, 0.15); color: var(--accent); }
.badge.inferred { background: rgba(255, 209, 102, 0.15); color: var(--warning); }
.badge.unknown { background: rgba(255, 123, 140, 0.15); color: var(--danger); }
.code {
  font-family: "Consolas", "SFMono-Regular", monospace;
  color: var(--text);
}
.muted { color: var(--muted); }
.empty-state {
  border: 1px dashed var(--line);
  border-radius: 12px;
  padding: 18px;
  color: var(--muted);
  background: rgba(255,255,255,0.01);
}
.site-footer {
  margin-top: 40px;
  color: var(--muted);
  border-top: 1px solid var(--line);
  padding-top: 18px;
}
@media (max-width: 760px) {
  .hero { grid-template-columns: 1fr; }
  header.site-header .container { align-items: flex-start; flex-direction: column; }
  nav.site-nav { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
"""

PAW_SVG = '''
<svg viewBox="0 0 100 100" aria-hidden="true">
  <path d="
    M30 43
    C19 43 12 35 14 25
    C16 16 24 12 31 16
    C38 20 40 31 37 37
    C35 41 33 43 30 43

    M70 43
    C81 43 88 35 86 25
    C84 16 76 12 69 16
    C62 20 60 31 63 37
    C65 41 67 43 70 43

    M50 36
    C42 36 37 29 39 22
    C41 15 47 12 52 15
    C58 18 59 26 56 32
    C55 35 53 36 50 36

    M50 52
    C35 52 24 62 24 75
    C24 87 34 92 45 88
    C49 87 52 87 56 88
    C67 92 76 87 76 75
    C76 62 65 52 50 52
  "/>
</svg>
'''


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def _project_name(project: Project) -> str:
    return project.name or "Project"


def _project_description(project: Project) -> str:
    description = project.metadata.get("description")
    if description:
        return str(description)
    readme_path = Path(project.root) / "README.md"
    if readme_path.exists():
        try:
            text = readme_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "Project purpose unknown."
        cleaned = [line.strip() for line in text.splitlines() if line.strip()]
        for line in cleaned:
            if line.startswith("#"):
                continue
            if line and not line.startswith("!"):
                return line[:220]
    return "Project purpose unknown."


def _languages(project: Project) -> list[str]:
    return sorted({file.language for file in project.files if file.language})


def _relationship_badge(value: str) -> str:
    key = (value or "UNKNOWN").upper()
    css = key.lower()
    return f'<span class="badge {css}" aria-label="Evidence status: { _escape(key) }">{_escape(key)}</span>'


def _evidence_summary(project: Project) -> str:
    counts = {"DECLARED": 0, "DETECTED": 0, "INFERRED": 0, "UNKNOWN": 0}
    for relationship in project.relationships:
        key = (relationship.evidence or "UNKNOWN").upper()
        if key in counts:
            counts[key] += 1
    entries = []
    for label in ["DECLARED", "DETECTED", "INFERRED", "UNKNOWN"]:
        entries.append(
            f'<div class="tile"><h3>{_escape(label)}</h3><p>{counts[label]} relationship(s)</p></div>'
        )
    return '<div class="grid">' + ''.join(entries) + '</div>'


def _nav(current: str) -> str:
    pages = [
        ("index.html", "Project overview"),
        ("entities.html", "Entities"),
        ("relationships.html", "Relationships"),
    ]
    html_links = []
    for href, label in pages:
        active = " active" if href == ("index.html" if current == "index" else "entities.html" if current == "entities" else "relationships.html") else ""
        html_links.append(f'<a class="{active.strip()}" href="{href}">{_escape(label)}</a>')
    return "".join(html_links)


def _stat_card(label: str, value: str) -> str:
    return (
        '<div class="metric">'
        f'<span class="metric-label">{_escape(label)}</span>'
        f'<span class="metric-value">{_escape(value)}</span>'
        '</div>'
    )


def _render_readme(project: Project) -> str:
    readme_path = Path(project.root) / "README.md"
    if not readme_path.exists():
        return '<div class="empty-state">No README.md was found in the project root.</div>'
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return '<div class="empty-state">README.md exists but could not be read.</div>'
    lines = [line.strip() for line in text.splitlines() if line.strip()][:12]
    if not lines:
        return '<div class="empty-state">README.md exists but contains no readable text.</div>'
    return "".join(f"<p>{_escape(line)}</p>" for line in lines)


def _render_entity_summary(project: Project) -> str:
    items = []
    for item in sorted(project.classes, key=lambda node: node.name):
        methods = ", ".join(item.methods) if item.methods else "No methods discovered"
        items.append(
            f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">{_escape(item.path)}</div>
              <div class="meta">Methods: {_escape(methods)}</div>
            </div>
            """
        )
    for item in sorted(project.functions, key=lambda node: node.name):
        signature = f"{item.name}({', '.join(item.parameters)})" if item.parameters else item.name
        items.append(
            f"""
            <div class="entity-item">
              <h3>{_escape(signature)}</h3>
              <div class="meta">{_escape(item.path)}</div>
              <div class="meta">Return: {_escape(item.return_type or 'unknown')}</div>
            </div>
            """
        )
    for item in sorted(project.methods, key=lambda node: node.name):
        details = item.class_name or "method"
        items.append(
            f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">Class: {_escape(details)}</div>
              <div class="meta">{_escape(item.path)}</div>
            </div>
            """
        )
    if not items:
        return '<div class="empty-state">No project entities were detected.</div>'
    return '<div class="entity-list">' + ''.join(items) + '</div>'


def _render_method_reference(project: Project) -> str:
    """Render method and function references with signatures and source evidence."""

    entries: list[str] = []
    class_map: dict[str, list] = {}
    for method in project.methods:
        class_map.setdefault(method.class_name or "module", []).append(method)

    for function in project.functions:
        class_map.setdefault("module", []).append(function)

    for name in sorted(class_map):
        group = class_map[name]
        items = []
        for item in sorted(group, key=lambda node: getattr(node, "name", "")):
            signature = item.name
            if hasattr(item, "parameters") and item.parameters:
                signature = f"{item.name}({', '.join(item.parameters)})"
            if getattr(item, "return_type", None):
                signature = f"{signature} -> {item.return_type}"
            doc = getattr(item, "documentation", None) or "No source documentation available."
            line = getattr(item, "line_start", None)
            location = f"{item.path}:{line}" if line else item.path
            items.append(
                f"""
                <div class="entity-item">
                  <h3>{_escape(signature)}</h3>
                  <div class="meta">{_escape(name)} · {_escape(location)}</div>
                  <p>{_escape(doc[:220])}</p>
                </div>
                """
            )
        if items:
            entries.append(
                f"<div class='section'><h3>{_escape(name)}</h3><div class='entity-list'>{''.join(items)}</div></div>"
            )

    if not entries:
        return '<div class="empty-state">No source-level method or function references were detected.</div>'
    return ''.join(entries)


def _mermaid_label(value: str) -> str:
    value = str(value or "node").replace('"', '\\"')
    return value


def _relationship_map_mermaid(project: Project) -> str:
    if not project.relationships:
        return "graph TD\n  node0[No relationships discovered]"

    nodes: dict[str, str] = {}
    lines = ["graph TD"]
    for relationship in project.relationships:
        for label in (relationship.source, relationship.target):
            if label not in nodes:
                safe = re.sub(r"[^A-Za-z0-9_]", "_", label) or "node"
                if safe in {"graph", "subgraph"}:
                    safe = f"_{safe}"
                nodes[label] = safe
        source_id = nodes[relationship.source]
        target_id = nodes[relationship.target]
        lines.append(
            f'  {source_id}["{_mermaid_label(relationship.source)}"] -->|{relationship.kind}| {target_id}["{_mermaid_label(relationship.target)}"]'
        )
    return "\n".join(lines)


def _render_relationships(project: Project) -> str:
    if not project.relationships:
        return '<div class="empty-state">No relationships were discovered in the shared relationship model.</div>'
    items = []
    for relationship in project.relationships:
        source_location = ""
        if relationship.source_location:
            source_location = (
                '<div class="meta">Source: '
                f'{_escape(str(relationship.source_location))}'
                '</div>'
            )
        items.append(
            f"""
            <div class="relationship-item">
              <h3><span class="code">{_escape(relationship.source)}</span> → <span class="code">{_escape(relationship.target)}</span></h3>
              <div class="meta">{_relationship_badge(relationship.evidence)} <span class="code">{_escape(relationship.kind)}</span></div>
              {source_location}
              <div class="meta">File: {_escape(relationship.source_file or 'Unknown')}</div>
            </div>
            """
        )
    mermaid = (
        '<div class="section">'
        '<h3>Relationship map</h3>'
        '<pre class="code" aria-label="Mermaid relationship map">'
        f'{_escape(_relationship_map_mermaid(project))}'
        '</pre>'
        '</div>'
    )
    return '<div class="relationship-list">' + ''.join(items) + '</div>' + mermaid


def _render_files(project: Project) -> str:
    if not project.files:
        return '<div class="empty-state">No project files were discovered.</div>'
    items = []
    for item in sorted(project.files, key=lambda node: node.path):
        items.append(
            f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">Language: {_escape(item.language or 'Unknown')}</div>
              <div class="meta">Path: {_escape(item.path)}</div>
            </div>
            """
        )
    return '<div class="entity-list">' + ''.join(items) + '</div>'


def _page_shell(title: str, current: str, body: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_escape(title)}</title>
  <meta name="description" content="Barkly Docs project overview and evidence-based documentation." />
  <link rel="stylesheet" href="assets/site.css" />
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header class="site-header">
    <div class="container">
      <div class="brand"><span class="paw">{PAW_SVG}</span> Barkly Docs</div>
      <nav class="site-nav" aria-label="Main navigation">{_nav(current)}</nav>
    </div>
  </header>
  <main id="main-content" class="container">
    {body}
  </main>
  <footer class="site-footer"><div class="container">Generated from the shared Barkly Project Model.</div></footer>
</body>
</html>'''


def _render_index(project: Project) -> str:
    description = _project_description(project)
    languages = _languages(project)
    project_summary = (
        '<div class="card hero-main">'
        '<div class="kicker">Project documentation</div>'
        f'<h1>{_escape(_project_name(project))}</h1>'
        f'<p>{_escape(description)}</p>'
        '</div>'
    )
    stats = (
        '<div class="card metrics">'
        + _stat_card("Files", str(len(project.files)))
        + _stat_card("Modules", str(len(project.modules)))
        + _stat_card("Classes", str(len(project.classes)))
        + _stat_card("Functions", str(len(project.functions)))
        + _stat_card("Methods", str(len(project.methods)))
        + _stat_card("Relationships", str(len(project.relationships)))
        + '</div>'
    )
    overview = (
        '<div class="section">'
        '<h2>Project overview</h2>'
        '<div class="section-subtitle">What this project appears to do, based on declared project metadata and static source evidence.</div>'
        '<div class="grid">'
        f'<div class="tile"><h3>Purpose</h3><p>{_escape(description)}</p></div>'
        f'<div class="tile"><h3>Languages</h3><p>{_escape(", ".join(languages) if languages else "Unknown")}</p></div>'
        f'<div class="tile"><h3>Root</h3><p>{_escape(project.root)}</p></div>'
        f'<div class="tile"><h3>Documentation</h3><p>{_escape("README.md present" if (Path(project.root) / "README.md").exists() else "README.md not discovered")}</p></div>'
        '</div>'
        '</div>'
    )
    evidence = (
        '<div class="section">'
        '<h2>Evidence and limits</h2>'
        '<div class="section-subtitle">Declared facts, detected structure, inferred patterns, and unknown areas remain clearly separated.</div>'
        + _evidence_summary(project)
        + '<div class="tile" style="margin-top:12px;"><h3>Evidence labels</h3><p>DECLARED = explicitly stated in source or project metadata; DETECTED = directly identified through static analysis; INFERRED = derived but not directly observed; UNKNOWN = not established by available evidence.</p></div>'
        + '</div>'
    )
    documentation = (
        '<div class="section">'
        '<h2>Documentation references</h2>'
        '<div class="section-subtitle">HTML output retains the project README where available.</div>'
        + _render_readme(project)
        + '</div>'
    )
    structure = (
        '<div class="section">'
        '<h2>Project structure</h2>'
        '<div class="section-subtitle">Discovered files and their source identities.</div>'
        + _render_files(project)
        + '</div>'
    )
    body = f'<section class="hero">{project_summary}{stats}</section>{overview}{evidence}{documentation}{structure}'
    return _page_shell(f"{_project_name(project)} — Barkly Docs", "index", body)


def _render_entities_page(project: Project) -> str:
    body = (
        '<section class="section">'
        '<h2>Entities</h2>'
        '<div class="section-subtitle">Classes, functions, and methods discovered in the project model.</div>'
        + _render_entity_summary(project)
        + '</section>'
        + '<section class="section">'
        '<h2>Method and function reference</h2>'
        '<div class="section-subtitle">Source-level signatures and documentation recovered from the shared model.</div>'
        + _render_method_reference(project)
        + '</section>'
    )
    return _page_shell(f"Entities — {_project_name(project)}", "entities", body)


def _render_relationships_page(project: Project) -> str:
    body = (
        '<section class="section">'
        '<h2>Relationships</h2>'
        '<div class="section-subtitle">Evidence-labeled relationships between project entities.</div>'
        + _render_relationships(project)
        + '</section>'
    )
    return _page_shell(f"Relationships — {_project_name(project)}", "relationships", body)


def render_project_website(project: Project, output_dir: str | Path) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    assets_dir = output_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    (assets_dir / "site.css").write_text(CSS, encoding="utf-8")

    index_path = output_path / "index.html"
    entities_path = output_path / "entities.html"
    relationships_path = output_path / "relationships.html"

    index_path.write_text(_render_index(project), encoding="utf-8")
    entities_path.write_text(_render_entities_page(project), encoding="utf-8")
    relationships_path.write_text(_render_relationships_page(project), encoding="utf-8")

    return [index_path, entities_path, relationships_path, assets_dir / "site.css"]


def generate_html_website(project: Project, output_dir: str | Path) -> list[Path]:
    return render_project_website(project, output_dir)


__all__ = [
    "CSS",
    "render_project_website",
    "generate_html_website",
]
