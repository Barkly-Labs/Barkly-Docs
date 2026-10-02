
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
