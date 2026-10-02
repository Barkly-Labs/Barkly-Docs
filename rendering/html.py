from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from analysis.graph import build_relation_graph
from model.project import Project

CSS = """
:root {
  --bg: #080808;
  --panel: #101010;
  --panel-alt: #151515;
  --line: #262626;
  --text: #f2f2f2;
  --muted: #9a9a9a;
  --accent: #ff6b9d;
  --success: #7dffb2;
  --warning: #ffd76b;
  --danger: #ff7b8c;
  --shadow: rgba(0, 0, 0, 0.28);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
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
  max-width: 1320px;
  margin: 0 auto;
  padding: 32px 18px 72px;
}
header.site-header {
  background: rgba(8, 8, 8, 0.92);
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 20;
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
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 10px;
}
.paw { width: 26px; height: 26px; display: inline-block; vertical-align: middle; }
nav.site-nav { display: flex; gap: 6px; flex-wrap: wrap; }
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
nav.site-nav a.active {
  color: var(--text);
  background: rgba(255, 107, 157, 0.12);
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(300px, 1fr);
  gap: 20px;
  margin-top: 32px;
}
.card {
  background:
    linear-gradient(135deg, rgba(255, 107, 157, 0.055), transparent 58%),
    var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 10px 30px var(--shadow);
}
.hero-main { padding: 28px; }
.hero-readme-image {
  margin: 0 0 18px;
  width: 100%;
  max-height: 280px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #0b0b0b;
}
.hero-readme-image img {
  display: block;
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  object-position: left center;
}
.hero-main h1 {
  font-size: clamp(2.4rem, 5vw, 4.5rem);
  margin: 0 0 12px;
  letter-spacing: -0.06em;
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
  background: #0d0d0d;
}
.metric-label {
  display: block;
  color: var(--muted);
  font-size: 0.72rem;
  letter-spacing: -0.03em;
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
.badge.declared { background: rgba(125, 255, 178, 0.12); color: var(--success); }
.badge.detected { background: rgba(255, 107, 157, 0.15); color: var(--accent); }
.badge.inferred { background: rgba(255, 215, 107, 0.12); color: var(--warning); }
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
  background: #0b0b0b;
}
.site-footer {
  margin-top: 40px;
  color: var(--muted);
  border-top: 1px solid var(--line);
  padding-top: 18px;
}
@media (max-width: 760px) {
  .container { padding-left: 16px; padding-right: 16px; }
  .hero { margin-top: 24px; }
  .hero-main { padding: 22px; }
  .section { margin-top: 26px; }
  .hero { grid-template-columns: 1fr; }
  header.site-header .container { align-items: flex-start; flex-direction: column; }
  nav.site-nav { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}

#relation-map-shell {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 360px);
  gap: 18px;
  margin-top: 24px;
}
#relation-map-panel,
#relation-map-details {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  overflow: hidden;
}
#relation-map-panel {
  min-height: 560px;
  position: relative;
}
#relation-map-canvas {
  width: 100%;
  height: 560px;
  display: block;
  background:
    linear-gradient(rgba(255,255,255,0.015), rgba(255,255,255,0.015)),
    radial-gradient(circle at top, rgba(255,107,157,0.08), transparent 60%);
}
#relation-map-details {
  padding: 18px;
}
.graph-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  background: #0d0d0d;
}
button, input, select {
  font: inherit;
}
button:focus-visible, input:focus-visible, select:focus-visible,
a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}
.graph-tools input[type="search"] {
  flex: 1 1 220px;
  background: #0b0b0b;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text);
  padding: 10px 14px;
}
.graph-tools select {
  background: #0b0b0b;
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 12px;
}
.graph-tools button {
  background: rgba(255, 107, 157, 0.12);
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 12px;
  cursor: pointer;
}
.graph-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 6px 10px;
  color: var(--muted);
}
.filter-chip input {
  accent-color: var(--accent);
}
.legend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-top: 18px;
}
.legend-item {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  background: #0d0d0d;
}
.legend-swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  margin-right: 8px;
}
.relationship-list {
  margin-top: 8px;
  display: grid;
  gap: 10px;
}
.relation-map-empty,
.relation-map-error {
  border: 1px dashed var(--line);
  border-radius: 12px;
  padding: 18px;
  color: var(--muted);
  background: #0b0b0b;
}
.relation-map-error {
  border-color: rgba(255, 123, 140, 0.4);
  color: var(--danger);
}
.node-label {
  font-size: 11px;
  fill: var(--text);
  pointer-events: none;
}
.edge-label {
  font-size: 10px;
  fill: var(--muted);
  pointer-events: none;
}
.graph-node {
  cursor: pointer;
}
.graph-node.selected .node-body {
  stroke: var(--accent);
  stroke-width: 2.5;
}
.graph-edge {
  stroke: var(--muted);
  stroke-width: 1.4;
  fill: none;
  cursor: pointer;
}
.graph-edge.selected {
  stroke: var(--accent);
  stroke-width: 2.2;
}
@media (max-width: 980px) {
  #relation-map-shell {
    grid-template-columns: 1fr;
  }
}

/* Barkly relationship pipeline */
.pipeline-list {
  display: grid;
  gap: 14px;
  margin-top: 20px;
}

.pipeline-group {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
}

.pipeline-group-header {
  padding: 14px 18px;
  background: var(--panel-alt);
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.pipeline-group-header h3 {
  margin: 0;
  font-size: 1rem;
}

.pipeline-step {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--line);
}

.pipeline-step:last-child {
  border-bottom: 0;
}

.pipeline-entity {
  min-width: 0;
  padding: 12px;
  background: #0b0b0b;
  border: 1px solid var(--line);
  border-radius: 10px;
}

.pipeline-entity.source {
  border-left: 3px solid var(--accent);
}

.pipeline-entity.target {
  border-left: 3px solid var(--success);
}

.pipeline-entity .entity-role {
  display: block;
  color: var(--muted);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 5px;
}

.pipeline-entity .entity-name {
  display: block;
  overflow-wrap: anywhere;
  font-family: Consolas, "SFMono-Regular", monospace;
  font-size: 0.88rem;
}

.pipeline-connector {
  display: grid;
  justify-items: center;
  gap: 5px;
  color: var(--accent);
  text-align: center;
}

.pipeline-connector .relation-kind {
  font-size: 0.76rem;
  color: var(--text);
  overflow-wrap: anywhere;
}

.pipeline-connector .arrow {
  font-size: 1.3rem;
  line-height: 1;
}

.pipeline-meta {
  grid-column: 1 / -1;
  color: var(--muted);
  font-size: 0.8rem;
  overflow-wrap: anywhere;
}

.graph-disclosure {
  margin-top: 28px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--panel);
  overflow: hidden;
}

.graph-disclosure > summary {
  cursor: pointer;
  padding: 18px 20px;
  font-weight: 700;
  color: var(--accent);
  background: var(--panel-alt);
}

.graph-disclosure > summary:hover {
  background: #1b171a;
}

.graph-disclosure[open] > .graph-description {
  padding: 0 20px;
  color: var(--muted);
}

.graph-disclosure #relation-map-shell {
  margin: 16px;
}

@media (max-width: 600px) {
  .pipeline-step {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .pipeline-connector {
    grid-template-columns: auto 1fr;
    justify-items: start;
    text-align: left;
  }

  .pipeline-connector .arrow {
    transform: rotate(90deg);
  }
}

/* Individual entity rows expand into their method/function/source details. */
.entity-expandable { padding: 0; overflow: hidden; }
.entity-row-summary {
  display: grid; grid-template-columns: minmax(180px, 1fr) minmax(120px, .5fr) minmax(120px, .5fr) minmax(260px, 1.7fr) auto;
  align-items: center; gap: 14px; padding: 13px 10px; cursor: pointer; list-style: none;
}
.entity-row-summary::-webkit-details-marker { display: none; }
.entity-row-summary:hover { background: rgba(255,255,255,.018); }
.entity-row-name { min-width: 0; overflow-wrap: anywhere; }
.entity-row-summary .meta { margin: 0; min-width: 0; overflow-wrap: anywhere; font-size: .72rem; }
.entity-row-action { color: var(--accent); font-size: .68rem; white-space: nowrap; }
.entity-expandable[open] .entity-row-action { font-size: 0; }
.entity-expandable[open] .entity-row-action::after { content: "Hide ↑"; font-size: .68rem; }
.entity-expandable[open] { border-color: rgba(255,107,157,.34); width: 100%; min-width: 0; }
.entity-expanded-view { width: 100%; min-width: 0; padding: 16px 18px 18px; border-top: 1px solid var(--line); background: #0b0b0b; }
.entity-expanded-description { margin: 0 0 14px; color: var(--muted); }
.entity-expanded-facts { display: grid; gap: 8px; margin: 0 0 14px; }
.entity-expanded-facts > div { display: grid; grid-template-columns: 100px minmax(0,1fr); gap: 12px; }
.entity-expanded-facts dt, .entity-detail-label { color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; }
.entity-expanded-facts dd { margin: 0; overflow-wrap: anywhere; }
.entity-members { margin-top: 14px; }
.entity-child-row { display: grid; gap: 4px; padding: 9px 0; border-bottom: 1px solid #202020; }
.entity-child-row:last-child { border-bottom: 0; }
.entity-child-row span { color: var(--muted); font-size: .82rem; }
.entity-source-preview { width: 100%; min-width: 0; margin-top: 14px; }
.entity-source-preview .entity-detail-label { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 7px; }
.entity-source-preview pre { width: 100%; min-width: 0; margin: 0; max-height: 300px; overflow: auto; padding: 13px; border: 1px solid var(--line); border-radius: 10px; background: #070707; }
.entity-source-preview code { font-family: Consolas, "SFMono-Regular", monospace; font-size: .78rem; white-space: pre; }
@media (max-width: 900px) {
  .entity-row-summary { grid-template-columns: 1fr auto; }
  .entity-row-summary .meta { grid-column: 1 / -1; }
}
"""

PAW_SVG = """
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
"""

