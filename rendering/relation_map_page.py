from __future__ import annotations

import json

from analysis.graph import build_relation_graph
from model.project import Project
from rendering.html import _page_shell, _project_name


def render_relation_map_page(project: Project) -> str:
    """Render Barkly's interactive SVG relationship spider map."""
    graph = build_relation_graph(project, view="relation_map", max_nodes=None, max_edges=None)
    payload = json.dumps(graph.as_dict(), ensure_ascii=False)
    # JSON lives in a script text node; prevent project-controlled text from
    # closing that element or becoming markup.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")

    body = (
        '<section class="subpage-header card">'
        '<div class="kicker">Barkly Docs · Project explorer</div>'
        '<h1>Relationship Map</h1>'
        '<p>Explore the real project graph as a focused spider map. Search the complete '
        'dataset, filter the visible graph, and select a node to inspect its evidence and connections.</p>'
        '</section>'
        '<section class="relation-map-toolbar card" aria-label="Relationship map controls">'
        '<div class="relation-map-search-wrap">'
        '<label for="relation-map-search">Search the complete graph</label>'
        '<input id="relation-map-search" type="search" placeholder="Name, type, path, qualified name…" autocomplete="off" />'
        '<ul id="relation-map-search-results" class="relation-map-search-results" hidden aria-label="Graph search results"></ul>'
        '</div>'
        '<div class="relation-map-filter-grid">'
        '<label>Entity type<select id="relation-map-kind"><option value="">All entity types</option></select></label>'
        '<label>Relationship type<select id="relation-map-edge-kind"><option value="">All relationship types</option></select></label>'
        '<label>Language<select id="relation-map-language"><option value="">All recorded languages</option></select></label>'
        '<label>Evidence<select id="relation-map-evidence"><option value="">All evidence levels</option></select></label>'
        '</div>'
        '<div class="relation-map-actions">'
        '<button type="button" data-graph-action="zoom-in" aria-label="Zoom in">Zoom in</button>'
        '<button type="button" data-graph-action="zoom-out" aria-label="Zoom out">Zoom out</button>'
        '<button type="button" data-graph-action="fit">Fit graph</button>'
        '<button type="button" data-graph-action="reset-view">Reset viewport</button>'
        '<button type="button" id="relation-map-back" disabled>Previous selection</button>'
        '<button type="button" id="relation-map-reset-filters">Reset exploration</button>'
        '</div>'
        '<p id="relation-map-count" class="muted" aria-live="polite"></p>'
        '<p id="relation-map-scope-status" class="muted relation-map-scope-status"></p>'
        '</section>'
        '<div id="relation-map-shell">'
        '<section id="relation-map-panel" aria-label="Interactive relationship spider map">'
        '<div id="relation-map-empty" class="relation-map-empty" hidden>No graph nodes match the current filters.</div>'
        '<svg id="relation-map-canvas" viewBox="0 0 1200 780" role="group" aria-label="Project relationship graph. Use search or Tab to select nodes.">'
        '<g id="relation-map-viewport"></g>'
        '</svg>'
        '</section>'
        '<aside id="relation-map-details" aria-label="Selected graph item details">'
        '<div class="kicker">Selected item</div>'
        '<div id="relation-map-details-body"></div>'
        '</aside>'
        '</div>'
        '<details class="relation-map-accessible card">'
        '<summary>Accessible list of nodes in the current view</summary>'
        '<p class="muted">Use these buttons as a non-visual alternative to selecting nodes in the map.</p>'
        '<ul id="relation-map-accessible-list"></ul>'
        '</details>'
        '<details class="relation-map-legend card">'
        '<summary>Map legend and scope</summary>'
        '<div class="legend-grid">'
        '<div class="legend-item"><span class="legend-swatch" style="background:#ff6b9d"></span>Modules</div>'
        '<div class="legend-item"><span class="legend-swatch" style="background:#6fb7ff"></span>Files</div>'
        '<div class="legend-item"><span class="legend-swatch" style="background:#7dffb2"></span>Classes / interfaces</div>'
        '<div class="legend-item"><span class="legend-swatch" style="background:#ffd76b"></span>Functions</div>'
        '<div class="legend-item"><span class="legend-swatch" style="background:#e3a7ff"></span>Methods</div>'
        '</div>'
        '<p class="muted">Lines are labeled through their accessible title and details. Evidence is shown textually in the details panel; color is not the only evidence cue.</p>'
        '</details>'
        '<p class="muted relation-map-inventory-link">The map intentionally scopes large graphs for readability; it never truncates the embedded dataset. '
        '<a href="relationships.html">Open the complete relationship inventory</a> for every recorded relationship.</p>'
        '<script id="relation-map-data" type="application/json">' + payload + '</script>'
        '<script src="assets/relation-map.js" defer></script>'
    )
    return _page_shell(f"Relationship Map · {_project_name(project)}", "relation-map", body)


__all__ = ["render_relation_map_page"]
