from __future__ import annotations

from model.project import Project
import json
from analysis.graph import build_relation_graph
from rendering.html import (
    _page_shell,
    _project_name,
)


def render_relation_map_page(project: Project) -> str:
    """Render the full, searchable, card-based relationship explorer."""
    graph = build_relation_graph(project, max_nodes=None, max_edges=None)
    graph_data = graph.as_dict()

    # Prevent a project string containing HTML/script markup from closing the
    # JSON script element when embedded in the page.
    payload = json.dumps(graph_data, ensure_ascii=False)
    payload = (
        payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    )

    body = (
        '<section class="subpage-header">'
        '<div class="kicker">Barkly Docs · Project explorer</div>'
        "<h1>Relationship Map</h1>"
        "<p>Explore files, modules, classes, functions, methods, and their "
        "detected relationships. Expand a card to inspect details and follow connections.</p>"
        "</section>"
        '<section class="card" style="margin:1rem 0;padding:1rem">'
        '<div class="relation-map-controls">'
        '<label for="relation-map-search">Search names, descriptions, and paths</label>'
        '<input id="relation-map-search" type="search" '
        'aria-label="Search relationship map" '
        'placeholder="Search the project…" autocomplete="off" />'
        '<label for="relation-map-kind">Filter by item type</label>'
        '<select id="relation-map-kind"><option value="">All types</option></select>'
        '<button type="button" id="relation-map-reset">Reset filters</button>'
        "</div>"
        '<p id="relation-map-count" class="muted" aria-live="polite"></p>'
        "</section>"
        '<div id="relation-card-grid" class="relation-card-grid" '
        'aria-live="polite"></div>'
        '<nav id="relation-map-pagination" class="relation-pagination" '
        'aria-label="Relationship map pages"></nav>'
        '<p class="muted">Descriptions and evidence reflect the scan output. '
        "Missing descriptions are shown as unavailable rather than guessed. "
        '<a href="relationships.html">Open the complete relationship inventory</a>.</p>'
        '<script id="relation-map-data" type="application/json">'
        + payload
        + "</script>"
        '<script src="assets/relation-map.js" defer></script>'
        "<style>"
        ".relation-map-controls{display:grid;grid-template-columns:1fr;gap:.5rem}"
        ".relation-map-controls input,.relation-map-controls select{width:100%;"
        "box-sizing:border-box;padding:.7rem;border:1px solid var(--border,#383838);"
        "border-radius:.5rem;background:var(--panel,#101010);color:inherit}"
        ".relation-map-controls button,.relation-pagination button,.relation-link{"
        "padding:.45rem .7rem;border:1px solid var(--border,#383838);"
        "border-radius:.5rem;background:var(--panel-alt,#151515);color:inherit;cursor:pointer}"
        ".relation-card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:1rem;align-items:start}"
        ".relation-card{min-width:0;overflow-wrap:anywhere}"
        ".relation-card-heading{display:flex;justify-content:space-between;gap:.5rem;align-items:center;flex-wrap:wrap}"
        ".relation-card h3{margin:.75rem 0 .25rem;font-size:1.05rem}"
        ".relation-path,.muted{color:var(--muted,#aaa);font-size:.9rem}"
        ".relation-details{margin-top:.8rem;border-top:1px solid var(--border,#383838);padding-top:.7rem}"
        ".relation-details summary{cursor:pointer;font-weight:600}"
        ".relation-detail-body{padding-top:.5rem}"
        ".relation-links{padding-left:1.2rem}"
        ".relation-links li{margin:.4rem 0;overflow-wrap:anywhere}"
        ".relation-link{text-align:left;max-width:100%;overflow-wrap:anywhere}"
        ".relation-pagination{display:flex;align-items:center;justify-content:center;gap:1rem;padding:1.25rem 0}"
        ".relation-pagination button:disabled{opacity:.45;cursor:not-allowed}"
        "@media(min-width:700px){.relation-map-controls{grid-template-columns:1fr 1fr;align-items:center}"
        ".relation-map-controls label{align-self:end}}"
        "</style>"
    )
    return _page_shell(
        f"Relationship Map ? {_project_name(project)}",
        "relation-map",
        body,
    )

__all__ = ["render_relation_map_page"]