RELATION_MAP_JS = '\n(() => {\n  "use strict";\n\n  const dataElement = document.getElementById("relation-map-data");\n  const grid = document.getElementById("relation-card-grid");\n  const search = document.getElementById("relation-map-search");\n  const kindFilter = document.getElementById("relation-map-kind");\n  const count = document.getElementById("relation-map-count");\n  const pagination = document.getElementById("relation-map-pagination");\n\n  if (!dataElement || !grid) return;\n\n  let graph;\n  try {\n    graph = JSON.parse(dataElement.textContent || "{}");\n  } catch (error) {\n    grid.textContent = "The relationship data could not be read.";\n    return;\n  }\n\n  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];\n  const edges = Array.isArray(graph.edges) ? graph.edges : [];\n  const byId = new Map(nodes.map(node => [String(node.id), node]));\n  const pageSize = 80;\n  let page = 0;\n  let filtered = nodes.slice();\n\n  const esc = value => String(value ?? "").replace(/[&<>"\']/g, char => ({\n    "&": "&amp;", "<": "&lt;", ">": "&gt;",\n    \'"\': "&quot;", "\'": "&#39;"\n  })[char]);\n\n  const value = (obj, ...keys) => {\n    for (const key of keys) {\n      if (obj && obj[key] !== undefined && obj[key] !== null && obj[key] !== "") {\n        return obj[key];\n      }\n    }\n    return "";\n  };\n\n  const kindOf = node => String(value(node, "kind", "type") || "unknown");\n  const labelOf = node => String(value(node, "label", "name", "qualified_name") || node.id || "Unnamed item");\n  const pathOf = node => String(value(node, "path", "source_file", "file_path") || "");\n  const evidenceOf = item => value(item, "evidence", "evidence_level") || "Not specified";\n\n  const incident = new Map();\n  for (const edge of edges) {\n    const from = String(edge.source ?? "");\n    const to = String(edge.target ?? "");\n    if (!incident.has(from)) incident.set(from, { incoming: [], outgoing: [] });\n    if (!incident.has(to)) incident.set(to, { incoming: [], outgoing: [] });\n    incident.get(from).outgoing.push(edge);\n    incident.get(to).incoming.push(edge);\n  }\n\n  const kinds = [...new Set(nodes.map(kindOf))].sort((a, b) => a.localeCompare(b));\n  for (const kind of kinds) {\n    const option = document.createElement("option");\n    option.value = kind;\n    option.textContent = kind;\n    kindFilter.appendChild(option);\n  }\n\n  function relatedMarkup(list, direction) {\n    if (!list.length) return \'<p class="muted">No \' + direction + \' relationships detected.</p>\';\n    return \'<ul class="relation-links">\' + list.map(edge => {\n      const otherId = direction === "incoming" ? String(edge.source) : String(edge.target);\n      const other = byId.get(otherId);\n      const otherName = other ? labelOf(other) : otherId;\n      const relation = value(edge, "label", "kind") || "related to";\n      return \'<li><button type="button" class="relation-link" data-open-node="\' +\n        esc(otherId) + \'">\' + esc(otherName) + \'</button>\' +\n        \'<span class="muted"> ? \' + esc(relation) + \'</span></li>\';\n    }).join("") + "</ul>";\n  }\n\n  function cardMarkup(node) {\n    const id = String(node.id ?? "");\n    const links = incident.get(id) || { incoming: [], outgoing: [] };\n    const metadata = node.metadata && typeof node.metadata === "object"\n      ? Object.entries(node.metadata)\n      : [];\n    const description = value(node, "description", "docstring", "summary", "explanation");\n    const qualified = value(node, "qualified_name");\n    const line = value(node, "line");\n    const evidence = evidenceOf(node);\n\n    return \'<article class="card relation-card" id="relation-node-\' + esc(id) + \'">\' +\n      \'<div class="relation-card-heading">\' +\n        \'<span class="badge">\' + esc(kindOf(node)) + \'</span>\' +\n        \'<span class="muted relation-count">\' +\n          links.incoming.length + \' in ? \' + links.outgoing.length + \' out</span>\' +\n      \'</div>\' +\n      \'<h3>\' + esc(labelOf(node)) + \'</h3>\' +\n      (pathOf(node) ? \'<p class="relation-path">\' + esc(pathOf(node)) +\n        (line ? \':\' + esc(line) : \'\') + \'</p>\' : \'\') +\n      \'<details class="relation-details">\' +\n        \'<summary>View details and connections</summary>\' +\n        \'<div class="relation-detail-body">\' +\n          (description ? \'<p>\' + esc(description) + \'</p>\' :\n            \'<p class="muted">No description was recorded for this item.</p>\') +\n          (qualified && qualified !== labelOf(node) ?\n            \'<p><strong>Qualified name:</strong> \' + esc(qualified) + \'</p>\' : \'\') +\n          \'<p><strong>Evidence:</strong> \' + esc(evidence) + \'</p>\' +\n          (node.source_location ? \'<p><strong>Source location:</strong> \' +\n            esc(node.source_location) + \'</p>\' : \'\') +\n          \'<h4>Outgoing relationships (\' + links.outgoing.length + \')</h4>\' +\n          relatedMarkup(links.outgoing, "outgoing") +\n          \'<h4>Incoming relationships (\' + links.incoming.length + \')</h4>\' +\n          relatedMarkup(links.incoming, "incoming") +\n          (metadata.length ? \'<h4>Additional metadata</h4><dl>\' +\n            metadata.map(([key, val]) => \'<dt>\' + esc(key) +\n              \'</dt><dd>\' + esc(typeof val === "object" ? JSON.stringify(val) : val) +\n              \'</dd>\').join("") + \'</dl>\' : \'\') +\n        \'</div>\' +\n      \'</details>\' +\n    \'</article>\';\n  }\n\n  function applyFilters(resetPage = true) {\n    const query = String(search.value || "").trim().toLowerCase();\n    const selectedKind = kindFilter.value;\n\n    filtered = nodes.filter(node => {\n      if (selectedKind && kindOf(node) !== selectedKind) return false;\n      if (!query) return true;\n      const haystack = [\n        labelOf(node), kindOf(node), pathOf(node),\n        value(node, "qualified_name", "description", "docstring")\n      ].join(" ").toLowerCase();\n      return haystack.includes(query);\n    });\n\n    if (resetPage) page = 0;\n    render();\n  }\n\n  function render() {\n    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));\n    page = Math.min(Math.max(page, 0), pages - 1);\n    const start = page * pageSize;\n    const visible = filtered.slice(start, start + pageSize);\n\n    count.textContent = "Showing " + (filtered.length ? start + 1 : 0) +\n      "?" + Math.min(start + pageSize, filtered.length) +\n      " of " + filtered.length + " matching items ? " +\n      nodes.length + " nodes ? " + edges.length + " relationships";\n\n    grid.innerHTML = visible.length\n      ? visible.map(cardMarkup).join("")\n      : \'<div class="card"><p>No matching items. Try a different search or filter.</p></div>\';\n\n    pagination.innerHTML = "";\n    const previous = document.createElement("button");\n    previous.type = "button";\n    previous.textContent = "Previous";\n    previous.disabled = page === 0;\n    previous.addEventListener("click", () => {\n      page--;\n      render();\n      grid.scrollIntoView({ behavior: "smooth", block: "start" });\n    });\n\n    const status = document.createElement("span");\n    status.textContent = "Page " + (page + 1) + " of " + pages;\n\n    const next = document.createElement("button");\n    next.type = "button";\n    next.textContent = "Next";\n    next.disabled = page >= pages - 1;\n    next.addEventListener("click", () => {\n      page++;\n      render();\n      grid.scrollIntoView({ behavior: "smooth", block: "start" });\n    });\n\n    pagination.append(previous, status, next);\n  }\n\n  grid.addEventListener("click", event => {\n    const button = event.target.closest("[data-open-node]");\n    if (!button) return;\n\n    const targetId = button.getAttribute("data-open-node");\n    const target = byId.get(targetId);\n    if (!target) return;\n\n    search.value = labelOf(target);\n    kindFilter.value = "";\n    applyFilters();\n\n    const card = document.getElementById("relation-node-" + CSS.escape(targetId));\n    if (card) {\n      card.scrollIntoView({ behavior: "smooth", block: "start" });\n      const details = card.querySelector("details");\n      if (details) details.open = true;\n    }\n  });\n\n  search.addEventListener("input", () => applyFilters());\n  kindFilter.addEventListener("change", () => applyFilters());\n\n  const reset = document.getElementById("relation-map-reset");\n  if (reset) reset.addEventListener("click", () => {\n    search.value = "";\n    kindFilter.value = "";\n    applyFilters();\n  });\n\n  applyFilters();\n})();\n'


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def _readme_title(project: Project) -> str:
    """Use the README's first H1 as the human-facing project name when present."""
    text = _read_readme(project)
    if text:
        for line in text.splitlines():
            match = re.match(r"^\s*#\s+(.+?)\s*#*\s*$", line)
            if match:
                title = re.sub(r"[`*_]", "", match.group(1)).strip()
                if title:
                    return title
    return ""


def _project_name(project: Project) -> str:
    return _readme_title(project) or project.name or "Project"


def _readme_path(project: Project) -> Path | None:
    """Find the project README without requiring an exact filename case."""
    root = Path(project.root)
    preferred = ["README.md", "README.markdown", "README"]
    for name in preferred:
        candidate = root / name
        if candidate.is_file():
            return candidate
    try:
        for candidate in root.iterdir():
            if candidate.is_file() and candidate.name.lower() in {
                "readme.md",
                "readme.markdown",
                "readme",
            }:
                return candidate
    except OSError:
        pass
    return None


