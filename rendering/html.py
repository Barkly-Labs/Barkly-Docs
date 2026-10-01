from __future__ import annotations

import html
import json
import re
from pathlib import Path

from analysis.graph import build_relation_graph
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
    radial-gradient(circle at top, rgba(141,211,255,0.08), transparent 60%);
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
  background: rgba(255,255,255,0.02);
}
.graph-tools input[type="search"] {
  flex: 1 1 220px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text);
  padding: 10px 14px;
}
.graph-tools button {
  background: rgba(141, 211, 255, 0.12);
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
  background: rgba(255,255,255,0.015);
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
  background: rgba(255,255,255,0.01);
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

RELATION_MAP_JS = """
document.addEventListener("DOMContentLoaded", () => {
  const dataElement = document.getElementById("relation-map-data");
  if (!dataElement) {
    return;
  }

  const graphData = JSON.parse(dataElement.textContent || "{}") || { nodes: [], edges: [] };
  const svg = document.getElementById("relation-map-canvas");
  const details = document.getElementById("relation-map-details");
  const searchInput = document.getElementById("relation-map-search");
  const nodeTypeFilters = Array.from(document.querySelectorAll("input[data-filter-node]"));
  const edgeTypeFilters = Array.from(document.querySelectorAll("input[data-filter-edge]"));
  const buttons = Array.from(document.querySelectorAll("[data-graph-action]"));
  const state = {
    selectedNodeId: null,
    selectedEdgeId: null,
    search: "",
    nodeTypes: new Set(nodeTypeFilters.filter((input) => input.checked).map((input) => input.value)),
    edgeTypes: new Set(edgeTypeFilters.filter((input) => input.checked).map((input) => input.value)),
    scale: 1,
    offsetX: 0,
    offsetY: 0,
    dragging: false,
    dragStartX: 0,
    dragStartY: 0,
  };

  const kindColors = {
    file: "#8dd3ff",
    module: "#7af0b6",
    class: "#ffd166",
    interface: "#d8a4ff",
    function: "#8dd3ff",
    method: "#ff9f7a",
    endpoint: "#ff7b8c",
    route: "#9ad3bc",
    variable: "#7fccff",
    component: "#a5d6a7",
    unknown: "#a4b3c9",
  };

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  function matchQuery(node, query) {
    if (!query) return true;
    const text = `${node.label || ""} ${node.qualified_name || ""} ${node.path || ""}`.toLowerCase();
    return text.includes(query.toLowerCase());
  }

  function getVisibleNodes() {
    const search = state.search.trim();
    return (graphData.nodes || []).filter((node) => {
      if (!state.nodeTypes.has(node.kind)) return false;
      return matchQuery(node, search);
    });
  }

  function getVisibleEdges() {
    const visibleNodeIds = new Set(getVisibleNodes().map((node) => node.id));
    const selectedEdgeKinds = state.edgeTypes;
    return (graphData.edges || []).filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target) && selectedEdgeKinds.has(edge.kind));
  }

  function computeLayout() {
    const visibleNodes = getVisibleNodes();
    const buckets = new Map();
    for (const node of visibleNodes) {
      if (!buckets.has(node.kind)) buckets.set(node.kind, []);
      buckets.get(node.kind).push(node);
    }

    const positions = new Map();
    let column = 0;
    for (const kind of Object.keys(kindColors)) {
      const bucket = buckets.get(kind) || [];
      if (bucket.length === 0) continue;
      for (let index = 0; index < bucket.length; index += 1) {
        const node = bucket[index];
        const x = 180 + column * 240 + (index % 3) * 80;
        const y = 120 + Math.floor(index / 3) * 120;
        positions.set(node.id, { x, y });
      }
      column += 1;
    }

    const remaining = visibleNodes.filter((node) => !positions.has(node.id));
    for (let index = 0; index < remaining.length; index += 1) {
      const node = remaining[index];
      positions.set(node.id, { x: 160 + (index % 4) * 180, y: 180 + Math.floor(index / 4) * 140 });
    }

    return positions;
  }

  function setDetailsPanel(target) {
    if (!details || !target) {
      return;
    }
    const htmlParts = [];
    if (target.kind) {
      htmlParts.push(`<div class="meta"><span class="badge detected">${target.kind}</span></div>`);
    }
    if (target.qualified_name) {
      htmlParts.push(`<h3>${target.qualified_name}</h3>`);
    }
    if (target.path || target.source_file) {
      htmlParts.push(`<div class="meta">Source: ${target.path || target.source_file || "unknown"}</div>`);
    }
    if (target.line) {
      htmlParts.push(`<div class="meta">Line: ${target.line}</div>`);
    }
    if (target.evidence) {
      htmlParts.push(`<div class="meta">Evidence: <span class="badge ${target.evidence.toLowerCase()}">${target.evidence}</span></div>`);
    }
    if (target.metadata && Object.keys(target.metadata).length > 0) {
      htmlParts.push(`<div class="meta">Metadata: ${Object.entries(target.metadata).slice(0, 6).map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}</div>`);
    }
    if (target.relationships && target.relationships.length) {
      htmlParts.push(`<div class="meta">Relationships: ${target.relationships.length}</div>`);
    }
    if (target.explanation) {
      htmlParts.push(`<p>${target.explanation}</p>`);
    }
    details.innerHTML = htmlParts.join("");
  }

  function renderGraph() {
    const visibleNodes = getVisibleNodes();
    const visibleEdges = getVisibleEdges();
    const positionMap = computeLayout();
    svg.innerHTML = "";

    if (!visibleNodes.length) {
      svg.innerHTML = '<text x="20" y="30" fill="#a4b3c9" font-size="16">No matching nodes.</text>';
      if (details) details.innerHTML = '<div class="relation-map-empty">No matching nodes are available for the selected filters.</div>';
      return;
    }

    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", "arrowhead");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "8");
    marker.setAttribute("refX", "6");
    marker.setAttribute("refY", "3");
    marker.setAttribute("orient", "auto");
    marker.innerHTML = '<path d="M0,0 L0,6 L6,3 z" fill="#a4b3c9"></path>';
    defs.appendChild(marker);
    svg.appendChild(defs);

    const edgeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const nodeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");

    for (const edge of visibleEdges) {
      const source = positionMap.get(edge.source);
      const target = positionMap.get(edge.target);
      if (!source || !target) continue;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const curve = Math.max(40, Math.abs(dx) * 0.25);
      const d = `M ${source.x} ${source.y} C ${source.x + curve} ${source.y}, ${target.x - curve} ${target.y}, ${target.x} ${target.y}`;
      path.setAttribute("d", d);
      path.setAttribute("class", `graph-edge ${state.selectedEdgeId === edge.id ? "selected" : ""}`.trim());
      path.setAttribute("stroke", "#a4b3c9");
      path.setAttribute("marker-end", "url(#arrowhead)");
      path.dataset.edgeId = edge.id;
      path.addEventListener("click", () => {
        state.selectedEdgeId = edge.id;
        state.selectedNodeId = null;
        const edgeRecord = graphData.edges.find((item) => item.id === edge.id);
        if (edgeRecord) {
          details.innerHTML = `<h3>${edgeRecord.kind}</h3><div class="meta">${edgeRecord.source} → ${edgeRecord.target}</div><div class="meta">Evidence: <span class="badge ${edgeRecord.evidence.toLowerCase()}">${edgeRecord.evidence}</span></div><p>${edgeRecord.explanation || "Source evidence recorded by the project analysis pipeline."}</p><div class="meta">File: ${edgeRecord.source_file || "unknown"}</div>`;
        }
        renderGraph();
      });
      edgeGroup.appendChild(path);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", String((source.x + target.x) / 2));
      label.setAttribute("y", String((source.y + target.y) / 2 - 8));
      label.setAttribute("class", "edge-label");
      label.textContent = edge.kind;
      edgeGroup.appendChild(label);
    }

    for (const node of visibleNodes) {
      const position = positionMap.get(node.id) || { x: 160, y: 140 };
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", `graph-node ${state.selectedNodeId === node.id ? "selected" : ""}`.trim());
      group.dataset.nodeId = node.id;

      const body = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      const width = Math.max(100, 12 + (node.label.length * 6));
      const height = 32;
      body.setAttribute("class", "node-body");
      body.setAttribute("x", String(position.x - width / 2));
      body.setAttribute("y", String(position.y - height / 2));
      body.setAttribute("rx", "10");
      body.setAttribute("width", String(width));
      body.setAttribute("height", String(height));
      body.setAttribute("fill", kindColors[node.kind] || kindColors.unknown);
      body.setAttribute("stroke", "rgba(255,255,255,0.2)");
      group.appendChild(body);

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", String(position.x));
      text.setAttribute("y", String(position.y + 4));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("class", "node-label");
      text.textContent = node.label.length > 24 ? `${node.label.slice(0, 22)}…` : node.label;
      group.appendChild(text);

      group.addEventListener("click", () => {
        state.selectedNodeId = node.id;
        state.selectedEdgeId = null;
        setDetailsPanel(node);
        renderGraph();
      });

      nodeGroup.appendChild(group);
    }

    svg.appendChild(edgeGroup);
    svg.appendChild(nodeGroup);
    const transform = `translate(${state.offsetX}px, ${state.offsetY}px) scale(${state.scale})`;
    svg.setAttribute("transform", transform);

    if (details && !state.selectedNodeId && !state.selectedEdgeId) {
      const summaryNode = visibleNodes[0];
      if (summaryNode) {
        setDetailsPanel(summaryNode);
      }
    }
  }

  function applyFilters() {
    state.nodeTypes = new Set(nodeTypeFilters.filter((input) => input.checked).map((input) => input.value));
    state.edgeTypes = new Set(edgeTypeFilters.filter((input) => input.checked).map((input) => input.value));
    renderGraph();
  }

  searchInput.addEventListener("input", (event) => {
    state.search = event.target.value;
    renderGraph();
  });
  nodeTypeFilters.forEach((input) => input.addEventListener("change", applyFilters));
  edgeTypeFilters.forEach((input) => input.addEventListener("change", applyFilters));

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.graphAction;
      if (action === "zoom-in") {
        state.scale = clamp(state.scale * 1.2, 0.3, 2.5);
      } else if (action === "zoom-out") {
        state.scale = clamp(state.scale / 1.2, 0.3, 2.5);
      } else if (action === "reset") {
        state.scale = 1;
        state.offsetX = 0;
        state.offsetY = 0;
      }
      renderGraph();
    });
  });

  svg.addEventListener("pointerdown", (event) => {
    state.dragging = true;
    state.dragStartX = event.clientX - state.offsetX;
    state.dragStartY = event.clientY - state.offsetY;
  });
  svg.addEventListener("pointermove", (event) => {
    if (!state.dragging) return;
    state.offsetX = event.clientX - state.dragStartX;
    state.offsetY = event.clientY - state.dragStartY;
    renderGraph();
  });
  svg.addEventListener("pointerup", () => {
    state.dragging = false;
  });
  svg.addEventListener("pointerleave", () => {
    state.dragging = false;
  });

  renderGraph();
});
"""


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


def _render_relation_map_page(project: Project) -> str:
    graph = build_relation_graph(project, view="relation_map")
    graph_payload = json.dumps(graph.as_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    node_types = sorted({node.kind for node in graph.nodes}) or ["file"]
    edge_types = sorted({edge.kind for edge in graph.edges}) or ["imports"]
    legend_items = [
        ('file', '#8dd3ff'),
        ('module', '#7af0b6'),
        ('class', '#ffd166'),
        ('interface', '#d8a4ff'),
        ('function', '#8dd3ff'),
        ('method', '#ff9f7a'),
        ('endpoint', '#ff7b8c'),
    ]
    filter_boxes = (
        ''.join(
            f'<label class="filter-chip"><input type="checkbox" data-filter-node value="{_escape(kind)}" checked /> {_escape(kind)}</label>'
            for kind in node_types
        )
        + ''.join(
            f'<label class="filter-chip"><input type="checkbox" data-filter-edge value="{_escape(kind)}" checked /> {_escape(kind)}</label>'
            for kind in edge_types
        )
    )
    legend_html = ''.join(
        f'<div class="legend-item"><span class="legend-swatch" style="background: {color};"></span>{_escape(kind)}</div>'
        for kind, color in legend_items
    )
    if graph.edges:
        edges = ''.join(
            f'<div class="relationship-item"><h3>{_escape(edge.source)} → {_escape(edge.target)}</h3><div class="meta">{_relationship_badge(edge.evidence)} <span class="code">{_escape(edge.kind)}</span></div><div class="meta">{_escape(edge.source_file or "Unknown file")}</div><p>{_escape(edge.explanation or "Static relationship discovered during source analysis.")}</p></div>'
            for edge in graph.edges[:20]
        )
        relationship_listing = f'<div class="relationship-list">{edges}</div>'
    else:
        relationship_listing = '<div class="relation-map-empty">No relationships were detected for the current scan.</div>'

    body = (
        '<section class="section">'
        '<h2>Relation Map</h2>'
        '<div class="section-subtitle">A normalized graph built from the current scan results and evidence-labeled relationships.</div>'
        + (f'<div class="meta">Graph nodes: {len(graph.nodes)} · edges: {len(graph.edges)} · unresolved: {len(graph.unresolved)}</div>' if graph.nodes or graph.edges else '')
        + '<div id="relation-map-shell">'
        '  <div id="relation-map-panel" class="card">'
        '    <div class="graph-tools">'
        '      <input id="relation-map-search" type="search" placeholder="Search by file path or symbol name" aria-label="Search graph" />'
        '      <button type="button" data-graph-action="zoom-in">Zoom+</button>'
        '      <button type="button" data-graph-action="zoom-out">Zoom-</button>'
        '      <button type="button" data-graph-action="reset">Reset view</button>'
        '    </div>'
        '    <div class="graph-filters">' + filter_boxes + '</div>'
        '    <svg id="relation-map-canvas" aria-label="Relation map graph"></svg>'
        '  </div>'
        '  <aside id="relation-map-details" class="card">'
        '    <h3>Node details</h3>'
        '    <div class="meta">Select a node or edge to inspect its evidence.</div>'
        '  </aside>'
        '</div>'
        + '<div class="section">'
        '<h3>Legend</h3>'
        '<div class="legend-grid">' + legend_html + '</div>'
        '</div>'
        + '<div class="section">'
        '<h3>Relationship list</h3>'
        + relationship_listing
        + '</div>'
        + (f'<script type="application/json" id="relation-map-data">{graph_payload}</script>' if graph_payload else '<script type="application/json" id="relation-map-data">{"nodes":[],"edges":[]}</script>')
        + '<script src="assets/relation-map.js" defer></script>'
        + '</section>'
    )
    return _page_shell(f"Relation Map — {_project_name(project)}", "relation-map", body)


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


def _render_json_data(project: Project) -> str:
    if not project.data:
        return '<div class="empty-state">No JSON data objects or arrays were extracted.</div>'

    items = []
    for item in sorted(project.data, key=lambda node: (node.metadata.get("path", node.path), node.kind)):
        key_summary = ", ".join(item.keys) if item.keys else "(empty)"
        value_preview = item.value if item.value is not None else ""
        meta_parts = [
            f"Type: {_escape(item.value_type or item.kind or 'unknown')}",
            f"Path: {_escape(item.metadata.get('path', item.path))}",
        ]
        if item.keys:
            meta_parts.append(f"Keys: {_escape(key_summary)}")
        if value_preview:
            meta_parts.append(f"Value: {_escape(value_preview)}")
        items.append(
            f"""
            <div class="entity-item">
              <h3>{_escape(item.name)}</h3>
              <div class="meta">{' · '.join(meta_parts)}</div>
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
    json_section = (
        '<div class="section">'
        '<h2>JSON data</h2>'
        '<div class="section-subtitle">Structured JSON values extracted as data facts without classifying them as functions or methods.</div>'
        + _render_json_data(project)
        + '</div>'
    )
    body = f'<section class="hero">{project_summary}{stats}</section>{overview}{evidence}{documentation}{structure}{json_section}'
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
    project_obj = project
    build_relation_graph(project_obj)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    assets_dir = output_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    (assets_dir / "site.css").write_text(CSS, encoding="utf-8")
    (assets_dir / "relation-map.js").write_text(RELATION_MAP_JS, encoding="utf-8")

    index_path = output_path / "index.html"
    entities_path = output_path / "entities.html"
    relationships_path = output_path / "relationships.html"
    relation_map_path = output_path / "relation-map.html"

    index_path.write_text(_render_index(project_obj), encoding="utf-8")
    entities_path.write_text(_render_entities_page(project_obj), encoding="utf-8")
    relationships_path.write_text(_render_relationships_page(project_obj), encoding="utf-8")
    relation_map_path.write_text(_render_relation_map_page(project_obj), encoding="utf-8")

    return [index_path, entities_path, relationships_path, relation_map_path, assets_dir / "site.css", assets_dir / "relation-map.js"]


def generate_html_website(project: Project, output_dir: str | Path) -> list[Path]:
    return render_project_website(project, output_dir)


__all__ = [
    "CSS",
    "render_project_website",
    "generate_html_website",
]
