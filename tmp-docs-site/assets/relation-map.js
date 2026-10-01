
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