def _read_readme(project: Project) -> str:
    path = _readme_path(project)
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _markdown_inline(value: str) -> str:
    """Render common README Markdown inline syntax to safe HTML."""
    escaped = html.escape(value, quote=False)
    escaped = re.sub(
        r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+["\']([^"\']*)["\'])?\)',
        lambda m: '<img alt="'
        + html.escape(m.group(1), quote=True)
        + '" src="'
        + html.escape(m.group(2), quote=True)
        + '"'
        + (
            (' title="' + html.escape(m.group(3), quote=True) + '"')
            if m.group(3)
            else ""
        )
        + ">",
        escaped,
    )
    escaped = re.sub(
        r'\[([^\]]+)\]\(([^)\s]+)(?:\s+["\']([^"\']*)["\'])?\)',
        lambda m: '<a href="'
        + html.escape(m.group(2), quote=True)
        + '"'
        + ">"
        + m.group(1)
        + "</a>",
        escaped,
    )
    escaped = re.sub(r"<(https?://[^>]+)>", r'<a href="\1">\1</a>', escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", escaped)
    return escaped


def _normalize_readme_markdown(text: str) -> str:
    """Normalize common README transport/encoding artifacts before parsing."""
    text = text.replace("\ufeff", "")
    text = text.replace("\ufffd", "")
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    text = text.replace("\\t", "\t")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Some generated/transported READMEs arrive flattened into one line with
    # Markdown section separators. Turn those separators back into real lines.
    text = re.sub(r"\s+---\s+(?=#{1,6}\s+)", "\n\n", text)
    text = re.sub(r"(?<!\n)\s+(#{1,6}\s+[^\n]+)", r"\n\n\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _render_markdown(text: str) -> str:
    """Convert README Markdown into structured HTML at generation time."""
    lines = _normalize_readme_markdown(text).split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    list_items: list[tuple[str, str]] = []
    quote_lines: list[str] = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    table_rows: list[list[str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append(
                "<p>"
                + " ".join(_markdown_inline(x.strip()) for x in paragraph)
                + "</p>"
            )
            paragraph.clear()

    def flush_list() -> None:
        if not list_items:
            return
        tag = list_items[0][0]
        out.append(
            "<"
            + tag
            + ">"
            + "".join("<li>" + item + "</li>" for _, item in list_items)
            + "</"
            + tag
            + ">"
        )
        list_items.clear()

    def flush_quote() -> None:
        if quote_lines:
            out.append(
                "<blockquote>"
                + "\n".join(_markdown_inline(x) for x in quote_lines)
                + "</blockquote>"
            )
            quote_lines.clear()

    def flush_table() -> None:
        nonlocal table_rows
        if len(table_rows) < 2:
            table_rows = []
            return
        header = table_rows[0]
        body = (
            table_rows[2:]
            if re.match(r"^\\s*:?-{3,}:?\\s*$", "|".join(table_rows[1]))
            else table_rows[1:]
        )
        parts = ['<div class="readme-table-wrap"><table><thead><tr>']
        parts.extend(
            "<th>" + _markdown_inline(cell.strip()) + "</th>" for cell in header
        )
        parts.append("</tr></thead>")
        if body:
            parts.append("<tbody>")
            for row in body:
                parts.append("<tr>")
                parts.extend(
                    "<td>" + _markdown_inline(cell.strip()) + "</td>" for cell in row
                )
                parts.append("</tr>")
            parts.append("</tbody>")
        parts.append("</table></div>")
        out.append("".join(parts))
        table_rows = []

    def is_table_separator(line: str) -> bool:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        return bool(cells) and all(re.match(r"^:?-{3,}:?$", c) for c in cells)

    for raw in lines:
        line = raw.rstrip()
        fence = re.match(r"^\s*```\s*([\w+.-]*)\s*$", line)
        if fence:
            flush_paragraph()
            flush_list()
            flush_quote()
            flush_table()
            if in_code:
                cls = (
                    f' class="language-{html.escape(code_lang, quote=True)}"'
                    if code_lang
                    else ""
                )
                out.append(
                    "<pre><code"
                    + cls
                    + ">"
                    + html.escape("\n".join(code_lines), quote=False)
                    + "</code></pre>"
                )
                in_code = False
                code_lang = ""
                code_lines = []
            else:
                in_code = True
                code_lang = fence.group(1)
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            flush_quote()
            flush_table()
            continue

        heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            flush_list()
            flush_quote()
            flush_table()
            level = len(heading.group(1))
            out.append(
                f"<h{level}>" + _markdown_inline(heading.group(2)) + f"</h{level}>"
            )
            continue

        if re.match(r"^\s*([-*_])(?:\s*\1){2,}\s*$", line):
            flush_paragraph()
            flush_list()
            flush_quote()
            flush_table()
            out.append("<hr>")
            continue

        if "|" in line and (
            table_rows
            or (
                lines.index(raw) + 1 < len(lines)
                and is_table_separator(lines[lines.index(raw) + 1])
            )
        ):
            flush_paragraph()
            flush_list()
            flush_quote()
            table_rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        if table_rows and is_table_separator(line):
            table_rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        if table_rows and "|" not in line:
            flush_table()

        bullet = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if bullet:
            flush_paragraph()
            flush_quote()
            flush_table()
            if list_items and list_items[0][0] != "ul":
                flush_list()
            list_items.append(("ul", _markdown_inline(bullet.group(1))))
            continue
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if ordered:
            flush_paragraph()
            flush_quote()
            flush_table()
            if list_items and list_items[0][0] != "ol":
                flush_list()
            list_items.append(("ol", _markdown_inline(ordered.group(1))))
            continue
        quote = re.match(r"^\s*>\s?(.*)$", line)
        if quote:
            flush_paragraph()
            flush_list()
            flush_table()
            quote_lines.append(quote.group(1))
            continue

        flush_list()
        flush_quote()
        flush_table()
        paragraph.append(line.strip())

    if in_code:
        cls = (
            f' class="language-{html.escape(code_lang, quote=True)}"'
            if code_lang
            else ""
        )
        out.append(
            "<pre><code"
            + cls
            + ">"
            + html.escape("\n".join(code_lines), quote=False)
            + "</code></pre>"
        )
    flush_paragraph()
    flush_list()
    flush_quote()
    flush_table()
    return "".join(out)


def _readme_sections(project: Project) -> dict[str, str]:
    """Return README sections keyed by normalized heading name."""
    text = _read_readme(project)
    if not text:
        return {}
    sections: dict[str, list[str]] = {"__intro__": []}
    current = "__intro__"
    for line in text.splitlines():
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            current = re.sub(r"[^a-z0-9]+", " ", match.group(1).lower()).strip()
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {
        key: "\n".join(value).strip()
        for key, value in sections.items()
        if "\n".join(value).strip()
    }


def _project_description(project: Project) -> str:
    """Use the README lead as the short, human-facing project description."""
    text = _read_readme(project)
    if text:
        lines = text.replace("\r\n", "\n").split("\n")
        lead: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if lead:
                    break
                continue
            if re.match(r"^#{1,6}\s+", stripped):
                if lead:
                    break
                continue
            if stripped.startswith("```") or stripped.startswith(
                (">", "- ", "* ", "+ ")
            ):
                if lead:
                    break
                continue
            lead.append(re.sub(r"[`*_>#]", "", stripped))
            if len(" ".join(lead)) >= 220:
                break
        if lead:
            # Small overview cards should stay compact: use only the first
            # complete sentence from the README lead. The full README remains
            # available in the dedicated README section below.
            text = " ".join(lead).strip()
            match = re.search(r"^(.+?[.!?](?:\s|$))", text)
            return (match.group(1).strip() if match else text).strip()
    description = project.metadata.get("description")
    if description:
        return str(description)
    return "Project purpose unknown."


def _languages(project: Project) -> list[str]:
    return sorted({file.language for file in project.files if file.language})


def _relationship_badge(value: str) -> str:
    key = (value or "UNKNOWN").upper()
    css = key.lower()
    return f'<span class="badge {css}" aria-label="Evidence status: { _escape(key) }">{_escape(key)}</span>'


def _evidence_summary(project: Project) -> str:
    """Show useful project evidence without inventing relationships for empty states."""
    labels = ("DECLARED", "DETECTED", "INFERRED", "UNKNOWN")
    grouped: dict[str, list] = {label: [] for label in labels}

    for relationship in project.relationships:
        key = str(relationship.evidence or "UNKNOWN").upper()
        if key not in grouped:
            key = "UNKNOWN"
        grouped[key].append(relationship)

    def row(name: object, value: object) -> str:
        return (
            '<li><span class="evidence-kind">'
            + _escape(name)
            + '</span><strong>'
            + _escape(value)
            + '</strong></li>'
        )

    entries: list[str] = []
    for label in labels:
        relationships = grouped[label]
        kind_counts: dict[str, int] = {}
        for relationship in relationships:
            kind = str(getattr(relationship, "kind", None) or "unspecified")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1

        data_rows: list[str] = []

        # Relationship evidence remains exact and evidence-labelled.
        for kind, count in sorted(
            kind_counts.items(),
            key=lambda pair: (-pair[1], pair[0].lower()),
        ):
            data_rows.append(row(kind, count))

        # Populate the cards with other facts that genuinely belong to that
        # evidence class instead of pretending zero-count relationships exist.
        if label == "DECLARED":
            readme = _readme_path(project)
            if readme is not None:
                data_rows.append(row("README", "present"))
            if project.name:
                data_rows.append(row("Project name", project.name))
            description = project.metadata.get("description")
            if description:
                data_rows.append(row("Description", str(description)))
            declared_languages = project.metadata.get("languages")
            if declared_languages:
                if isinstance(declared_languages, (list, tuple, set)):
                    declared_languages = ", ".join(str(x) for x in declared_languages)
                data_rows.append(row("Declared languages", declared_languages))

        elif label == "DETECTED":
            data_rows.extend(
                [
                    row("Files", len(project.files)),
                    row("Languages", len(_languages(project))),
                    row("Classes", len(project.classes)),
                    row("Functions", len(project.functions)),
                    row("Methods", len(project.methods)),
                    row("Relationships", len(relationships)),
                ]
            )

        elif label == "INFERRED":
            if not relationships:
                data_rows.append(
                    row("Inferred relationships", "none recorded by static analysis")
                )

        elif label == "UNKNOWN":
            if not relationships:
                data_rows.append(row("Unknown relationships", "none recorded"))
            data_rows.append(
                row(
                    "Runtime behavior",
                    "not established by static analysis",
                )
            )
            data_rows.append(
                row(
                    "External/dynamic behavior",
                    "not established unless present in scanned evidence",
                )
            )

        data_html = (
            '<details class="evidence-data">'
            '<summary>View evidence data</summary>'
            '<ul>' + "".join(data_rows) + '</ul>'
            '</details>'
            if data_rows
            else '<p class="evidence-empty">No evidence was recorded for this category.</p>'
        )

        entries.append(
            '<div class="tile evidence-tile">'
            f'<h3>{_escape(label)}</h3>'
            f'<p class="evidence-total"><strong>{len(relationships)}</strong> relationship(s)</p>'
            + data_html
            + '</div>'
        )

    return '<div class="grid evidence-grid">' + "".join(entries) + "</div>"


def _nav(current: str) -> str:
    pages = [
        ("index.html", "Project overview"),
        ("entities.html", "Entities"),
        ("relationships.html", "Relationships"),
        ("relation-map.html", "Relation Map"),
    ]
    current_map = {
        "index": "index.html",
        "entities": "entities.html",
        "relationships": "relationships.html",
        "relation-map": "relation-map.html",
    }
    html_links = []
    for href, label in pages:
        active = " active" if href == current_map.get(current, "index.html") else ""
        html_links.append(
            f'<a class="{active.strip()}" href="{href}">{_escape(label)}</a>'
        )
    return "".join(html_links)


def _stat_card(label: str, value: str) -> str:
    return (
        '<div class="metric">'
        f'<span class="metric-label">{_escape(label)}</span>'
        f'<span class="metric-value">{_escape(value)}</span>'
        "</div>"
    )



def _readme_image_reference(project: Project) -> tuple[Path, str] | None:
    """Return the first usable local image referenced by the README."""
    readme = _readme_path(project)
    text = _read_readme(project)
    if readme is None or not text:
        return None

    candidates: list[tuple[str, str]] = []

    markdown = re.search(
        r'!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+["\'][^"\']*["\'])?\s*\)',
        text,
        flags=re.IGNORECASE,
    )
    if markdown:
        candidates.append((markdown.group(2), markdown.group(1) or "Project image"))

    html_image = re.search(
        r'<img\b[^>]*?\bsrc\s*=\s*["\']([^"\']+)["\'][^>]*>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if html_image:
        candidates.append((html_image.group(1), "Project image"))

    root = Path(project.root).resolve()
    for raw_src, alt in candidates:
        src = html.unescape(raw_src.strip())
        if not src or src.startswith(("http://", "https://", "//", "data:", "#")):
            continue

        local_ref = src.split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
        candidate = (readme.parent / Path(local_ref)).resolve()

        try:
            candidate.relative_to(root)
        except ValueError:
            continue

        if candidate.is_file() and candidate.suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"
        }:
            return candidate, alt

    return None


def _prepare_readme_title_image(project: Project, output_path: Path) -> None:
    """Copy the README's first local image into assets/readme for the title card."""
    metadata = getattr(project, "metadata", None)
    if not isinstance(metadata, dict):
        return

    metadata.pop("_barkly_readme_title_image", None)
    metadata.pop("_barkly_readme_title_image_alt", None)

    image = _readme_image_reference(project)
    if image is None:
        return

    source, alt = image
    target_dir = output_path / "assets" / "readme"
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.name).strip("-") or "readme-image"
    target = target_dir / safe_name
    shutil.copy2(source, target)

    metadata["_barkly_readme_title_image"] = f"assets/readme/{safe_name}"
    metadata["_barkly_readme_title_image_alt"] = alt


def _render_readme_title_image(project: Project) -> str:
    """Render the prepared README image inside the main title card."""
    metadata = getattr(project, "metadata", None)
    if not isinstance(metadata, dict):
        return ""

    src = metadata.get("_barkly_readme_title_image")
    if not src:
        return ""

    alt = metadata.get("_barkly_readme_title_image_alt") or "Project image"
    return (
        '<div class="hero-readme-image">'
        f'<img src="{html.escape(str(src), quote=True)}" '
        f'alt="{html.escape(str(alt), quote=True)}" loading="eager">'
        '</div>'
    )

def _render_readme(project: Project) -> str:
    """Render README content as a calm, structured, human-readable document."""
    text = _read_readme(project)
    if not text:
        if _readme_path(project) is None:
            return '<div class="empty-state">No README was found in the project root.</div>'
        return '<div class="empty-state">README exists but could not be read.</div>'

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    title = _readme_title(project)
    body_lines: list[str] = []
    skipped_title = False
    for line in lines:
        if not skipped_title and re.match(r"^\s*#\s+", line):
            skipped_title = True
            continue
        body_lines.append(line)

    rendered = _render_markdown("\n".join(body_lines))
    if not rendered.strip():
        return '<div class="empty-state">README is present but contains no readable content.</div>'

    return (
        '<article class="readme-panel">'
        '<header class="readme-intro">'
        '<span class="readme-kicker">PROJECT README</span>'
        f'<h2>{_escape(title or "Project documentation")}</h2>'
        f'<p class="readme-lead">{_escape(_project_description(project))}</p>'
        "</header>"
        f'<div class="readme-content">{rendered}</div>'
        "</article>"
    )


def _render_entity_summary(project: Project) -> str:
    items = []
    for item in sorted(project.classes, key=lambda node: node.name):
        methods = ", ".join(item.methods) if item.methods else "No methods discovered"
        items.append(f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">{_escape(item.path)}</div>
              <div class="meta">Methods: {_escape(methods)}</div>
            </div>
            """)
    for item in sorted(project.functions, key=lambda node: node.name):
        signature = (
            f"{item.name}({', '.join(item.parameters)})"
            if item.parameters
            else item.name
        )
        items.append(f"""
            <div class="entity-item">
              <h3>{_escape(signature)}</h3>
              <div class="meta">{_escape(item.path)}</div>
              <div class="meta">Return: {_escape(item.return_type or 'unknown')}</div>
            </div>
            """)
    for item in sorted(project.methods, key=lambda node: node.name):
        details = item.class_name or "method"
        items.append(f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">Class: {_escape(details)}</div>
              <div class="meta">{_escape(item.path)}</div>
            </div>
            """)
    if not items:
        return '<div class="empty-state">No project entities were detected.</div>'
    return '<div class="entity-list">' + "".join(items) + "</div>"


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
            doc = (
                getattr(item, "documentation", None)
                or "No source documentation available."
            )
            line = getattr(item, "line_start", None)
            location = f"{item.path}:{line}" if line else item.path
            items.append(f"""
                <div class="entity-item">
                  <h3>{_escape(signature)}</h3>
                  <div class="meta">{_escape(name)} · {_escape(location)}</div>
                  <p>{_escape(doc[:220])}</p>
                </div>
                """)
        if items:
            entries.append(
                f"<div class='section'><h3>{_escape(name)}</h3><div class='entity-list'>{''.join(items)}</div></div>"
            )

    if not entries:
        return '<div class="empty-state">No source-level method or function references were detected.</div>'
    return "".join(entries)


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
                f"{_escape(str(relationship.source_location))}"
                "</div>"
            )
        items.append(f"""
            <div class="relationship-item">
              <h3><span class="code">{_escape(relationship.source)}</span> → <span class="code">{_escape(relationship.target)}</span></h3>
              <div class="meta">{_relationship_badge(relationship.evidence)} <span class="code">{_escape(relationship.kind)}</span></div>
              {source_location}
              <div class="meta">File: {_escape(relationship.source_file or 'Unknown')}</div>
            </div>
            """)
    mermaid = (
        '<div class="section">'
        "<h3>Relationship map</h3>"
        '<pre class="code" aria-label="Mermaid relationship map">'
        f"{_escape(_relationship_map_mermaid(project))}"
        "</pre>"
        "</div>"
    )
    return '<div class="relationship-list">' + "".join(items) + "</div>" + mermaid


def _render_relationship_pipeline(graph) -> str:
    """Render discovered graph edges as readable source-to-target pipelines."""

    if not graph.edges:
        return (
            '<div class="empty-state">'
            "No relationships were detected for the current scan."
            "</div>"
        )

    # Group by source file so the relationships are easier to browse.
    grouped: dict[str, list] = {}

    for edge in graph.edges:
        source_file = str(edge.source_file or "Unknown source file")
        grouped.setdefault(source_file, []).append(edge)

    groups = []

    for source_file in sorted(grouped):
        edges = sorted(
            grouped[source_file],
            key=lambda edge: (
                str(edge.source).lower(),
                str(edge.kind).lower(),
                str(edge.target).lower(),
            ),
        )

        steps = []

        for edge in edges:
            evidence = str(edge.evidence or "UNKNOWN").upper()
            evidence_css = evidence.lower()

            explanation = str(
                edge.explanation or "Relationship recorded during static analysis."
            )

            steps.append(f"""
                <article class="pipeline-step">
                  <div class="pipeline-entity source">
                    <span class="entity-role">Source</span>
                    <span class="entity-name">
                      {_escape(edge.source)}
                    </span>
                  </div>

                  <div class="pipeline-connector">
                    <span class="relation-kind">
                      {_escape(edge.kind or "related to")}
                    </span>
                    <span class="arrow" aria-hidden="true">→</span>
                  </div>

                  <div class="pipeline-entity target">
                    <span class="entity-role">Target</span>
                    <span class="entity-name">
                      {_escape(edge.target)}
                    </span>
                  </div>

                  <div class="pipeline-meta">
                    {_relationship_badge(evidence)}
                    <span>Source file: {_escape(edge.source_file or "Unknown")}</span>
                    <p>{_escape(explanation)}</p>
                  </div>
                </article>
                """)

        groups.append(f"""
            <section class="pipeline-group">
              <div class="pipeline-group-header">
                <h3>{_escape(source_file)}</h3>
                <span class="badge detected">
                  {len(edges)} relationship(s)
                </span>
              </div>
              {''.join(steps)}
            </section>
            """)

    return '<div class="pipeline-list">' + "".join(groups) + "</div>"


def _render_full_spider_map(project: Project) -> str:
    """Render the complete internal project graph, including code-level nodes."""
    from html import escape
    from math import cos, sin, pi

    # The default graph view is used rather than the filtered project overview.
    graph = build_relation_graph(
        project,
        max_nodes=None,
        max_edges=None,
    )

    nodes = list(graph.nodes)
    if not nodes:
        return """
        <section class="section" id="full-spider-map">
          <h2>Full Project Spider Map</h2>
          <p class="section-subtitle">
            No graph nodes were returned. Check the relationship graph builder.
          </p>
        </section>
        """

    node_by_id = {str(node.id): node for node in nodes}
    count = len(nodes)

    # Use a roomy circular layout. The SVG remains scrollable for large projects.
    radius = max(320.0, count * 15.0)
    margin = 190.0
    width = int(radius * 2 + margin * 2)
    height = int(radius * 2 + margin * 2)
    cx = width / 2
    cy = height / 2

    positions = {}
    for index, node in enumerate(nodes):
        angle = (2 * pi * index / count) - pi / 2
        positions[str(node.id)] = (
            cx + radius * cos(angle),
            cy + radius * sin(angle),
        )

    def label_of(node):
        return str(
            getattr(node, "label", None)
            or getattr(node, "name", None)
            or getattr(node, "id", "Component")
        )

    def node_kind(node):
        metadata = getattr(node, "metadata", {}) or {}
        return str(
            metadata.get("kind")
            or metadata.get("type")
            or metadata.get("category")
            or ""
        ).lower()

    def color_of(node):
        kind = node_kind(node)
        identity = (
            str(getattr(node, "id", "")) + " " + label_of(node) + " " + kind
        ).lower()

        if "method" in identity:
            return "#efa0cf"
        if "function" in identity:
            return "#f3bd82"
        if "class" in identity:
            return "#96aaff"
        if any(term in identity for term in ("module", "package", "file")):
            return "#6edca5"
        return "#b8a0ef"

    edge_markup = []
    connection_rows = []
    seen_edges = set()

    for edge in graph.edges:
        source_id = str(edge.source)
        target_id = str(edge.target)

        if source_id not in positions or target_id not in positions:
            continue

        # Preserve distinct relationship types between the same two nodes.
        metadata = getattr(edge, "metadata", {}) or {}
        relation = str(
            metadata.get("kind")
            or metadata.get("type")
            or metadata.get("relationship")
            or "connects to"
        )
        identity = (source_id, target_id, relation)
        if identity in seen_edges:
            continue
        seen_edges.add(identity)

        x1, y1 = positions[source_id]
        x2, y2 = positions[target_id]

        edge_markup.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}" class="full-spider-edge">'
            f"<title>{escape(relation)}: "
            f"{escape(label_of(node_by_id[source_id]))} ? "
            f"{escape(label_of(node_by_id[target_id]))}</title></line>"
        )

        connection_rows.append(
            "<li><code>"
            + escape(label_of(node_by_id[source_id]))
            + '</code> <span class="full-spider-relation">'
            + escape(relation)
            + "</span> <code>"
            + escape(label_of(node_by_id[target_id]))
            + "</code></li>"
        )

    node_markup = []
    box_width = 154
    box_height = 38

    for node in nodes:
        node_id = str(node.id)
        x, y = positions[node_id]
        label = label_of(node)
        display_label = label.replace("\\", "/")
        if len(display_label) > 22:
            display_label = display_label[:21] + "?"

        node_markup.append(
            f'<g class="full-spider-node" tabindex="0" '
            f'aria-label="{escape(label, quote=True)}">'
            f"<title>{escape(label)}"
            f'{" ? " + escape(node_kind(node)) if node_kind(node) else ""}'
            f"</title>"
            f'<rect x="{x - box_width / 2:.1f}" '
            f'y="{y - box_height / 2:.1f}" '
            f'width="{box_width}" height="{box_height}" rx="8" '
            f'style="stroke:{color_of(node)}"/>'
            f'<text x="{x:.1f}" y="{y + 4:.1f}" '
            f'text-anchor="middle">{escape(display_label)}</text>'
            f"</g>"
        )

    return f"""
    <section class="section" id="full-spider-map">
      <h2>Full Project Spider Map</h2>
      <div class="section-subtitle">
        Code-level view of the project's internal structure.
        Nodes represent everything exposed by the graph builder;
        hover or focus a node or connection to inspect its label.
      </div>
      <div class="card full-spider-card" style="padding:16px;margin-top:16px">
        <div class="full-spider-toolbar">
          <span>{count} nodes</span>
          <span>{len(seen_edges)} relationships</span>
          <span class="meta">Scroll horizontally and vertically to explore.</span>
        </div>
        <div class="full-spider-scroll" tabindex="0"
             role="region" aria-label="Scrollable full project spider map">
          <svg class="full-spider-svg" xmlns="http://www.w3.org/2000/svg"
               viewBox="0 0 {width} {height}"
               role="img" aria-label="Full project code relationship graph">
            <g class="full-spider-edges">{''.join(edge_markup)}</g>
            <g class="full-spider-nodes">{''.join(node_markup)}</g>
          </svg>
        </div>
        <div class="full-spider-legend">
          <span><i style="background:#6edca5"></i> Modules / files</span>
          <span><i style="background:#96aaff"></i> Classes</span>
          <span><i style="background:#f3bd82"></i> Functions</span>
          <span><i style="background:#efa0cf"></i> Methods</span>
          <span><i style="background:#b8a0ef"></i> Other nodes</span>
        </div>
        <details class="architecture-details">
          <summary>Browse all rendered connections ({len(connection_rows)})</summary>
          <ul class="architecture-connection-list">
            {''.join(connection_rows)}
          </ul>
        </details>
      </div>
      <style>
        .full-spider-toolbar,.full-spider-legend {{
          display:flex; flex-wrap:wrap; gap:10px 18px;
          align-items:center; margin-bottom:12px; font-size:.85rem;
        }}
        .full-spider-scroll {{
          max-height:75vh; overflow:auto;
          border:1px solid var(--line); border-radius:10px;
        }}
        .full-spider-svg {{ display:block; min-width:100%; }}
        .full-spider-edge {{
          stroke:var(--muted); stroke-opacity:.45; stroke-width:1.1;
        }}
        .full-spider-node rect {{
          fill:var(--card, #20242d); stroke-width:2;
        }}
        .full-spider-node text {{
          fill:var(--text); font-size:11px; font-weight:600;
          pointer-events:none;
        }}
        .full-spider-node:hover rect,
        .full-spider-node:focus rect {{
          stroke-width:4; filter:brightness(1.15); outline:none;
        }}
        .full-spider-legend span {{ display:inline-flex; gap:6px; align-items:center; }}
        .full-spider-legend i {{ display:inline-block; width:10px; height:10px; border-radius:3px; }}
        .full-spider-relation {{ color:var(--muted); padding:0 5px; }}
      </style>
    </section>
    """




def _render_files(project: Project) -> str:
    if not project.files:
        return '<div class="empty-state">No project files were discovered.</div>'
    items = []
    for item in sorted(project.files, key=lambda node: node.path):
        items.append(f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">Language: {_escape(item.language or 'Unknown')}</div>
              <div class="meta">Path: {_escape(item.path)}</div>
            </div>
            """)
    return '<div class="entity-list">' + "".join(items) + "</div>"




def _render_entity_group(items, empty_message: str) -> str:
    """Render each entity row as its own disclosure with useful code-level details."""
    if not items:
        return f'<div class="empty-state">{_escape(empty_message)}</div>'

    def value(item, *names):
        for name in names:
            candidate = getattr(item, name, None)
            if candidate is not None and candidate != "":
                return candidate
        return None

    def source_excerpt(item, max_lines: int = 14) -> str:
        raw_path = str(value(item, "path", "file_path", "source_file") or "")
        if not raw_path:
            return ""
        candidate = Path(raw_path)
        if not candidate.is_absolute() or not candidate.is_file():
            return ""
        try:
            lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        if not lines:
            return ""
        raw_start = value(item, "line_start", "start_line", "line", "lineno") or 1
        raw_end = value(item, "line_end", "end_line")
        try:
            first = max(1, int(raw_start))
        except (TypeError, ValueError):
            first = 1
        try:
            last = int(raw_end) if raw_end else first + max_lines - 1
        except (TypeError, ValueError):
            last = first + max_lines - 1
        first = min(first, len(lines))
        last = min(max(first, last), first + max_lines - 1, len(lines))
        excerpt = "\n".join(lines[first - 1:last]).rstrip()
        if not excerpt:
            return ""
        return (
            '<div class="entity-source-preview">'
            '<div class="entity-detail-label">Source preview '
            f'<span>lines {first}–{last}</span></div>'
            f'<pre><code>{html.escape(excerpt, quote=False)}</code></pre>'
            '</div>'
        )

    def child_entities(item) -> str:
        children = value(item, "methods", "functions", "members")
        if not children:
            return ""
        if isinstance(children, str):
            children = [part.strip() for part in children.split(",") if part.strip()]
        try:
            children = list(children)
        except TypeError:
            children = [children]
        if not children:
            return ""

        rows = []
        for child in children:
            if isinstance(child, str):
                child_name = child
                signature = child
                child_doc = ""
            else:
                child_name = str(value(child, "name", "qualified_name", "label") or "Unnamed member")
                params = value(child, "parameters", "params")
                if isinstance(params, (list, tuple)):
                    params = ", ".join(str(x) for x in params)
                signature = f"{child_name}({params})" if params else child_name
                child_doc = str(value(child, "documentation", "docstring", "description") or "")
            rows.append(
                '<div class="entity-child-row">'
                f'<code>{_escape(signature)}</code>'
                + (f'<span>{_escape(child_doc[:180])}</span>' if child_doc else "")
                + '</div>'
            )
        return (
            '<div class="entity-members">'
            '<div class="entity-detail-label">Methods / functions</div>'
            + "".join(rows)
            + '</div>'
        )

    rendered = []
    for item in sorted(items, key=lambda node: (getattr(node, "path", "") or "", getattr(node, "name", "") or "")):
        name = getattr(item, "name", "") or "Unnamed"
        path = getattr(item, "path", "") or ""
        language = getattr(item, "language", "") or "Unknown"
        kind = getattr(item, "kind", "") or item.__class__.__name__
        line = value(item, "line_start", "start_line", "line", "lineno")
        end_line = value(item, "line_end", "end_line")
        documentation = value(item, "documentation", "docstring", "description", "summary")
        parameters = value(item, "parameters", "params", "arguments")
        return_type = value(item, "return_type", "returns")
        class_name = value(item, "class_name", "owner", "parent_class")

        if isinstance(parameters, (list, tuple)):
            parameters = ", ".join(str(x) for x in parameters)

        meta = [
            f'<span class="meta">Type: {_escape(str(kind))}</span>',
            f'<span class="meta">Language: {_escape(str(language))}</span>',
        ]
        if path:
            meta.append(f'<span class="meta">Path: {_escape(str(path))}</span>')

        facts = []
        if class_name:
            facts.append(f'<div><dt>Class</dt><dd>{_escape(str(class_name))}</dd></div>')
        if parameters:
            facts.append(f'<div><dt>Parameters</dt><dd><code>{_escape(str(parameters))}</code></dd></div>')
        if return_type:
            facts.append(f'<div><dt>Returns</dt><dd><code>{_escape(str(return_type))}</code></dd></div>')
        if path:
            location = str(path)
            if line:
                location += f':{line}'
                if end_line and str(end_line) != str(line):
                    location += f'–{end_line}'
            facts.append(f'<div><dt>Source</dt><dd><code>{_escape(location)}</code></dd></div>')

        detail = (
            (f'<p class="entity-expanded-description">{_escape(str(documentation))}</p>' if documentation else '')
            + ('<dl class="entity-expanded-facts">' + ''.join(facts) + '</dl>' if facts else '')
            + child_entities(item)
            + source_excerpt(item)
        )
        if not detail:
            detail = '<p class="muted">No additional source details were recorded for this entity.</p>'

        rendered.append(
            '<details class="entity-item entity-expandable">'
            '<summary class="entity-row-summary">'
            f'<strong class="entity-row-name">{_escape(str(name))}</strong>'
            + ''.join(meta)
            + '<span class="entity-row-action">Expand ↓</span>'
            + '</summary>'
            '<div class="entity-expanded-view">'
            + detail
            + '</div>'
            + '</details>'
        )

    return '<div class="entity-list">' + "".join(rendered) + "</div>"

def _collect_project_entities(project: Project, kind: str):
    """Collect one semantic entity type without mixing it into other cards."""
    wanted = kind.lower().rstrip("s")
    aliases = {
        "class": {"class"},
        "function": {"function", "func"},
        "method": {"method"},
        "module": {"module", "package"},
        "dependency": {"dependency", "import", "include", "require"},
        "relationship": {"relationship"},
    }
    accepted = aliases.get(wanted, {wanted})
    found = []
    seen = set()

    def add(item):
        if item is None:
            return
        key = (
            str(getattr(item, "path", "") or ""),
            str(getattr(item, "name", "") or ""),
            str(getattr(item, "line", "") or ""),
            str(getattr(item, "kind", "") or item.__class__.__name__),
        )
        if key not in seen:
            seen.add(key)
            found.append(item)

    # Prefer explicit normalized Project Model collections when present.
    for attr in (kind, kind.rstrip("s"), kind + "s"):
        value = getattr(project, attr, None)
        if value is not None and not isinstance(value, (str, bytes, dict)):
            try:
                for item in value:
                    add(item)
            except TypeError:
                pass

    # Some readers attach symbols/entities to their source file.
    for file_item in getattr(project, "files", []) or []:
        for attr in ("entities", "symbols", "members", "items"):
            values = getattr(file_item, attr, None)
            if values is None or isinstance(values, (str, bytes, dict)):
                continue
            try:
                iterator = iter(values)
            except TypeError:
                continue
            for item in iterator:
                raw_kind = str(
                    getattr(item, "kind", "")
                    or getattr(item, "type", "")
                    or item.__class__.__name__
                ).lower().replace("_", " ").strip()
                singular = raw_kind.rstrip("s")
                if singular in accepted:
                    add(item)

    return found


def _collect_relationships(project: Project):
    """Use the relationship model itself; never render a missing value as 'Unknown'."""
    relationships = getattr(project, "relationships", None)
    if relationships is None:
        graph = getattr(project, "graph", None)
        relationships = getattr(graph, "relationships", None) if graph is not None else None
    if relationships is None:
        return []
    try:
        return list(relationships)
    except TypeError:
        return []


def _render_relationship_group(items) -> str:
    if not items:
        return '<div class="empty-state">No relationships were discovered.</div>'

    rendered = []
    for rel in items:
        source = (
            getattr(rel, "source", None)
            or getattr(rel, "from_entity", None)
            or getattr(rel, "from_", None)
            or getattr(rel, "source_name", None)
            or "Unknown source"
        )
        target = (
            getattr(rel, "target", None)
            or getattr(rel, "to_entity", None)
            or getattr(rel, "to", None)
            or getattr(rel, "target_name", None)
            or "Unknown target"
        )
        relation = (
            getattr(rel, "kind", None)
            or getattr(rel, "type", None)
            or getattr(rel, "relationship_type", None)
            or "relationship"
        )

        def label(value):
            return str(getattr(value, "name", None) or getattr(value, "path", None) or value)

        rendered.append(
            '<div class="entity-item">'
            f'<h3>{_escape(label(source))} → {_escape(label(target))}</h3>'
            f'<div class="meta">Relationship: {_escape(str(relation))}</div>'
            '</div>'
        )
    return '<div class="entity-list">' + "".join(rendered) + "</div>"



def _render_index_data_section(title: str, description: str, action: str, body: str) -> str:
    search_id = "search-" + "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
    return (
        '<details class="index-section-card searchable-section">'
        '<summary><div class="index-section-heading">'
        f'<h2>{_escape(title)}</h2><p>{_escape(description)}</p>'
        '</div>'
        f'<span class="index-section-action" aria-hidden="true">{_escape(action)} ↓</span>'
        '</summary>'
        '<div class="index-section-body">'
        '<div class="index-card-tools">'
        f'<input id="{_escape(search_id)}" class="index-card-search" type="search" '
        f'placeholder="Search {_escape(title.lower())}…" aria-label="Search {_escape(title.lower())}">'
        '<span class="index-card-count" aria-live="polite"></span>'
        '</div>'
        f'{body}<div class="index-no-results">No matching items.</div>'
        '<button class="index-card-more" type="button">Show all</button>'
        '</div></details>'
    )

def _is_json_project_file(item) -> bool:
    path = str(getattr(item, "path", "") or "").replace("\\", "/").lower()
    name = str(getattr(item, "name", "") or "").lower()
    return path.endswith(".json") or name.endswith(".json")


def _render_json_files(project: Project) -> str:
    json_files = [item for item in project.files if _is_json_project_file(item)]
    if not json_files:
        return '<div class="empty-state">No JSON files were discovered.</div>'
    items = []
    for item in sorted(json_files, key=lambda node: node.path):
        items.append(f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">JSON</div>
              <div class="meta">Path: {_escape(item.path)}</div>
            </div>
            """)
    return '<div class="entity-list">' + "".join(items) + "</div>"


def _render_other_files(project: Project) -> str:
    other_files = [item for item in project.files if not _is_json_project_file(item)]
    if not other_files:
        return '<div class="empty-state">No non-JSON project files were discovered.</div>'
    items = []
    for item in sorted(other_files, key=lambda node: node.path):
        items.append(f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">Language: {_escape(item.language or 'Unknown')}</div>
              <div class="meta">Path: {_escape(item.path)}</div>
            </div>
            """)
    return '<div class="entity-list">' + "".join(items) + "</div>"

def _render_json_data(project: Project) -> str:
    """Render JSON values only from files that are actually JSON."""
    json_files = [item for item in project.files if _is_json_project_file(item)]
    if not json_files:
        return '<div class="empty-state">No JSON data was discovered.</div>'

    rendered = []
    for item in sorted(json_files, key=lambda node: node.path):
        path = getattr(item, "path", "") or ""
        name = getattr(item, "name", "") or path or "JSON file"
        rendered.append(
            '<div class="entity-item">'
            f'<h3>{_escape(str(name))}</h3>'
            '<div class="meta">Type: JSON file</div>'
            f'<div class="meta">Path: {_escape(str(path))}</div>'
            '</div>'
        )
    return '<div class="entity-list">' + "".join(rendered) + "</div>"


def _page_shell(title: str, current: str, body: str) -> str:
    return f"""<!DOCTYPE html>
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
<script>
(() => {{
  const norm = v => (v || "").toLowerCase().trim();
  document.querySelectorAll(".searchable-section").forEach(section => {{
    const body = section.querySelector(".index-section-body");
    const input = section.querySelector(".index-card-search");
    const count = section.querySelector(".index-card-count");
    const items = [...section.querySelectorAll(".entity-list > .entity-item")];
    const empty = section.querySelector(".index-no-results");
    const more = section.querySelector(".index-card-more");
    if (!input || !items.length) {{
      if (input) input.closest(".index-card-tools").style.display = "none";
      if (more) more.style.display = "none";
      return;
    }}

    let expanded = false;
    const update = () => {{
      const q = norm(input.value);
      let matches = 0;
      items.forEach(item => {{
        const match = !q || norm(item.textContent).includes(q);
        item.dataset.searchMatch = match ? "true" : "false";
        item.hidden = !match;
        if (match) matches++;
      }});

      if (q) {{
        body.classList.add("show-all");
        if (more) more.style.display = "none";
      }} else {{
        body.classList.toggle("show-all", expanded);
        if (more) {{
          more.style.display = items.length > 12 ? "block" : "none";
          more.textContent = expanded ? "Show less" : `Show all ${{items.length}}`;
        }}
      }}
      count.textContent = q ? `${{matches}} of ${{items.length}}` : `${{items.length}} items`;
      if (empty) empty.style.display = matches ? "none" : "block";
    }};

    if (more) more.addEventListener("click", () => {{
      expanded = !expanded;
      update();
    }});
    input.addEventListener("input", update);
    input.addEventListener("keydown", e => e.stopPropagation());
    update();
  }});
}})();
</script>
</body>
</html>"""


def _render_project_architecture(project: Project) -> str:
    """Render a native, project-only spider relationship map."""
    from html import escape
    from math import cos, sin, pi

    graph = build_relation_graph(
        project,
        view="project_overview",
        max_nodes=None,
        max_edges=None,
    )

    nodes = list(graph.nodes)
    if not nodes:
        return """
        <section class="section project-architecture" id="project-architecture">
          <h2>Project Spider Map</h2>
          <p class="section-subtitle">No internal project components were found.</p>
        </section>
        """

    node_by_id = {str(node.id): node for node in nodes}
    count = len(nodes)

    # Place components around a ring so relationships form a spider-like map.
    width = max(1100, int(count * 24))
    height = max(760, int(count * 18))
    cx, cy = width / 2, height / 2
    radius = max(230, min(width, height) * 0.39)

    positions = {}
    for index, node in enumerate(nodes):
        angle = (2 * pi * index / count) - (pi / 2)
        positions[str(node.id)] = (
            cx + radius * cos(angle),
            cy + radius * sin(angle),
        )

    def full_label(node):
        return str(getattr(node, "label", None) or getattr(node, "id", "Component"))

    def short_label(value, limit=25):
        value = value.replace("\\", "/")
        if len(value) > limit:
            return value[: limit - 1] + "?"
        return value

    def node_color(node):
        metadata = getattr(node, "metadata", {}) or {}
        identity = (
            " ".join(
                (
                    str(getattr(node, "id", "")),
                    full_label(node),
                    str(metadata.get("kind", "")),
                    str(metadata.get("type", "")),
                    str(metadata.get("path", "")),
                )
            )
            .lower()
            .replace("\\", "/")
        )

        if any(
            term in identity
            for term in (
                "database",
                "repository",
                "repositories",
                "model",
                "schema",
                "storage",
                "persistence",
                "migration",
            )
        ):
            return "#96aaff"
        if any(
            term in identity
            for term in (
                "entrypoint",
                "entry_point",
                "main.py",
                "main.rs",
                "app.py",
                "server.py",
                "routes",
                "router",
                "controller",
                "endpoint",
                "cli",
            )
        ):
            return "#efa0cf"
        return "#6edca5"

    edge_markup = []
    seen_edges = set()

    for edge in graph.edges:
        source_id = str(edge.source)
        target_id = str(edge.target)

        if (
            source_id not in positions
            or target_id not in positions
            or source_id == target_id
        ):
            continue

        identity = (source_id, target_id)
        if identity in seen_edges:
            continue
        seen_edges.add(identity)

        x1, y1 = positions[source_id]
        x2, y2 = positions[target_id]
        metadata = getattr(edge, "metadata", {}) or {}
        relation = (
            metadata.get("kind")
            or metadata.get("type")
            or metadata.get("relationship")
            or "connects to"
        )

        edge_markup.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="spider-edge">'
            f"<title>{escape(str(relation))}: "
            f"{escape(full_label(node_by_id[source_id]))} ? "
            f"{escape(full_label(node_by_id[target_id]))}</title></line>"
        )

    node_markup = []
    box_width, box_height = 170, 48

    for node in nodes:
        node_id = str(node.id)
        x, y = positions[node_id]
        left, top = x - box_width / 2, y - box_height / 2
        label = full_label(node)
        color = node_color(node)

        node_markup.append(
            f'<g class="spider-node" tabindex="0" role="img" '
            f'aria-label="{escape(label, quote=True)}">'
            f"<title>{escape(label)}</title>"
            f'<rect x="{left:.1f}" y="{top:.1f}" '
            f'width="{box_width}" height="{box_height}" rx="10" '
            f'style="stroke:{color}" />'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" '
            f'text-anchor="middle">{escape(short_label(label))}</text>'
            f"</g>"
        )

    return f"""
    <section class="section project-architecture" id="project-architecture">
      <h2>Project Spider Map</h2>
      <div class="section-subtitle">
        Internal components and their detected relationships.
        Hover over a component or connection for its full details.
      </div>
      <div class="card spider-map-card" style="padding:16px;margin-top:16px">
        <div class="spider-legend">
          <span><i class="spider-key spider-key-entry"></i> Entry points</span>
          <span><i class="spider-key spider-key-core"></i> Core components</span>
          <span><i class="spider-key spider-key-data"></i> Data and persistence</span>
          <span class="meta">{count} components ? {len(seen_edges)} connections</span>
        </div>
        <div class="spider-map-scroll" role="region" aria-label="Scrollable project relationship spider map" tabindex="0">
          <svg class="spider-map" xmlns="http://www.w3.org/2000/svg"
               viewBox="0 0 {width} {height}" role="img"
               aria-label="Project component relationship map">
            <defs>
              <marker id="spider-arrow" markerWidth="8" markerHeight="8"
                      refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L6,3 z" fill="var(--muted)" />
              </marker>
            </defs>
            <g class="spider-edges" marker-end="url(#spider-arrow)">
              {''.join(edge_markup)}
            </g>
            <g class="spider-nodes">
              {''.join(node_markup)}
            </g>
          </svg>
        </div>
        <style>
          .spider-legend {{
            display:flex; align-items:center; flex-wrap:wrap;
            gap:12px 18px; margin-bottom:12px; font-size:.85rem;
          }}
          .spider-legend span {{ display:inline-flex; align-items:center; gap:6px; }}
          .spider-key {{ display:inline-block; width:10px; height:10px; border-radius:3px; }}
          .spider-key-entry {{ background:#efa0cf; }}
          .spider-key-core {{ background:#6edca5; }}
          .spider-key-data {{ background:#96aaff; }}
          .spider-map-scroll {{
            width:100%; max-height:75vh; overflow:auto;
            border:1px solid var(--line); border-radius:10px;
            background:var(--bg, transparent);
          }}
          .spider-map {{ display:block; width:100%; height:auto; min-width:900px; }}
          .spider-edge {{
            stroke:var(--muted); stroke-opacity:.55; stroke-width:1.5;
            fill:none;
          }}
          .spider-node rect {{
            fill:var(--card, #20242d); stroke-width:2;
          }}
          .spider-node text {{
            fill:var(--text); font-size:13px; font-weight:600;
            pointer-events:none;
          }}
          .spider-node:hover rect,
          .spider-node:focus rect {{
            stroke-width:4; filter:brightness(1.12); outline:none;
          }}
          @media (max-width:600px) {{
            .spider-map-card {{ padding:10px !important; }}
            .spider-map {{ min-width:850px; }}
          }}
        </style>
        <details class="architecture-details">
          <summary>View the full internal connection list ({len(seen_edges)})</summary>
          <ul class="architecture-connection-list">
            {''.join(
                '<li>' + escape(full_label(node_by_id[str(edge.source)]))
                + ' <span class="architecture-relation-type">'
                + escape(str((getattr(edge, "metadata", {}) or {}).get("kind")
                    or (getattr(edge, "metadata", {}) or {}).get("type")
                    or "connects to"))
                + '</span> '
                + escape(full_label(node_by_id[str(edge.target)]))
                + '</li>'
                for edge in graph.edges
                if str(edge.source) in node_by_id
                and str(edge.target) in node_by_id
            )}
          </ul>
        </details>
      </div>
    </section>
    """


def _render_three_layer_architecture(project: Project) -> str:
    """Render a connected, three-layer overview of the scanned project."""
    from pathlib import PurePosixPath

    def esc(value: object) -> str:
        return html.escape(str(value or ""), quote=True)

    files = list(getattr(project, "files", []) or [])
    modules = list(getattr(project, "modules", []) or [])
    classes = list(getattr(project, "classes", []) or [])
    functions = list(getattr(project, "functions", []) or [])
    methods = list(getattr(project, "methods", []) or [])
    data_items = list(getattr(project, "data", []) or [])

    def get(item: object, *names: str) -> str:
        for name in names:
            value = (
                item.get(name) if isinstance(item, dict) else getattr(item, name, None)
            )
            if value is not None and value != "":
                return str(value)
        return ""

    def path_of(item: object) -> str:
        return get(item, "path", "file_path", "source_file", "filename").replace(
            "\\", "/"
        )

    def source_preview(item: object, max_lines: int = 12) -> str:
        """Return a small, bounded source excerpt for a scanned project entity."""
        raw_path = path_of(item)
        if not raw_path:
            return ""

        root = Path(project.root).resolve()
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate

        try:
            candidate = candidate.resolve()
            # Homepage previews must only read files from the scanned project.
            candidate.relative_to(root)
            if not candidate.is_file():
                return ""
            lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, ValueError):
            return ""

        if not lines:
            return ""

        start_value = (
            get(item, "line_start", "start_line", "line", "lineno")
            or "1"
        )
        end_value = get(item, "line_end", "end_line")
        try:
            start = max(1, int(start_value))
        except (TypeError, ValueError):
            start = 1
        try:
            end = int(end_value) if end_value else start + max_lines - 1
        except (TypeError, ValueError):
            end = start + max_lines - 1

        end = max(start, min(end, start + max_lines - 1, len(lines)))
        start = min(start, len(lines))
        excerpt = "\n".join(lines[start - 1:end]).rstrip()
        if not excerpt:
            return ""

        return (
            '<div class="architecture-source-preview">'
            '<div class="architecture-source-label">Source preview'
            f'<span>lines {start}–{end}</span></div>'
            f'<pre><code>{esc(excerpt)}</code></pre>'
            '</div>'
        )

    def item_card(item: object, kind: str, duplicate_count: int = 1) -> str:
        name = (
            get(item, "qualified_name", "name", "label", "module")
            or path_of(item)
            or "(unnamed item)"
        )
        path = path_of(item)
        description = (
            get(item, "description", "docstring", "summary", "explanation")
            or "No description was recorded by the scanner."
        )
        preview = source_preview(item)

        # Give every architecture entry a useful expanded view. Keep this
        # evidence-based: only render fields actually present on the scan model.
        detail_rows: list[str] = []
        line_start = get(item, "line_start", "start_line", "line", "lineno")
        line_end = get(item, "line_end", "end_line")
        if path:
            location = path
            if line_start:
                location += f":{line_start}"
                if line_end and line_end != line_start:
                    location += f"–{line_end}"
            detail_rows.append(
                f'<div><dt>Source</dt><dd class="code">{esc(location)}</dd></div>'
            )

        parameters = get(item, "parameters", "params", "arguments")
        return_type = get(item, "return_type", "returns")
        class_name = get(item, "class_name", "parent_class", "owner")
        methods = get(item, "methods")
        language = get(item, "language")

        if class_name:
            detail_rows.append(
                f'<div><dt>Class</dt><dd class="code">{esc(class_name)}</dd></div>'
            )
        if parameters:
            detail_rows.append(
                f'<div><dt>Parameters</dt><dd class="code">{esc(parameters)}</dd></div>'
            )
        if return_type:
            detail_rows.append(
                f'<div><dt>Returns</dt><dd class="code">{esc(return_type)}</dd></div>'
            )
        if methods:
            detail_rows.append(
                f'<div><dt>Methods</dt><dd class="code">{esc(methods)}</dd></div>'
            )
        if language:
            detail_rows.append(
                f'<div><dt>Language</dt><dd>{esc(language)}</dd></div>'
            )

        details = (
            '<dl class="architecture-entity-facts">' + "".join(detail_rows) + "</dl>"
            if detail_rows
            else ""
        )
        extra = (
            f'<p class="architecture-match-note">{duplicate_count} matching scan records were grouped into this card.</p>'
            if duplicate_count > 1
            else ""
        )
        return (
            '<details class="card architecture-item">'
            '<summary class="architecture-item-summary">'
            f'<div class="architecture-item-kind-row"><span class="architecture-item-kind">{esc(kind)}</span></div>'
            '<div class="architecture-item-main-row">'
            f'<strong class="architecture-item-name">{esc(name)}</strong>'
            '<span class="architecture-expand">Expand →</span>'
            "</div>"
            "</summary>"
            '<div class="architecture-item-details">'
            '<div class="architecture-expanded-heading">Expanded view</div>'
            f'<p class="architecture-entity-description">{esc(description)}</p>'
            + details
            + preview
            + extra
            + "</div></details>"
        )

    def item_name(item: object, fallback_to_path: bool = True) -> str:
        return (
            get(item, "qualified_name", "name", "label", "module")
            or (path_of(item) if fallback_to_path else "")
            or "(unnamed item)"
        ).strip()

    def dedupe_items(
        items: list, *, display_name_only: bool = False
    ) -> list[tuple[object, int]]:
        grouped: dict[str, tuple[object, int]] = {}
        order: list[str] = []
        for item in items:
            name = item_name(item)
            path = path_of(item).lower().strip("/")
            key = (
                name.lower().strip()
                if display_name_only
                else (name.lower().strip(), path)
            )
            if key in grouped:
                representative, count = grouped[key]
                grouped[key] = (representative, count + 1)
            else:
                grouped[key] = (item, 1)
                order.append(key)
        return [grouped[key] for key in order]

    def cards(items: list, kind: str, limit: int) -> str:
        if not items:
            return (
                '<p class="architecture-empty">No '
                + esc(kind.lower())
                + " records were identified in this scan.</p>"
            )
        unique = dedupe_items(items, display_name_only=True)
        shown = "".join(item_card(item, kind, count) for item, count in unique[:limit])
        if len(unique) > limit:
            shown += (
                '<p class="architecture-more">Showing '
                + str(limit)
                + " of "
                + str(len(unique))
                + " unique items here. See the Structure and Relationship Map pages "
                "for the full inventory.</p>"
            )
        return '<div class="architecture-card-grid">' + shown + "</div>"

    entry_names = {
        "main.py",
        "__main__.py",
        "app.py",
        "server.py",
        "manage.py",
        "cli.py",
        "main.rs",
        "main.go",
        "index.js",
        "index.ts",
        "server.js",
        "server.ts",
        "program.cs",
        "startup.cs",
        "application.java",
    }
    # Candidate discovery is intentionally conservative. Duplicate scan
    # records must not turn into a wall of identical "main" cards.
    entry_files = []
    seen_entry_paths = set()
    for item in files:
        p = path_of(item)
        normalized_path = p.lower().strip("/")
        name = PurePosixPath(p).name.lower()
        is_candidate = name in entry_names or any(
            f"/{part}/" in f"/{normalized_path}/"
            for part in ("routes", "routers", "controllers")
        )
        if not is_candidate:
            continue
        key = normalized_path or f"unnamed-file-{len(entry_files)}"
        if key in seen_entry_paths:
            continue
        seen_entry_paths.add(key)
        entry_files.append(item)

    entry_function_names = {
        "main",
        "run",
        "cli",
        "app",
        "create_app",
        "createapp",
        "serve",
        "start_server",
        "main_cli",
    }
    entry_functions = [
        item
        for item in functions
        if get(item, "name", "qualified_name").split(".")[-1].lower()
        in entry_function_names
    ]

    # Entry candidates are grouped by their visible entry name. This prevents
    # dozens of identical "main" cards when the project contains multiple
    # modules exposing a conventional entry function. The first source record
    # remains the representative and the card records how many matches were
    # grouped into it.
    entry_candidates = []
    entry_candidates.extend(entry_files)
    entry_candidates.extend(entry_functions)

    # For entry points, group by the name the human actually sees on the
    # card: file candidates use their basename (main.py/app.py/etc.), while
    # function candidates use the function name (main/run/etc.). This is
    # intentionally broader than path-based deduplication so repeated
    # conventional entry names do not flood the homepage.
    grouped_entries: dict[str, tuple[object, int]] = {}
    entry_order: list[str] = []
    for item in entry_candidates:
        path = path_of(item)
        if item in entry_files:
            visible = PurePosixPath(path).name if path else item_name(item)
        else:
            visible = get(item, "name", "qualified_name").split(".")[-1] or item_name(
                item
            )
        key = visible.lower().strip()
        if key in grouped_entries:
            representative, count = grouped_entries[key]
            grouped_entries[key] = (representative, count + 1)
        else:
            grouped_entries[key] = (item, 1)
            entry_order.append(key)
    unique_entry_candidates = [grouped_entries[key] for key in entry_order]

    layer1_items = [
        item_card(item, "Entry-point candidate", count)
        for item, count in unique_entry_candidates
    ]

    layer1 = (
        '<div class="architecture-card-grid">' + "".join(layer1_items[:24]) + "</div>"
        if layer1_items
        else '<p class="architecture-empty">No conventional entry points were identified. '
        "This does not prove that the project has none.</p>"
    )
    if len(unique_entry_candidates) > 24:
        layer1 += (
            '<p class="architecture-more">Showing 24 of '
            + str(len(unique_entry_candidates))
            + " unique entry candidates. Check the full project structure for others.</p>"
        )

    layer2 = (
        cards(modules, "Module", 16)
        + cards(classes, "Class", 16)
        + cards(functions, "Function", 16)
        + cards(methods, "Method", 16)
    )

    support_files = [
        item
        for item in files
        if any(
            word in path_of(item).lower()
            for word in (
                "config",
                "setting",
                "database",
                "repository",
                "migration",
                "schema",
                "storage",
                "persist",
                "model",
            )
        )
    ]
    layer3 = cards(data_items, "Data record", 16)
    if support_files:
        layer3 += '<h3 class="architecture-subheading">Supporting files</h3>' + cards(
            support_files, "Supporting file candidate", 16
        )

    return (
        '<section id="project-architecture-layers" class="architecture-flow">'
        "<style>"
        "#project-architecture-layers{margin:2rem 0}"
        ".architecture-flow-intro{max-width:70ch;color:var(--muted,#aaa)}"
        ".architecture-layer{position:relative;padding:1.25rem;margin:0 auto;"
        "width:100%;box-sizing:border-box;border:1px solid var(--border,#383838);"
        "border-radius:1rem;background:var(--panel,#101010)}"
        ".architecture-layer-1{border-top:3px solid #b985d6}"
        ".architecture-layer-2{border-top:3px solid #729ee8}"
        ".architecture-layer-3{border-top:3px solid #72b994}"
        ".architecture-layer-heading{display:flex;gap:.8rem;align-items:center;"
        "flex-wrap:wrap;margin-bottom:1rem}"
        ".architecture-layer-number{display:inline-grid;place-items:center;"
        "width:2rem;height:2rem;border-radius:50%;background:var(--panel-alt,#202020);"
        "font-weight:700}"
        ".architecture-layer-heading h3{margin:0}"
        ".architecture-layer-description{color:var(--muted,#aaa);margin:.4rem 0 1rem}"
        ".architecture-connector{height:3.25rem;display:flex;align-items:center;"
        "justify-content:center;position:relative}"
        '.architecture-connector:before{content:"";height:100%;width:2px;'
        "background:linear-gradient(to bottom,#b985d6,#729ee8)}"
        ".architecture-connector:nth-of-type(4):before{background:linear-gradient(to bottom,#729ee8,#72b994)}"
        ".architecture-connector span{position:absolute;bottom:0;transform:translateY(50%);"
        "background:var(--bg,#080808);border:1px solid var(--border,#383838);"
        "border-radius:999px;padding:.2rem .65rem;font-size:.75rem;color:var(--muted,#aaa)}"
        ".architecture-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem}"
        ".architecture-item{margin:0!important;padding:0!important;min-width:0;min-height:112px;"
        "overflow:hidden;overflow-wrap:anywhere;border:1px solid var(--border,#383838);"
        "background:linear-gradient(180deg,rgba(255,255,255,.018),rgba(255,255,255,.006));}"
        ".architecture-item[open]{grid-column:1/-1;width:100%;min-width:0}"
        ".architecture-item-summary{display:block;min-height:112px;padding:.7rem .75rem;"
        "cursor:pointer;list-style:none;box-sizing:border-box}"
        ".architecture-item-summary::-webkit-details-marker{display:none}"
        ".architecture-item-kind-row{height:22px;display:flex;align-items:flex-start}"
        ".architecture-item-kind{display:inline-flex;align-items:center;max-width:100%;"
        "font-size:.62rem;text-transform:uppercase;letter-spacing:.055em;line-height:1.2;"
        "color:#b9b5b8;border:1px solid #343434;background:#101010;"
        "border-radius:999px;padding:.22rem .45rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".architecture-item-main-row{display:grid;grid-template-columns:minmax(0,1fr) auto;"
        "gap:.55rem;align-items:end;min-height:58px}"
        ".architecture-item-name{display:block;min-width:0;color:var(--text,#f5f5f5);"
        "font-size:.78rem;line-height:1.35;font-weight:700;overflow-wrap:anywhere;word-break:normal}"
        ".architecture-expand{align-self:end;white-space:nowrap;color:#9b979a;font-size:.63rem}"
        ".architecture-item[open] .architecture-expand{font-size:0}"
        '.architecture-item[open] .architecture-expand:after{content:"Hide details ↑";font-size:.63rem}'
        ".architecture-item-details{width:100%;min-width:0;padding:.7rem .75rem .8rem;border-top:1px solid #222;"
        "color:var(--muted,#aaa);font-size:.78rem;line-height:1.5}"
        ".architecture-path{font-size:.72rem;overflow-wrap:anywhere}"
        ".architecture-expanded-heading{width:100%;margin:0 0 .35rem;font-weight:700;color:var(--text,#f5f5f5)}"
        ".architecture-entity-description{width:100%;max-width:none;margin:.25rem 0 .75rem}"
        ".architecture-entity-facts{display:grid!important;grid-template-columns:1fr!important;width:100%!important;max-width:none!important;min-width:0!important;margin:.5rem 0!important;padding:0!important;gap:.45rem}"
        ".architecture-entity-facts>div{display:grid!important;grid-template-columns:minmax(90px,140px) minmax(0,1fr)!important;width:100%!important;max-width:none!important;min-width:0!important;align-items:start;gap:.75rem;padding:.45rem .55rem;border:1px solid #242424;border-radius:8px;background:#0b0b0b;box-sizing:border-box}"
        ".architecture-entity-facts dt{margin:0;color:#8f898d;font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em}"
        ".architecture-entity-facts dd{margin:0!important;min-width:0!important;width:auto!important;max-width:none!important;overflow-wrap:normal!important;word-break:normal!important;white-space:normal}"
        ".architecture-entity-facts dd.code{white-space:pre-wrap!important;overflow-wrap:anywhere!important;word-break:normal!important}"
        ".architecture-source-preview{display:block!important;width:100%!important;max-width:none!important;min-width:0!important;box-sizing:border-box;margin-top:.65rem;border:1px solid #292929;border-radius:9px;overflow:hidden;background:#090909}"
        ".architecture-source-label{display:flex;justify-content:space-between;gap:.75rem;padding:.38rem .55rem;border-bottom:1px solid #242424;color:#d4d0d2;font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.045em}"
        ".architecture-source-label span{color:#777;font-weight:500;text-transform:none;letter-spacing:0}"
        ".architecture-source-preview pre{display:block!important;width:100%!important;max-width:100%!important;min-width:0!important;box-sizing:border-box;margin:0;padding:.6rem;max-height:15rem;overflow:auto;background:#090909}"
        ".architecture-source-preview code{font-family:Consolas,\"SFMono-Regular\",monospace;font-size:.7rem;line-height:1.5;color:#ddd;white-space:pre;tab-size:4}"
        ".architecture-match-note{margin:.45rem 0 0;color:#7f7a7e;font-size:.68rem}"
        ".architecture-empty,.architecture-more{color:var(--muted,#aaa);font-size:.82rem}"
        ".architecture-subheading{margin:1.25rem 0 .75rem}"
        "@media(max-width:980px){.architecture-card-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}"
        "@media(max-width:720px){.architecture-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}"
        "@media(max-width:520px){.architecture-layer{padding:.85rem}.architecture-card-grid{grid-template-columns:1fr}}"
        """

/* Human-centered architecture cards: closed by default, explicit controls,
   and a clear click target without removing any underlying information. */
.architecture-controls{
  display:flex;align-items:center;gap:7px;flex-wrap:wrap;
  margin:0 0 10px;padding:7px;
  border:1px solid rgba(255,255,255,.055);border-radius:9px;
  background:rgba(255,255,255,.012)
}
.architecture-control{
  appearance:none;border:1px solid #303030;border-radius:999px;
  padding:5px 9px;background:#111;color:#c8c4c7;
  font:600 9px/1.2 "SFMono-Regular",Consolas,monospace;
  cursor:pointer;transition:background .15s,border-color .15s,color .15s
}
.architecture-control:hover,.architecture-control:focus-visible{
  color:#fff;border-color:rgba(255,107,157,.38);background:rgba(255,107,157,.08)
}
.architecture-control-hint{color:#777277;font-size:9px;margin-left:2px}
.architecture-card{cursor:pointer}
.architecture-card > summary{
  position:relative;display:grid!important;grid-template-columns:minmax(0,1fr) auto;
  grid-template-rows:auto auto;column-gap:8px;align-items:center;
  list-style:none;cursor:pointer;user-select:none
}
.architecture-card > summary::-webkit-details-marker{display:none}
.architecture-card > summary:after{display:none!important}
.architecture-card-name{grid-column:1;grid-row:1;color:#f5f3f4}
.architecture-card-meta{grid-column:1;grid-row:2;color:#8f8b8e}
.architecture-card-action{
  grid-column:2;grid-row:1 / span 2;align-self:center;white-space:nowrap;
  color:#8f8b8e;font:600 8px/1.2 "SFMono-Regular",Consolas,monospace;
  transition:color .15s
}
.architecture-card:hover .architecture-card-action{color:#ff86ad}
.architecture-card[open] .architecture-card-action{font-size:0}
.architecture-card[open] .architecture-card-action:after{content:"Hide details ↑";font-size:8px}
.architecture-card[open] > summary{background:rgba(255,107,157,.025)}
.architecture-card-details{animation:architecture-reveal .13s ease-out}
@keyframes architecture-reveal{from{opacity:0;transform:translateY(-2px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:560px){
 .architecture-controls{align-items:stretch}
 .architecture-control-hint{flex-basis:100%;margin-top:1px}
 .architecture-card > summary{grid-template-columns:minmax(0,1fr)}
 .architecture-card-action{grid-column:1;grid-row:3;margin-top:4px}
}


/* Simple collapsible architecture cards — applies to all 3 layers. */
.architecture-item { cursor: default; }
.architecture-item > summary { cursor: pointer; user-select: none; }
.architecture-item > summary:hover { background: rgba(255,255,255,.018); }
.architecture-item > .architecture-item-details { display: none; }
.architecture-item[open] > .architecture-item-details { display: block; }
.architecture-item[open] { border-color: rgba(255,107,157,.28); }
.architecture-item[open] > summary .architecture-expand { color: #ff86ad; }




/* Barkly Standard index — same palette, lower cognitive load. */
.index-human-flow{display:grid;gap:18px;margin-top:26px}
.index-section-card{border:1px solid var(--line);border-radius:16px;background:var(--panel);overflow:hidden}
.index-section-card > summary{list-style:none;cursor:pointer;padding:18px 20px;display:flex;align-items:center;justify-content:space-between;gap:18px;user-select:none}
.index-section-card > summary::-webkit-details-marker{display:none}
.index-section-card > summary:hover{background:rgba(255,107,157,.025)}
.index-section-card[open]{border-color:rgba(255,107,157,.24)}
.index-section-card[open] > summary{border-bottom:1px solid var(--line)}
.index-section-heading{min-width:0}
.index-section-heading h2{margin:0 0 6px;font-size:1.18rem}
.index-section-heading p{margin:0;color:var(--muted);font-size:.84rem;line-height:1.55;max-width:760px}
.index-section-action{flex:0 0 auto;color:var(--muted);font:600 9px/1.2 "SFMono-Regular",Consolas,monospace;white-space:nowrap}
.index-section-card:hover .index-section-action{color:var(--accent)}
.index-section-card[open] .index-section-action{font-size:0}
.index-section-card[open] .index-section-action:after{content:"Hide ↑";font-size:9px}
.index-section-body{padding:18px 20px 20px}
.index-glance{margin-top:26px}
.index-glance-head{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:12px}
.index-glance-head h2{margin:0;font-size:1.25rem}
.index-glance-head p{margin:4px 0 0;color:var(--muted);font-size:.82rem;max-width:720px;line-height:1.55}
.index-glance-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px}
.index-glance-card{min-width:0;border:1px solid var(--line);border-radius:14px;background:var(--panel);padding:16px 17px}
.index-glance-card-purpose{grid-row:span 2}
.index-glance-card h3{margin:0 0 8px;color:var(--muted);font:700 9px/1.2 "SFMono-Regular",Consolas,monospace;letter-spacing:.08em;text-transform:uppercase}
.index-glance-card p{margin:0;color:var(--text-soft);line-height:1.6;overflow-wrap:anywhere}
.index-glance-card-purpose p{font-size:.98rem;color:var(--text)}
.index-evidence{margin-top:12px;border-top:1px solid var(--line);padding-top:14px}
.index-evidence h3{margin:0 0 5px;font-size:.9rem}
.index-evidence > p{margin:0 0 12px;color:var(--muted);font-size:.8rem;line-height:1.55}

.index-evidence .evidence-grid{align-items:start}
.index-evidence .evidence-tile{min-width:0}
.index-evidence .evidence-total{margin:0;color:var(--text-soft)}
.index-evidence .evidence-total strong{font-size:1rem;color:var(--text)}
.index-evidence .evidence-data{margin-top:10px;border-top:1px solid var(--line);padding-top:9px}
.index-evidence .evidence-data > summary{cursor:pointer;list-style:none;color:var(--accent);font:600 9px/1.3 "SFMono-Regular",Consolas,monospace}
.index-evidence .evidence-data > summary::-webkit-details-marker{display:none}
.index-evidence .evidence-data > summary::after{content:" ↓"}
.index-evidence .evidence-data[open] > summary::after{content:" ↑"}
.index-evidence .evidence-data ul{list-style:none;margin:9px 0 0;padding:0;display:grid;gap:6px}
.index-evidence .evidence-data li{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding-top:6px;border-top:1px solid rgba(255,255,255,.045);font-size:.72rem}
.index-evidence .evidence-kind{min-width:0;color:var(--muted);overflow-wrap:anywhere}
.index-evidence .evidence-data strong{flex:0 0 auto;color:var(--text)}
.index-evidence .evidence-empty{margin:8px 0 0;color:var(--muted);font-size:.72rem}

.index-deep-label{margin:30px 0 0;color:var(--accent);font:800 8px/1 "SFMono-Regular",Consolas,monospace;letter-spacing:.16em;text-transform:uppercase}
.index-deep-title{margin:7px 0 4px;font-size:1.35rem}
.index-deep-copy{margin:0 0 14px;color:var(--muted);font-size:.84rem;line-height:1.55;max-width:760px}
@media(max-width:820px){.index-glance-grid{grid-template-columns:1fr 1fr}.index-glance-card-purpose{grid-column:1/-1;grid-row:auto}}
@media(max-width:560px){.index-glance-grid{grid-template-columns:1fr}.index-glance-card-purpose{grid-column:auto}.index-section-card > summary{align-items:flex-start;flex-direction:column}.index-glance-head{align-items:flex-start;flex-direction:column}}

/* Collapsible Documentation references card */
.documentation-card {
  margin-top: 32px;
  overflow: hidden;
}
.documentation-card > summary {
  display: block;
  list-style: none;
  cursor: pointer;
  user-select: none;
  padding: 18px 20px;
}
.documentation-card > summary::-webkit-details-marker { display: none; }
.documentation-card > summary:hover {
  background: rgba(255,107,157,.025);
}
.documentation-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.documentation-card-title {
  min-width: 0;
}
.documentation-card-title h2 {
  margin: 0 0 8px;
  font-size: 1.5rem;
}
.documentation-card-title .section-subtitle {
  margin: 0;
}
.documentation-card-action {
  flex: 0 0 auto;
  color: var(--muted);
  font: 600 9px/1.2 "SFMono-Regular",Consolas,monospace;
  white-space: nowrap;
}
.documentation-card:hover .documentation-card-action {
  color: var(--accent);
}
.documentation-card[open] .documentation-card-action {
  font-size: 0;
}
.documentation-card[open] .documentation-card-action::after {
  content: "Hide documentation ↑";
  font-size: 9px;
}
.documentation-card-body {
  padding: 0 20px 20px;
  border-top: 1px solid var(--line);
}
.documentation-card[open] {
  border-color: rgba(255,107,157,.28);
}
@media (max-width: 560px) {
  .documentation-card-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}


/* Searchable, low-cognitive-load Barkly data cards */
.index-card-tools{display:flex;align-items:center;gap:10px;margin:0 0 14px}
.index-card-search{width:100%;min-height:40px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;background:rgba(255,255,255,.025);color:var(--text);font:500 12px/1.35 "SFMono-Regular",Consolas,monospace;outline:none}
.index-card-search::placeholder{color:var(--muted)}
.index-card-search:focus{border-color:rgba(255,107,157,.55);box-shadow:0 0 0 3px rgba(255,107,157,.08)}
.index-card-count{flex:0 0 auto;color:var(--muted);font:600 9px/1 "SFMono-Regular",Consolas,monospace;white-space:nowrap}
.index-section-body .entity-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
.index-section-body .entity-item{min-width:0;padding:13px 14px;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,.018)}
.index-section-body .entity-item:hover{border-color:rgba(255,107,157,.28);background:rgba(255,107,157,.025)}
.index-section-body .entity-item h3{margin:0 0 8px;font-size:13px;line-height:1.35;overflow-wrap:anywhere}
.index-section-body .entity-item .meta{display:block;margin-top:4px;color:var(--muted);font-size:10px;line-height:1.45;overflow-wrap:anywhere}
.index-no-results{display:none;padding:18px;color:var(--muted);text-align:center;font-size:12px}
@media(max-width:620px){.index-section-body .entity-list{grid-template-columns:1fr}.index-card-tools{align-items:stretch;flex-direction:column}}


/* Calm Barkly data browser: one readable row per entity */
.index-section-body .entity-list{
  display:flex;
  flex-direction:column;
  gap:6px;
}
.index-section-body .entity-item{
  display:grid;
  grid-template-columns:minmax(180px,1.15fr) minmax(100px,.55fr) minmax(110px,.55fr) minmax(260px,2fr);
  align-items:center;
  gap:10px 18px;
  padding:10px 12px;
  min-height:52px;
  border:1px solid rgba(255,255,255,.065);
  border-radius:8px;
  background:rgba(255,255,255,.012);
}
.index-section-body .entity-item:hover{
  border-color:rgba(255,107,157,.22);
  background:rgba(255,107,157,.018);
}
.index-section-body .entity-item h3{
  margin:0;
  font-size:12px;
  line-height:1.3;
}
.index-section-body .entity-item .meta{
  margin:0;
  font-size:9px;
  line-height:1.35;
}
.index-section-body .entity-item .meta:last-child{
  color:rgba(255,255,255,.52);
}
.index-section-body .entity-item:nth-child(n+13){
  display:none;
}
.index-section-body.show-all .entity-item:nth-child(n+13){
  display:grid;
}
.index-card-tools{
  position:sticky;
  top:8px;
  z-index:2;
  padding:8px;
  margin:0 0 10px;
  border:1px solid rgba(255,255,255,.06);
  border-radius:10px;
  background:rgba(15,15,16,.94);
  backdrop-filter:blur(10px);
}
.index-card-search{
  min-height:36px;
  border:0;
  background:transparent;
}
.index-card-more{
  display:block;
  width:100%;
  margin-top:10px;
  padding:9px 12px;
  border:1px solid var(--line);
  border-radius:8px;
  background:transparent;
  color:var(--muted);
  cursor:pointer;
  font:600 9px/1.2 "SFMono-Regular",Consolas,monospace;
}
.index-card-more:hover{
  color:var(--text);
  border-color:rgba(255,107,157,.3);
}
@media(max-width:900px){
  .index-section-body .entity-item{
    grid-template-columns:minmax(150px,1fr) minmax(90px,.55fr) minmax(220px,1.5fr);
  }
  .index-section-body .entity-item .meta:nth-of-type(2){display:none}
}
@media(max-width:620px){
  .index-section-body .entity-item{
    display:block;
    padding:11px 12px;
  }
  .index-section-body.show-all .entity-item:nth-child(n+13){display:block}
  .index-section-body .entity-item h3{margin-bottom:6px}
  .index-section-body .entity-item .meta{margin-top:3px}
}

/* Human-centered README presentation */
.readme-panel {
  border: 1px solid rgba(255,255,255,.075);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.012));
  overflow: hidden;
}
.readme-intro {
  padding: 20px 22px 16px;
  border-bottom: 1px solid rgba(255,255,255,.07);
  background: linear-gradient(135deg, rgba(255,107,157,.06), transparent 55%);
}
.readme-kicker {
  color: var(--accent);
  font: 800 8px/1 "SFMono-Regular", Consolas, monospace;
  letter-spacing: .16em;
}
.readme-intro h2 { margin: 7px 0 6px; font-size: 20px; letter-spacing: -.03em; }
.readme-lead { max-width: 850px; margin: 0; color: var(--text-soft); line-height: 1.65; }
.readme-content { padding: 20px 22px 24px; max-width: 980px; }
.readme-content h1 { font-size: 22px; }
.readme-content h2 { margin: 25px 0 9px; padding-top: 6px; font-size: 16px; border-top: 1px solid rgba(255,255,255,.055); }
.readme-content h3 { margin: 18px 0 7px; font-size: 13px; }
.readme-content p { max-width: 820px; color: #c9c5c8; }
.readme-content ul, .readme-content ol { max-width: 820px; padding-left: 22px; }
.readme-content li { margin: 5px 0; color: #c9c5c8; }
.readme-content pre { margin: 12px 0 16px; }
.readme-content blockquote { margin: 12px 0; padding: 8px 14px; border-left: 2px solid var(--accent); color: var(--muted); background: rgba(255,107,157,.035); }
.readme-content hr { border: 0; border-top: 1px solid rgba(255,255,255,.07); margin: 20px 0; }
.readme-content a { color: var(--accent-bright); }

/* Barkly Standard secondary-page header — independent of the index hero grid. */
.subpage-header {
  display: block;
  width: 100%;
  margin: 24px 0 0;
  padding: 0 0 22px;
  text-align: left;
}
.subpage-header .kicker {
  display: block;
  width: 100%;
  margin: 0 0 8px;
  text-align: left;
}
.subpage-header h1 {
  display: block;
  width: 100%;
  margin: 0 0 6px;
  padding: 0;
  text-align: left;
  font-size: clamp(1.8rem, 3vw, 2.35rem);
  line-height: 1.15;
  letter-spacing: -0.035em;
}
.subpage-header p {
  display: block;
  width: 100%;
  max-width: 72ch;
  margin: 0;
  padding: 0;
  text-align: left;
  color: var(--muted);
}
.subpage-header + .section,
.subpage-header + .card {
  margin-top: 12px;
}


/* Entity disclosure layout fix.
   The expandable <details> owns the full row. Only its <summary> is a grid. */
.index-section-body .entity-item.entity-expandable {
  display: block;
  width: 100%;
  min-width: 0;
  padding: 0;
  min-height: 0;
}

.index-section-body .entity-item.entity-expandable > .entity-row-summary {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns:
    minmax(180px, 1.15fr)
    minmax(100px, .55fr)
    minmax(110px, .55fr)
    minmax(260px, 2fr)
    auto;
  align-items: center;
  gap: 10px 18px;
  padding: 10px 12px;
}

.index-section-body .entity-item.entity-expandable > .entity-expanded-view {
  display: block;
  width: 100%;
  min-width: 0;
  grid-column: 1 / -1;
  padding: 16px 18px 18px;
}

.index-section-body .entity-item.entity-expandable .entity-source-preview,
.index-section-body .entity-item.entity-expandable .entity-source-preview pre {
  display: block;
  width: 100%;
  min-width: 0;
  max-width: 100%;
}

.index-section-body.show-all .entity-item.entity-expandable:nth-child(n+13) {
  display: block;
}

@media (max-width: 900px) {
  .index-section-body .entity-item.entity-expandable > .entity-row-summary {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .index-section-body .entity-item.entity-expandable > .entity-row-summary .meta {
    grid-column: 1 / -1;
  }
}

@media (max-width: 620px) {
  .index-section-body .entity-item.entity-expandable {
    padding: 0;
  }
  .index-section-body .entity-item.entity-expandable > .entity-row-summary {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    padding: 11px 12px;
  }
  .index-section-body .entity-item.entity-expandable > .entity-row-summary .meta,
  .index-section-body .entity-item.entity-expandable > .entity-row-summary .entity-row-action {
    grid-column: 1;
  }
}

</style>"""
        "<h2>How the project fits together</h2>"
        '<p class="architecture-flow-intro">Follow the three layers from possible entry points, '
        "through the main code, to data and supporting systems. Expand any card for its recorded "
        "description and source path. Entry points and supporting roles are candidates inferred "
        "from names and paths, not guaranteed execution flow.</p>"
        '<details class="architecture-layer architecture-layer-1">'
        '<summary class="architecture-layer-summary"><span class="architecture-layer-heading"><span class="architecture-layer-number">1</span>'
        '<h3>Main entrance</h3><span class="architecture-layer-toggle">View section →</span></span>'
        '<span class="architecture-layer-description">Where execution or requests may enter the project.</span></summary>'
        + layer1
        + "</details>"
        '<div class="architecture-connector" aria-hidden="true"><span>Entry into the core</span></div>'
        '<details class="architecture-layer architecture-layer-2">'
        '<summary class="architecture-layer-summary"><span class="architecture-layer-heading"><span class="architecture-layer-number">2</span>'
        '<h3>Main project files and code</h3><span class="architecture-layer-toggle">View section →</span></span>'
        '<span class="architecture-layer-description">Modules, classes, functions, and methods identified by the scanner.</span></summary>'
        + layer2
        + "</details>"
        '<div class="architecture-connector" aria-hidden="true"><span>Core code and data</span></div>'
        '<details class="architecture-layer architecture-layer-3">'
        '<summary class="architecture-layer-summary"><span class="architecture-layer-heading"><span class="architecture-layer-number">3</span>'
        '<h3>Data points and supporting systems</h3><span class="architecture-layer-toggle">View section →</span></span>'
        '<span class="architecture-layer-description">Data records and candidate configuration, schema, storage, and persistence files.</span></summary>'
        + layer3
        + "</details>"
        "</section>"
    )







def render_project_website(project: Project, output_dir: str | Path) -> list[Path]:
    # Page renderers live in separate modules so each page can evolve independently.
    # Imports are intentionally local: page modules reuse shared helpers from this
    # module without creating an import-time circular dependency.
    from rendering.index_page import render_index
    from rendering.entities_page import render_entities_page
    from rendering.relationships_page import render_relationships_page
    from rendering.relation_map_page import render_relation_map_page

    project_obj = project
    build_relation_graph(project_obj)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    assets_dir = output_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    (assets_dir / "site.css").write_text(CSS, encoding="utf-8")
    (assets_dir / "relation-map.js").write_text(RELATION_MAP_JS, encoding="utf-8")
    _prepare_readme_title_image(project_obj, output_path)

    index_path = output_path / "index.html"
    entities_path = output_path / "entities.html"
    relationships_path = output_path / "relationships.html"
    relation_map_path = output_path / "relation-map.html"

    index_path.write_text(render_index(project_obj), encoding="utf-8")
    entities_path.write_text(render_entities_page(project_obj), encoding="utf-8")
    relationships_path.write_text(render_relationships_page(project_obj), encoding="utf-8")
    relation_map_path.write_text(render_relation_map_page(project_obj), encoding="utf-8")

    return [
        index_path,
        entities_path,
        relationships_path,
        relation_map_path,
        assets_dir / "site.css",
        assets_dir / "relation-map.js",
    ]

def generate_html_website(project: Project, output_dir: str | Path) -> list[Path]:
    return render_project_website(project, output_dir)


__all__ = [
    "CSS",
    "render_project_website",
    "generate_html_website",
]