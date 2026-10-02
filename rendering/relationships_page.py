from __future__ import annotations

import hashlib
import html
import json

from model.project import Project
from rendering.html import _escape, _page_shell, _project_name


def _relationship_id(relationship, index: int) -> str:
    identity = "|".join(
        str(value or "")
        for value in (
            relationship.source,
            relationship.target,
            relationship.kind,
            relationship.source_file,
            relationship.source_location,
            index,
        )
    )
    return "relationship-" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:14]


def _location_text(relationship) -> str:
    location = relationship.source_location or {}
    if not isinstance(location, dict):
        return str(location)
    line = location.get("line") or location.get("line_start") or location.get("start_line")
    end = location.get("line_end") or location.get("end_line")
    column = location.get("column") or location.get("column_start")
    parts = []
    if line:
        value = str(line)
        if end and str(end) != value:
            value += f"–{end}"
        parts.append("line " + value)
    if column:
        parts.append("column " + str(column))
    return ", ".join(parts)


def _render_metadata(metadata: dict) -> str:
    if not metadata:
        return ""
    rows = []
    for key, value in sorted(metadata.items(), key=lambda item: str(item[0]).casefold()):
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (dict, list, tuple)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        rows.append(
            '<div><dt>{}</dt><dd><code>{}</code></dd></div>'.format(
                _escape(str(key).replace("_", " ").title()), _escape(str(value))
            )
        )
    if not rows:
        return ""
    return (
        '<div class="relationship-metadata">'
        '<div class="entity-detail-label">Recorded metadata</div>'
        '<dl class="entity-expanded-facts">' + "".join(rows) + "</dl></div>"
    )


def _render_relationship_card(relationship, index: int) -> str:
    relation_id = _relationship_id(relationship, index)
    panel_id = relation_id + "-details"
    source = str(relationship.source or "")
    target = str(relationship.target or "")
    kind = str(relationship.kind or "related")
    source_file = str(relationship.source_file or "")
    evidence = str(relationship.evidence or "UNKNOWN").upper()
    if evidence not in {"DECLARED", "DETECTED", "INFERRED", "UNKNOWN"}:
        evidence = "UNKNOWN"
    location = _location_text(relationship)
    metadata = dict(relationship.metadata or {})

    search_values = [source, target, kind, source_file, evidence, location]
    search_values.extend(str(key) for key in metadata)
    search_values.extend(str(value) for value in metadata.values())
    search_text = " ".join(search_values).casefold()

    facts = [
        f'<div><dt>Type</dt><dd><code>{_escape(kind)}</code></dd></div>',
        f'<div><dt>Evidence</dt><dd><span class="badge {evidence.lower()}">{_escape(evidence)}</span></dd></div>',
    ]
    if source_file:
        facts.append(f'<div><dt>Source file</dt><dd><code>{_escape(source_file)}</code></dd></div>')
    if location:
        facts.append(f'<div><dt>Location</dt><dd><code>{_escape(location)}</code></dd></div>')

    return (
        f'<article class="relationship-explorer-item entity-explorer-item entity-item" id="{relation_id}" '
        f'data-relationship-search="{html.escape(search_text, quote=True)}" '
        f'data-relationship-kind="{html.escape(kind.casefold(), quote=True)}">'
        '<div class="entity-explorer-row">'
        '<div class="entity-explorer-primary relationship-primary">'
        f'<strong class="entity-row-name"><code>{_escape(source)}</code> → <code>{_escape(target)}</code></strong>'
        f'<span class="entity-type-tag">{_escape(kind)}</span>'
        '</div>'
        '<div class="entity-explorer-meta">'
        + (f'<span>{_escape(source_file)}</span>' if source_file else '<span class="muted">Source file unavailable</span>')
        + f'<span>{_escape(evidence)}</span>'
        '</div>'
        f'<button class="entity-disclosure-button relationship-disclosure-button" type="button" aria-expanded="false" '
        f'aria-controls="{panel_id}">Expand <span aria-hidden="true">↓</span></button>'
        '</div>'
        f'<div class="entity-expanded-view" id="{panel_id}" hidden>'
        '<div class="entity-detail-label">Relationship</div>'
        '<p class="relationship-direction"><code>' + _escape(source) + '</code> '
        '<span aria-label="relates to">→</span> <code>' + _escape(target) + '</code></p>'
        '<dl class="entity-expanded-facts">' + "".join(facts) + '</dl>'
        + _render_metadata(metadata)
        + '</div></article>'
    )


