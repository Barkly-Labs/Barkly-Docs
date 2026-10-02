from __future__ import annotations

import html
import json
import re
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
  const depthInput = document.getElementById("relation-map-depth");
  const nodeTypeFilters = Array.from(document.querySelectorAll("input[data-filter-node]"));
  const edgeTypeFilters = Array.from(document.querySelectorAll("input[data-filter-edge]"));
  const evidenceFilters = Array.from(document.querySelectorAll("input[data-filter-evidence]"));
  const directionFilters = Array.from(document.querySelectorAll("input[data-filter-direction]"));
  const buttons = Array.from(document.querySelectorAll("[data-graph-action]"));
  const nodeMap = new Map((graphData.nodes || []).map((node) => [node.id, node]));
  const edgeMap = new Map((graphData.edges || []).map((edge) => [edge.id, edge]));
  const state = {
    selectedNodeId: null,
    selectedEdgeId: null,
    search: "",
    nodeTypes: new Set(nodeTypeFilters.filter((input) => input.checked).map((input) => input.value)),
    edgeTypes: new Set(edgeTypeFilters.filter((input) => input.checked).map((input) => input.value)),
    evidenceTypes: new Set(evidenceFilters.filter((input) => input.checked).map((input) => input.value)),
    showIncoming: true,
    showOutgoing: true,
    hopDepth: Number(depthInput?.value || 1),
    scale: 1,
    offsetX: 0,
    offsetY: 0,
    dragging: false,
    dragStartX: 0,
    dragStartY: 0,
  };

  const kindColors = {
    file: "#ff6b9d",
    module: "#7dffb2",
    class: "#ffd76b",
    interface: "#c4a7ff",
    function: "#ff6b9d",
    method: "#ffb38a",
    endpoint: "#ff8aa1",
    route: "#7dffb2",
    variable: "#ff9fc0",
    component: "#b7e4a8",
    unknown: "#9a9a9a",
  };

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const nodeRadius = (node) => Math.max(18, Math.min(54, 10 + (node.label || "").length * 1.2));

  function matchQuery(node, query) {
    if (!query) return true;
    const text = `${node.label || ""} ${node.qualified_name || ""} ${node.path || ""} ${node.source_file || ""}`.toLowerCase();
    return text.includes(query.toLowerCase());
  }

  function getVisibleNodes() {
    const query = state.search.trim();
    const baseNodes = (graphData.nodes || []).filter((node) => {
      if (!state.nodeTypes.has(node.kind)) return false;
      return matchQuery(node, query);
    });

    if (!state.selectedNodeId) {
      return baseNodes;
    }

    const focusNode = nodeMap.get(state.selectedNodeId);
    if (!focusNode) {
      return baseNodes;
    }

    const matching = new Set(baseNodes.map((node) => node.id));
    const visited = new Set([focusNode.id]);
    const queue = [{ id: focusNode.id, depth: 0 }];

    while (queue.length) {
      const current = queue.shift();
      if (!current) continue;
      const edges = (graphData.edges || []).filter((edge) => {
        if (!state.edgeTypes.has(edge.kind)) return false;
        if (edge.source === current.id && state.showOutgoing) return true;
        if (edge.target === current.id && state.showIncoming) return true;
        return false;
      });
      for (const edge of edges) {
        const next = edge.source === current.id ? edge.target : edge.source;
        if (next === current.id) continue;
        if (visited.has(next)) continue;
        const nextDepth = current.depth + 1;
        if (nextDepth > state.hopDepth) continue;
        visited.add(next);
        queue.push({ id: next, depth: nextDepth });
        matching.add(next);
      }
    }

    return baseNodes.filter((node) => matching.has(node.id) || node.id === focusNode.id);
  }

  function getVisibleEdges() {
    const visibleNodeIds = new Set(getVisibleNodes().map((node) => node.id));
    return (graphData.edges || []).filter((edge) => {
      if (!state.edgeTypes.has(edge.kind)) return false;
      if (!state.evidenceTypes.has((edge.evidence || "UNKNOWN").toUpperCase())) return false;
      if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) return false;
      const sourceToTarget = edge.source === state.selectedNodeId || edge.target === state.selectedNodeId;
      if (state.selectedNodeId && !sourceToTarget && state.hopDepth <= 1) {
        return false;
      }
      if (edge.source === state.selectedNodeId && !state.showOutgoing) return false;
      if (edge.target === state.selectedNodeId && !state.showIncoming) return false;
      return true;
    });
  }

  function ensureNodePositions(nodes) {
    const positions = new Map();
    if (!nodes.length) return positions;
    const centerX = 420;
    const centerY = 260;
    if (nodes.length === 1) {
      positions.set(nodes[0].id, { x: centerX, y: centerY, vx: 0, vy: 0 });
      return positions;
    }

    const angleStep = (Math.PI * 2) / nodes.length;
    nodes.forEach((node, index) => {
      const angle = angleStep * index;
      const radius = Math.min(180, 90 + nodes.length * 6);
      positions.set(node.id, {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
      });
    });
    return positions;
  }

  function computeLayout() {
    const visibleNodes = getVisibleNodes();
    const visibleEdges = getVisibleEdges();
    if (!visibleNodes.length) return new Map();

    const positions = ensureNodePositions(visibleNodes);
    const centerNode = state.selectedNodeId ? nodeMap.get(state.selectedNodeId) : null;
    const focusPos = centerNode ? positions.get(centerNode.id) || { x: 420, y: 260 } : { x: 420, y: 260 };

    for (let iteration = 0; iteration < 120; iteration += 1) {
      const forces = new Map();
      for (const node of visibleNodes) {
        forces.set(node.id, { x: 0, y: 0 });
      }

      for (let index = 0; index < visibleNodes.length; index += 1) {
        for (let otherIndex = index + 1; otherIndex < visibleNodes.length; otherIndex += 1) {
          const a = visibleNodes[index];
          const b = visibleNodes[otherIndex];
          const pa = positions.get(a.id);
          const pb = positions.get(b.id);
          if (!pa || !pb) continue;
          const dx = pb.x - pa.x;
          const dy = pb.y - pa.y;
          const distSq = dx * dx + dy * dy + 0.0001;
          const dist = Math.sqrt(distSq);
          const repulse = (1200 / distSq) * 1.3;
          const fx = (dx / dist) * repulse;
          const fy = (dy / dist) * repulse;
          forces.get(a.id).x -= fx;
          forces.get(a.id).y -= fy;
          forces.get(b.id).x += fx;
          forces.get(b.id).y += fy;
        }
      }

      for (const edge of visibleEdges) {
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) continue;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const spring = (dist - 110) * 0.035;
        const fx = (dx / dist) * spring;
        const fy = (dy / dist) * spring;
        forces.get(edge.source).x += fx;
        forces.get(edge.source).y += fy;
        forces.get(edge.target).x -= fx;
        forces.get(edge.target).y -= fy;
      }

      for (const node of visibleNodes) {
        const pos = positions.get(node.id);
        const force = forces.get(node.id);
        if (!pos || !force) continue;
        pos.vx = (pos.vx + force.x) * 0.72;
        pos.vy = (pos.vy + force.y) * 0.72;
        pos.x += pos.vx;
        pos.y += pos.vy;

        if (node.id === centerNode?.id) {
          pos.x += (focusPos.x - pos.x) * 0.30;
          pos.y += (focusPos.y - pos.y) * 0.30;
        }

        pos.x = clamp(pos.x, 40, 860);
        pos.y = clamp(pos.y, 40, 520);
      }
    }

    return positions;
  }

  function buildRelatedList(nodeId) {
    const relations = (graphData.edges || []).filter((edge) => edge.source === nodeId || edge.target === nodeId);
    const names = relations.map((edge) => {
      const other = edge.source === nodeId ? edge.target : edge.source;
      const entry = nodeMap.get(other) || { label: other, qualified_name: other };
      return `<li><a href="#" data-select-node="${other}">${entry.label || entry.qualified_name || other}</a> <span class="badge ${edge.evidence.toLowerCase()}">${edge.evidence}</span> <span class="code">${edge.kind}</span></li>`;
    });
    return names.length ? `<ul>${names.join('')}</ul>` : '<div class="meta">No adjacent links in the current scope.</div>';
  }

  function setDetailsPanel(target) {
    if (!details || !target) {
      return;
    }
    const incoming = (graphData.edges || []).filter((edge) => edge.target === target.id && state.edgeTypes.has(edge.kind));
    const outgoing = (graphData.edges || []).filter((edge) => edge.source === target.id && state.edgeTypes.has(edge.kind));

    const related = buildRelatedList(target.id);
    const htmlParts = [
      `<div class="meta"><span class="badge detected">${target.kind || "entity"}</span></div>`,
      `<h3>${target.qualified_name || target.label || target.id}</h3>`,
      target.path || target.source_file ? `<div class="meta">Source: ${target.path || target.source_file || "unknown"}</div>` : "",
      target.line ? `<div class="meta">Line: ${target.line}</div>` : "",
      target.evidence ? `<div class="meta">Evidence: <span class="badge ${target.evidence.toLowerCase()}">${target.evidence}</span></div>` : "",
      `<div class="meta">Incoming: ${incoming.length} · Outgoing: ${outgoing.length}</div>`,
      `<div class="section"><h4>Connected entities</h4>${related}</div>`,
    ];

    details.innerHTML = htmlParts.join("");

    details.querySelectorAll("[data-select-node]").forEach((anchor) => {
      anchor.addEventListener("click", (event) => {
        event.preventDefault();
        const relatedId = anchor.getAttribute("data-select-node");
        if (relatedId) {
          state.selectedNodeId = relatedId;
          state.selectedEdgeId = null;
          renderGraph();
        }
      });
    });
  }

  function fitToViewport() {
    const visibleNodes = getVisibleNodes();
    if (!visibleNodes.length) {
      state.scale = 1;
      state.offsetX = 0;
      state.offsetY = 0;
      return;
    }

    const positions = computeLayout();
    const xs = [];
    const ys = [];
    for (const node of visibleNodes) {
      const pos = positions.get(node.id);
      if (!pos) continue;
      xs.push(pos.x);
      ys.push(pos.y);
    }
    if (!xs.length) return;
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);
    const width = Math.max(1, maxX - minX);
    const height = Math.max(1, maxY - minY);
    const viewWidth = 900;
    const viewHeight = 560;
    const scale = clamp(Math.min((viewWidth - 80) / width, (viewHeight - 80) / height), 0.35, 2.2);
    state.scale = scale;
    state.offsetX = (viewWidth / 2) - ((minX + maxX) / 2) * scale;
    state.offsetY = (viewHeight / 2) - ((minY + maxY) / 2) * scale;
  }

  function renderGraph() {
    const visibleNodes = getVisibleNodes();
    const visibleEdges = getVisibleEdges();
    const positionMap = computeLayout();

    svg.innerHTML = "";
    const root = document.createElementNS("http://www.w3.org/2000/svg", "g");
    root.setAttribute("transform", `translate(${state.offsetX} ${state.offsetY}) scale(${state.scale})`);

    if (!visibleNodes.length) {
      svg.innerHTML = '<text x="20" y="30" fill="#9a9a9a" font-size="16">No matching nodes.</text>';
      if (details) details.innerHTML = '<div class="relation-map-empty">No matching nodes are available for the selected filters.</div>';
      return;
    }

    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", "arrowhead");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "8");
    marker.setAttribute("refX", "7");
    marker.setAttribute("refY", "3.5");
    marker.setAttribute("orient", "auto");
    marker.innerHTML = '<path d="M0,0 L7,3.5 L0,7 z" fill="#9a9a9a"></path>';
    defs.appendChild(marker);
    root.appendChild(defs);

    const edgeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    for (const edge of visibleEdges) {
      const source = positionMap.get(edge.source);
      const target = positionMap.get(edge.target);
      if (!source || !target) continue;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const curve = Math.max(40, Math.abs(dx) * 0.18);
      const d = `M ${source.x} ${source.y} C ${source.x + curve} ${source.y}, ${target.x - curve} ${target.y}, ${target.x} ${target.y}`;
      path.setAttribute("d", d);
      path.setAttribute("class", `graph-edge ${state.selectedEdgeId === edge.id ? "selected" : ""}`.trim());
      path.setAttribute("stroke", edge.evidence === "DECLARED" ? "#7dffb2" : edge.evidence === "INFERRED" ? "#ffd76b" : edge.evidence === "UNKNOWN" ? "#ff8aa1" : "#9a9a9a");
      path.setAttribute("stroke-width", edge.evidence === "UNKNOWN" ? "1.1" : "1.5");
      path.setAttribute("fill", "none");
      path.setAttribute("marker-end", "url(#arrowhead)");
      path.dataset.edgeId = edge.id;
      path.addEventListener("click", () => {
        state.selectedEdgeId = edge.id;
        state.selectedNodeId = null;
        const edgeItem = edgeMap.get(edge.id);
        if (edgeItem) {
          details.innerHTML = `<h3>${edgeItem.kind}</h3><div class="meta">${edgeItem.source} → ${edgeItem.target}</div><div class="meta">Evidence: <span class="badge ${String(edgeItem.evidence || "UNKNOWN").toLowerCase()}">${edgeItem.evidence || "UNKNOWN"}</span></div><div class="meta">File: ${edgeItem.source_file || "unknown"}</div><p>${edgeItem.explanation || "Static relationship recorded during project analysis."}</p>`;
        }
      });
      edgeGroup.appendChild(path);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", String((source.x + target.x) / 2));
      label.setAttribute("y", String((source.y + target.y) / 2 - 8));
      label.setAttribute("class", "edge-label");
      label.textContent = edge.kind;
      edgeGroup.appendChild(label);
    }
    root.appendChild(edgeGroup);

    const nodeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    for (const node of visibleNodes) {
      const position = positionMap.get(node.id) || { x: 300, y: 200 };
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", `graph-node ${state.selectedNodeId === node.id ? "selected" : ""}`.trim());
      group.dataset.nodeId = node.id;

      const width = Math.max(88, nodeRadius(node) * 3.6);
      const height = 34;
      const body = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      body.setAttribute("class", "node-body");
      body.setAttribute("x", String(position.x - width / 2));
      body.setAttribute("y", String(position.y - height / 2));
      body.setAttribute("rx", "12");
      body.setAttribute("width", String(width));
      body.setAttribute("height", String(height));
      body.setAttribute("fill", kindColors[node.kind] || kindColors.unknown);
      body.setAttribute("stroke", "rgba(255,255,255,0.3)");
      body.setAttribute("stroke-width", state.selectedNodeId === node.id ? "2.8" : "1.2");
      group.appendChild(body);

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", String(position.x));
      text.setAttribute("y", String(position.y + 4));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("class", "node-label");
      const labelText = (node.label || node.qualified_name || node.id).slice(0, 26);
      text.textContent = labelText;
      group.appendChild(text);

      group.addEventListener("click", () => {
        state.selectedNodeId = node.id;
        state.selectedEdgeId = null;
        setDetailsPanel(node);
        renderGraph();
      });
      nodeGroup.appendChild(group);
    }
    root.appendChild(nodeGroup);
    svg.appendChild(root);

    if (details && !state.selectedNodeId && !state.selectedEdgeId) {
      const summaryNode = visibleNodes[0];
      if (summaryNode) setDetailsPanel(summaryNode);
    }
  }

  function applyFilters() {
    state.nodeTypes = new Set(nodeTypeFilters.filter((input) => input.checked).map((input) => input.value));
    state.edgeTypes = new Set(edgeTypeFilters.filter((input) => input.checked).map((input) => input.value));
    state.evidenceTypes = new Set(evidenceFilters.filter((input) => input.checked).map((input) => input.value));
    state.showIncoming = directionFilters.some((input) => input.dataset.filterDirection === "incoming" && input.checked);
    state.showOutgoing = directionFilters.some((input) => input.dataset.filterDirection === "outgoing" && input.checked);
    renderGraph();
  }

  function handleButtonAction(action) {
    if (action === "zoom-in") {
      state.scale = clamp(state.scale * 1.2, 0.35, 2.5);
    } else if (action === "zoom-out") {
      state.scale = clamp(state.scale / 1.2, 0.35, 2.5);
    } else if (action === "fit") {
      fitToViewport();
    } else if (action === "reset") {
      state.scale = 1;
      state.offsetX = 0;
      state.offsetY = 0;
      state.selectedNodeId = null;
      state.selectedEdgeId = null;
      state.hopDepth = 1;
      if (depthInput) depthInput.value = "1";
    } else if (action === "reset-filters") {
      nodeTypeFilters.forEach((input) => { input.checked = true; });
      edgeTypeFilters.forEach((input) => { input.checked = true; });
      evidenceFilters.forEach((input) => { input.checked = true; });
      directionFilters.forEach((input) => { input.checked = true; });
      state.hopDepth = 1;
      if (depthInput) depthInput.value = "1";
      state.selectedNodeId = null;
      state.selectedEdgeId = null;
      applyFilters();
      return;
    } else if (action === "expand") {
      if (state.selectedNodeId) {
        state.hopDepth = Math.min(4, Number(state.hopDepth) + 1);
        if (depthInput) depthInput.value = String(state.hopDepth);
      }
    } else if (action === "focus") {
      state.selectedNodeId = state.selectedNodeId || (graphData.nodes || [])[0]?.id || null;
      fitToViewport();
    }
    renderGraph();
  }

  searchInput?.addEventListener("input", (event) => {
    state.search = event.target.value;
    renderGraph();
  });
  depthInput?.addEventListener("change", (event) => {
    state.hopDepth = Number(event.target.value) || 1;
    renderGraph();
  });
  nodeTypeFilters.forEach((input) => input.addEventListener("change", applyFilters));
  edgeTypeFilters.forEach((input) => input.addEventListener("change", applyFilters));
  evidenceFilters.forEach((input) => input.addEventListener("change", applyFilters));
  directionFilters.forEach((input) => input.addEventListener("change", applyFilters));
  buttons.forEach((button) => {
    button.addEventListener("click", () => handleButtonAction(button.dataset.graphAction));
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
  svg.addEventListener("pointerup", () => { state.dragging = false; });
  svg.addEventListener("pointerleave", () => { state.dragging = false; });

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

def _render_relationship_pipeline(graph) -> str:
    """Render discovered graph edges as readable source-to-target pipelines."""

    if not graph.edges:
        return (
            '<div class="empty-state">'
            'No relationships were detected for the current scan.'
            '</div>'
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
                edge.explanation
                or "Relationship recorded during static analysis."
            )

            steps.append(
                f"""
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
                """
            )

        groups.append(
            f"""
            <section class="pipeline-group">
              <div class="pipeline-group-header">
                <h3>{_escape(source_file)}</h3>
                <span class="badge detected">
                  {len(edges)} relationship(s)
                </span>
              </div>
              {''.join(steps)}
            </section>
            """
        )

    return '<div class="pipeline-list">' + "".join(groups) + "</div>"


def _render_relation_map_page(project: Project) -> str:
    graph = build_relation_graph(project, view="relation_map", max_nodes=None, max_edges=None)
    graph_payload = json.dumps(graph.as_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    node_types = sorted({node.kind for node in graph.nodes}) or ["file"]
    edge_types = sorted({edge.kind for edge in graph.edges}) or ["imports"]
    legend_items = [
        ('file', '#ff6b9d'),
        ('module', '#7dffb2'),
        ('class', '#ffd76b'),
        ('interface', '#d8a4ff'),
        ('function', '#ff6b9d'),
        ('method', '#ff9f7a'),
        ('endpoint', '#ff7b8c'),
    ]
    evidence_types = ["DECLARED", "DETECTED", "INFERRED", "UNKNOWN"]
    filter_boxes = (
        ''.join(
            f'<label class="filter-chip"><input type="checkbox" data-filter-node value="{_escape(kind)}" checked /> {_escape(kind)}</label>'
            for kind in node_types
        )
        + ''.join(
            f'<label class="filter-chip"><input type="checkbox" data-filter-edge value="{_escape(kind)}" checked /> {_escape(kind)}</label>'
            for kind in edge_types
        )
        + ''.join(
            f'<label class="filter-chip"><input type="checkbox" data-filter-evidence value="{_escape(kind)}" checked /> {_escape(kind)}</label>'
            for kind in evidence_types
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
        relationship_listing = _render_relationship_pipeline(graph)
    else:
        relationship_listing = '<div class="relation-map-empty">No relationships were detected for the current scan.</div>'

    body = (
        '<section class="section">'
        '<h2>Relation Map</h2>'
        '<div class="section-subtitle">A force-directed spider-web graph built from the current scan results and evidence-labeled relationships.</div>'
        + (f'<div class="meta">Graph nodes: {len(graph.nodes)} · edges: {len(graph.edges)} · unresolved: {len(graph.unresolved)}</div>' if graph.nodes or graph.edges else '')
        + (f'<div class="meta">{_escape(graph.warnings[0])}</div>' if graph.warnings else '')
        + '<div id="relation-map-shell">'
        '  <div id="relation-map-panel" class="card">'
        '    <div class="graph-tools">'
        '      <input id="relation-map-search" type="search" placeholder="Search by file path or symbol name" aria-label="Search graph" />'
        '      <label class="filter-chip"><input type="checkbox" data-filter-direction="incoming" checked /> Incoming</label>'
        '      <label class="filter-chip"><input type="checkbox" data-filter-direction="outgoing" checked /> Outgoing</label>'
        '      <select id="relation-map-depth" aria-label="Relationship hop depth">'
        '        <option value="1">1 hop</option>'
        '        <option value="2">2 hops</option>'
        '        <option value="3">3 hops</option>'
        '        <option value="4">4 hops</option>'
        '      </select>'
        '      <button type="button" data-graph-action="focus">Center</button>'
        '      <button type="button" data-graph-action="expand">Expand</button>'
        '      <button type="button" data-graph-action="fit">Fit</button>'
        '      <button type="button" data-graph-action="zoom-in">Zoom+</button>'
        '      <button type="button" data-graph-action="zoom-out">Zoom-</button>'
        '      <button type="button" data-graph-action="reset">Reset view</button>'
        '      <button type="button" data-graph-action="reset-filters">Reset filters</button>'
        '    </div>'
        '    <div class="graph-filters">' + filter_boxes + '</div>'
        '    <svg id="relation-map-canvas" aria-label="Relation map graph" viewBox="0 0 900 560"></svg>'
        '  </div>'
        '  <aside id="relation-map-details" class="card">'
        '    <h3>Node details</h3>'
        '    <div class="meta">Select a node or edge to inspect its evidence and relationships.</div>'
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




def _render_relationship_preview(project: Project, graph_generated: bool = True) -> str:
    if not project.relationships:
        return (
            '<div class="empty-state">'
            'No relationships were discovered for this project yet.'
            '</div>'
        )

    if not graph_generated:
        return (
            '<div class="empty-state">'
            'The relationship graph could not be generated. '
            'Install Graphviz and the Python graphviz package, then regenerate the docs.'
            '</div>'
        )

    return f"""
    <div class="relationship-preview">
      <a href="relationships.html" aria-label="Open the complete relationship list">
        <img
          src="assets/relationship-graph.png"
          alt="Graphviz diagram of detected relationships between project entities"
          loading="lazy"
        />
      </a>
      <p class="meta">
        Graphviz diagram of {len(project.relationships)} detected relationships.
        <a href="relationships.html">Explore the complete relationship list</a>.
        <a href="relation-map.html">Open interactive relationship map</a>.
      </p>
    </div>
    """


def _write_relationship_graph_png(project: Project, output_path: Path) -> bool:
    """Render the project's actual relationship model as a Graphviz PNG."""
    if not project.relationships:
        return False

    try:
        from graphviz import Digraph
    except ImportError:
        return False

    graph = Digraph(
        name="BarklyRelationships",
        format="png",
        engine="dot",
        graph_attr={
            "bgcolor": "#080808",
            "rankdir": "LR",
            "splines": "true",
            "overlap": "false",
            "pad": "0.35",
            "nodesep": "0.45",
            "ranksep": "0.8",
            "fontname": "Arial",
            "fontsize": "20",
            "fontcolor": "#ff6b9d",
            "label": "BARKLY DOCS  /  RELATIONSHIP GRAPH",
            "labelloc": "t",
        },
        node_attr={
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "#101010",
            "color": "#ff6b9d",
            "fontcolor": "#f2f2f2",
            "fontname": "Arial",
            "fontsize": "10",
            "margin": "0.16,0.10",
        },
        edge_attr={
            "color": "#9a9a9a",
            "fontcolor": "#ffd76b",
            "fontname": "Arial",
            "fontsize": "8",
            "arrowsize": "0.7",
        },
    )

    evidence_colors = {
        "DECLARED": "#7dffb2",
        "DETECTED": "#ff6b9d",
        "INFERRED": "#ffd76b",
        "UNKNOWN": "#ff7b8c",
    }

    def node_id(value: object) -> str:
        # Graphviz IDs are generated from labels, avoiding unsafe raw identifiers.
        return str(value or "Unknown").strip() or "Unknown"

    relationships = sorted(
        project.relationships,
        key=lambda rel: (
            str(rel.source).lower(),
            str(rel.kind).lower(),
            str(rel.target).lower(),
        ),
    )

    for rel in relationships:
        source = node_id(rel.source)
        target = node_id(rel.target)
        kind = str(rel.kind or "related to")
        evidence = str(rel.evidence or "UNKNOWN").upper()
        edge_color = evidence_colors.get(evidence, "#9a9a9a")

        graph.node(source, label=source, color="#ff6b9d", fillcolor="#191219")
        graph.node(target, label=target, color="#7dffb2", fillcolor="#101b15")
        graph.edge(
            source,
            target,
            label=f"{kind} · {evidence}",
            color=edge_color,
            fontcolor=edge_color,
            tooltip=str(getattr(rel, "explanation", "") or kind),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Graphviz appends the selected format extension; cleanup removes its .gv source.
        rendered = Path(graph.render(filename=output_path.stem, directory=str(output_path.parent), cleanup=True))
        if rendered != output_path and rendered.exists():
            rendered.replace(output_path)
        return output_path.exists()
    except Exception:
        # Missing Graphviz system executable or another render error: keep HTML generation alive.
        return False


def _render_index(project: Project, graph_generated: bool = True) -> str:
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
    relationship_preview = (
        '<div class="section">'
        '<h2>Relationship Pipeline</h2>'
        '<div class="section-subtitle">'
        'A visual summary of how discovered project entities connect.'
        '</div>'
        + _render_relationship_preview(project, graph_generated)
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
  
    body = (
        f'<section class="hero">{project_summary}{stats}</section>'
        f'{relationship_preview}'
        f'{overview}{evidence}{documentation}{structure}{json_section}'
    )
    return _page_shell(
        f"{_project_name(project)} — Barkly Docs",
        "index",
        body,
    )
   


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

    relationship_graph_png = assets_dir / "relationship-graph.png"
    graph_generated = _write_relationship_graph_png(project_obj, relationship_graph_png)

    index_path = output_path / "index.html"
    entities_path = output_path / "entities.html"
    relationships_path = output_path / "relationships.html"
    relation_map_path = output_path / "relation-map.html"

    index_path.write_text(_render_index(project_obj, graph_generated), encoding="utf-8")
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
