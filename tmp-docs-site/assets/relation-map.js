
(() => {
  "use strict";

  const dataElement = document.getElementById("relation-map-data");
  const grid = document.getElementById("relation-card-grid");
  const search = document.getElementById("relation-map-search");
  const kindFilter = document.getElementById("relation-map-kind");
  const count = document.getElementById("relation-map-count");
  const pagination = document.getElementById("relation-map-pagination");

  if (!dataElement || !grid) return;

  let graph;
  try {
    graph = JSON.parse(dataElement.textContent || "{}");
  } catch (error) {
    grid.textContent = "The relationship data could not be read.";
    return;
  }

  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph.edges) ? graph.edges : [];
  const byId = new Map(nodes.map(node => [String(node.id), node]));
  const pageSize = 80;
  let page = 0;
  let filtered = nodes.slice();

  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;"
  })[char]);

  const value = (obj, ...keys) => {
    for (const key of keys) {
      if (obj && obj[key] !== undefined && obj[key] !== null && obj[key] !== "") {
        return obj[key];
      }
    }
    return "";
  };

  const kindOf = node => String(value(node, "kind", "type") || "unknown");
  const labelOf = node => String(value(node, "label", "name", "qualified_name") || node.id || "Unnamed item");
  const pathOf = node => String(value(node, "path", "source_file", "file_path") || "");
  const evidenceOf = item => value(item, "evidence", "evidence_level") || "Not specified";

  const incident = new Map();
  for (const edge of edges) {
    const from = String(edge.source ?? "");
    const to = String(edge.target ?? "");
    if (!incident.has(from)) incident.set(from, { incoming: [], outgoing: [] });
    if (!incident.has(to)) incident.set(to, { incoming: [], outgoing: [] });
    incident.get(from).outgoing.push(edge);
    incident.get(to).incoming.push(edge);
  }

  const kinds = [...new Set(nodes.map(kindOf))].sort((a, b) => a.localeCompare(b));
  for (const kind of kinds) {
    const option = document.createElement("option");
    option.value = kind;
    option.textContent = kind;
    kindFilter.appendChild(option);
  }

  function relatedMarkup(list, direction) {
    if (!list.length) return '<p class="muted">No ' + direction + ' relationships detected.</p>';
    return '<ul class="relation-links">' + list.map(edge => {
      const otherId = direction === "incoming" ? String(edge.source) : String(edge.target);
      const other = byId.get(otherId);
      const otherName = other ? labelOf(other) : otherId;
      const relation = value(edge, "label", "kind") || "related to";
      return '<li><button type="button" class="relation-link" data-open-node="' +
        esc(otherId) + '">' + esc(otherName) + '</button>' +
        '<span class="muted"> ? ' + esc(relation) + '</span></li>';
    }).join("") + "</ul>";
  }

  function cardMarkup(node) {
    const id = String(node.id ?? "");
    const links = incident.get(id) || { incoming: [], outgoing: [] };
    const metadata = node.metadata && typeof node.metadata === "object"
      ? Object.entries(node.metadata)
      : [];
    const description = value(node, "description", "docstring", "summary", "explanation");
    const qualified = value(node, "qualified_name");
    const line = value(node, "line");
    const evidence = evidenceOf(node);

    return '<article class="card relation-card" id="relation-node-' + esc(id) + '">' +
      '<div class="relation-card-heading">' +
        '<span class="badge">' + esc(kindOf(node)) + '</span>' +
        '<span class="muted relation-count">' +
          links.incoming.length + ' in ? ' + links.outgoing.length + ' out</span>' +
      '</div>' +
      '<h3>' + esc(labelOf(node)) + '</h3>' +
      (pathOf(node) ? '<p class="relation-path">' + esc(pathOf(node)) +
        (line ? ':' + esc(line) : '') + '</p>' : '') +
      '<details class="relation-details">' +
        '<summary>View details and connections</summary>' +
        '<div class="relation-detail-body">' +
          (description ? '<p>' + esc(description) + '</p>' :
            '<p class="muted">No description was recorded for this item.</p>') +
          (qualified && qualified !== labelOf(node) ?
            '<p><strong>Qualified name:</strong> ' + esc(qualified) + '</p>' : '') +
          '<p><strong>Evidence:</strong> ' + esc(evidence) + '</p>' +
          (node.source_location ? '<p><strong>Source location:</strong> ' +
            esc(node.source_location) + '</p>' : '') +
          '<h4>Outgoing relationships (' + links.outgoing.length + ')</h4>' +
          relatedMarkup(links.outgoing, "outgoing") +
          '<h4>Incoming relationships (' + links.incoming.length + ')</h4>' +
          relatedMarkup(links.incoming, "incoming") +
          (metadata.length ? '<h4>Additional metadata</h4><dl>' +
            metadata.map(([key, val]) => '<dt>' + esc(key) +
              '</dt><dd>' + esc(typeof val === "object" ? JSON.stringify(val) : val) +
              '</dd>').join("") + '</dl>' : '') +
        '</div>' +
      '</details>' +
    '</article>';
  }

  function applyFilters(resetPage = true) {
    const query = String(search.value || "").trim().toLowerCase();
    const selectedKind = kindFilter.value;

    filtered = nodes.filter(node => {
      if (selectedKind && kindOf(node) !== selectedKind) return false;
      if (!query) return true;
      const haystack = [
        labelOf(node), kindOf(node), pathOf(node),
        value(node, "qualified_name", "description", "docstring")
      ].join(" ").toLowerCase();
      return haystack.includes(query);
    });

    if (resetPage) page = 0;
    render();
  }

  function render() {
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    page = Math.min(Math.max(page, 0), pages - 1);
    const start = page * pageSize;
    const visible = filtered.slice(start, start + pageSize);

    count.textContent = "Showing " + (filtered.length ? start + 1 : 0) +
      "?" + Math.min(start + pageSize, filtered.length) +
      " of " + filtered.length + " matching items ? " +
      nodes.length + " nodes ? " + edges.length + " relationships";

    grid.innerHTML = visible.length
      ? visible.map(cardMarkup).join("")
      : '<div class="card"><p>No matching items. Try a different search or filter.</p></div>';

    pagination.innerHTML = "";
    const previous = document.createElement("button");
    previous.type = "button";
    previous.textContent = "Previous";
    previous.disabled = page === 0;
    previous.addEventListener("click", () => {
      page--;
      render();
      grid.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    const status = document.createElement("span");
    status.textContent = "Page " + (page + 1) + " of " + pages;

    const next = document.createElement("button");
    next.type = "button";
    next.textContent = "Next";
    next.disabled = page >= pages - 1;
    next.addEventListener("click", () => {
      page++;
      render();
      grid.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    pagination.append(previous, status, next);
  }

  grid.addEventListener("click", event => {
    const button = event.target.closest("[data-open-node]");
    if (!button) return;

    const targetId = button.getAttribute("data-open-node");
    const target = byId.get(targetId);
    if (!target) return;

    search.value = labelOf(target);
    kindFilter.value = "";
    applyFilters();

    const card = document.getElementById("relation-node-" + CSS.escape(targetId));
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "start" });
      const details = card.querySelector("details");
      if (details) details.open = true;
    }
  });

  search.addEventListener("input", () => applyFilters());
  kindFilter.addEventListener("change", () => applyFilters());

  const reset = document.getElementById("relation-map-reset");
  if (reset) reset.addEventListener("click", () => {
    search.value = "";
    kindFilter.value = "";
    applyFilters();
  });

  applyFilters();
})();