def _render_relationship_explorer(project: Project) -> str:
    relationships = list(project.relationships or [])
    cards = "".join(_render_relationship_card(item, index) for index, item in enumerate(relationships))
    total = len(relationships)
    kinds = sorted({str(item.kind or "related") for item in relationships}, key=str.casefold)
    options = "".join(
        f'<option value="{html.escape(kind.casefold(), quote=True)}">{_escape(kind)}</option>'
        for kind in kinds
    )
    if not cards:
        cards = '<div class="empty-state relationship-explorer-initial-empty">No relationships were discovered in the shared relationship model.</div>'
    return (
        '<div class="entity-explorer relationship-explorer" data-relationship-explorer>'
        '<div class="entity-explorer-tools">'
        '<label for="relationship-search">Search project relationships</label>'
        '<div class="relationship-search-controls">'
        '<div class="entity-search-row">'
        '<input id="relationship-search" type="search" autocomplete="off" '
        'placeholder="Search source, target, type, path, or metadata" '
        'aria-describedby="relationship-search-status">'
        '<button type="button" class="entity-search-clear relationship-search-clear" aria-label="Clear relationship search" disabled>Clear</button>'
        '</div>'
        '<div class="relationship-filter-row">'
        '<label for="relationship-kind-filter">Relationship type</label>'
        '<select id="relationship-kind-filter"><option value="">All relationship types</option>' + options + '</select>'
        '</div></div>'
        f'<p class="entity-search-status relationship-search-status" id="relationship-search-status" role="status" aria-live="polite"><strong>{total}</strong> relationships</p>'
        '</div>'
        '<div class="entity-explorer-list relationship-explorer-list">' + cards + '</div>'
        '<div class="empty-state entity-search-empty relationship-search-empty" hidden>No relationships match the current search and type filter.</div>'
        '</div>'
    )


RELATIONSHIP_EXPLORER_SCRIPT = r"""
<script>
(() => {
  const explorer = document.querySelector('[data-relationship-explorer]');
  if (!explorer) return;
  const input = explorer.querySelector('#relationship-search');
  const kind = explorer.querySelector('#relationship-kind-filter');
  const clear = explorer.querySelector('.relationship-search-clear');
  const status = explorer.querySelector('.relationship-search-status');
  const empty = explorer.querySelector('.relationship-search-empty');
  const items = Array.from(explorer.querySelectorAll('.relationship-explorer-item'));

  const escapeHtml = value => value.replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const update = () => {
    const query = input.value.trim().toLocaleLowerCase();
    const selectedKind = kind.value.trim().toLocaleLowerCase();
    let matches = 0;
    for (const item of items) {
      const queryMatches = !query || (item.dataset.relationshipSearch || '').includes(query);
      const kindMatches = !selectedKind || (item.dataset.relationshipKind || '') === selectedKind;
      const visible = queryMatches && kindMatches;
      item.hidden = !visible;
      if (visible) matches += 1;
    }
    clear.disabled = !input.value && !kind.value;
    empty.hidden = matches !== 0 || items.length === 0;
    const context = [];
    if (query) context.push(`matching “${escapeHtml(input.value.trim())}”`);
    if (selectedKind) context.push(`of type “${escapeHtml(kind.options[kind.selectedIndex].text)}”`);
    status.innerHTML = `<strong>${matches}</strong> ${matches === 1 ? 'relationship' : 'relationships'}${context.length ? ' ' + context.join(' ') : ''}`;
  };

  input.addEventListener('input', update);
  kind.addEventListener('change', update);
  clear.addEventListener('click', () => {
    input.value = '';
    kind.value = '';
    update();
    input.focus();
  });

  explorer.addEventListener('click', event => {
    const button = event.target.closest('.relationship-disclosure-button');
    if (!button) return;
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    if (!panel) return;
    const expanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!expanded));
    panel.hidden = expanded;
    button.firstChild.nodeValue = expanded ? 'Expand ' : 'Hide ';
    const arrow = button.querySelector('[aria-hidden="true"]');
    if (arrow) arrow.textContent = expanded ? '↓' : '↑';
  });

  update();
})();
</script>
"""


def render_relationships_page(project: Project) -> str:
    body = (
        '<section class="subpage-header">'
        '<div class="kicker">Barkly Docs · Project relationships</div>'
        '<h1>Relationships</h1>'
        '<p>Search detected connections, then expand a relationship to inspect its direction, evidence, source, and recorded metadata.</p>'
        '</section>'
        '<section class="section relationship-explorer-section">'
        '<h2>Relationship explorer</h2>'
        '<div class="section-subtitle">Relationship types, evidence, and unresolved information reflect the shared project model; nothing is inferred by this page.</div>'
        + _render_relationship_explorer(project)
        + '</section>'
        '<section class="section">'
        '<h2>Relationship map</h2>'
        '<div class="section-subtitle">Explore the same project connections visually without replacing the searchable inventory.</div>'
        '<a class="entity-search-clear relationship-map-link" href="relation-map.html">Open relationship map</a>'
        '</section>'
        + RELATIONSHIP_EXPLORER_SCRIPT
    )
    return _page_shell(f"Relationships — {_project_name(project)}", "relationships", body)


__all__ = ["render_relationships_page"]
