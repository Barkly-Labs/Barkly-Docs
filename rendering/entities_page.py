from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from model.project import Project
from rendering.html import _escape, _page_shell, _project_name


def _value(item, *names):
    for name in names:
        candidate = getattr(item, name, None)
        if candidate is not None and candidate != "":
            return candidate
    return None


def _entity_kind(item) -> str:
    raw = str(_value(item, "kind", "type") or item.__class__.__name__)
    return raw.removesuffix("Node").replace("_", " ").strip() or "Entity"



def _entity_name(item) -> str:
    name = _value(item, "name", "label")
    if name:
        return str(name)
    if item.__class__.__name__ == "EndpointNode":
        return f"{getattr(item, 'method', 'HTTP')} {getattr(item, 'path', '')}".strip()
    return "Unnamed"

def _entity_signature(item) -> str:
    name = _entity_name(item)
    parameters = _value(item, "parameters", "params", "arguments")
    if isinstance(parameters, (list, tuple)):
        parameters = ", ".join(str(value) for value in parameters)
    signature = f"{name}({parameters})" if parameters else name
    return_type = _value(item, "return_type", "returns")
    return f"{signature} -> {return_type}" if return_type else signature


def _entity_qualified_name(item) -> str:
    explicit = _value(item, "qualified_name", "fully_qualified_name", "fqn", "namespace")
    if not explicit:
        metadata = getattr(item, "metadata", {}) or {}
        explicit = (
            metadata.get("qualified_name")
            or metadata.get("fully_qualified_name")
            or metadata.get("fqn")
            or metadata.get("namespace")
        )
    if explicit:
        return str(explicit)
    class_name = _value(item, "class_name", "owner", "parent_class")
    name = _entity_name(item)
    return f"{class_name}.{name}" if class_name else name


def _stable_entity_id(item, index: int) -> str:
    identity = "|".join(
        str(part or "")
        for part in (
            _entity_kind(item),
            _value(item, "path", "file_path", "source_file"),
            _entity_qualified_name(item),
            _value(item, "line_start", "start_line", "line", "lineno"),
            index,
        )
    )
    return "entity-" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:14]


def _source_excerpt(item, max_lines: int = 14) -> str:
    raw_path = str(_value(item, "path", "file_path", "source_file") or "")
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
    raw_start = _value(item, "line_start", "start_line", "line", "lineno") or 1
    raw_end = _value(item, "line_end", "end_line")
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


def _members(item) -> str:
    groups = []
    for label, attr_names in (
        ("Methods / functions", ("methods", "functions", "members")),
        ("Properties / attributes", ("properties", "attributes")),
        ("Constants / values", ("constants",)),
    ):
        children = _value(item, *attr_names)
        if not children:
            continue
        if isinstance(children, str):
            children = [part.strip() for part in children.split(",") if part.strip()]
        try:
            children = list(children)
        except TypeError:
            children = [children]
        rows = []
        for child in children:
            if isinstance(child, str):
                child_name, child_doc = child, ""
            else:
                child_name = _entity_signature(child)
                child_doc = str(_value(child, "documentation", "docstring", "description") or "")
            rows.append(
                '<div class="entity-child-row">'
                f'<code>{_escape(child_name)}</code>'
                + (f'<span>{_escape(child_doc[:180])}</span>' if child_doc else "")
                + '</div>'
            )
        if rows:
            groups.append(
                '<div class="entity-members">'
                f'<div class="entity-detail-label">{_escape(label)}</div>'
                + "".join(rows)
                + '</div>'
            )
    return "".join(groups)


def _related_relationships(project: Project, item) -> str:
    names = {
        str(value)
        for value in (
            _value(item, "name"),
            _entity_qualified_name(item),
        )
        if value
    }
    matches = []
    for relationship in project.relationships:
        source = str(getattr(relationship, "source", "") or "")
        target = str(getattr(relationship, "target", "") or "")
        if source not in names and target not in names:
            continue
        evidence = str(getattr(relationship, "evidence", "UNKNOWN") or "UNKNOWN")
        matches.append(
            '<li>'
            f'<code>{_escape(source)}</code> '
            f'<span class="entity-relation-kind">{_escape(str(getattr(relationship, "kind", "related")))}</span> '
            f'<code>{_escape(target)}</code> '
            f'<span class="badge {evidence.lower()}">{_escape(evidence)}</span>'
            '</li>'
        )
    if not matches:
        return '<p class="muted entity-no-relationships">No relationships recorded for this entity.</p>'
    return (
        '<div class="entity-related">'
        '<div class="entity-detail-label">Relationships</div>'
        '<ul>' + "".join(matches[:30]) + '</ul>'
        + (f'<p class="muted">Showing 30 of {len(matches)} relationships.</p>' if len(matches) > 30 else "")
        + '</div>'
    )


def _collect_entities(project: Project):
    collections = (
        "classes", "functions", "methods", "modules", "interfaces", "variables",
        "components", "routes", "endpoints", "dependencies", "configurations",
        "tests", "documentation",
    )
    entities = []
    seen = set()
    for collection in collections:
        for item in getattr(project, collection, []) or []:
            key = (
                collection,
                str(_value(item, "path", "file_path", "source_file") or ""),
                _entity_qualified_name(item),
                str(_value(item, "line_start", "start_line", "line", "lineno") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            entities.append(item)
    return sorted(
        entities,
        key=lambda item: (
            str(_value(item, "path", "file_path", "source_file") or "").lower(),
            _entity_kind(item).lower(),
            _entity_qualified_name(item).lower(),
        ),
    )


def _render_entity_card(project: Project, item, index: int) -> str:
    entity_id = _stable_entity_id(item, index)
    panel_id = entity_id + "-details"
    name = _entity_name(item)
    kind = _entity_kind(item)
    path = str(_value(item, "path", "file_path", "source_file") or "")
    language = str(_value(item, "language") or "Unknown")
    qualified_name = _entity_qualified_name(item)
    documentation = str(_value(item, "documentation", "docstring", "description", "summary") or "")
    signature = _entity_signature(item)
    metadata = getattr(item, "metadata", {}) or {}
    line = _value(item, "line_start", "start_line", "line", "lineno") or metadata.get("line")
    end_line = _value(item, "line_end", "end_line") or metadata.get("line_end")
    module = str(_value(item, "module", "namespace", "package") or metadata.get("module") or "")
    evidence = str(_value(item, "evidence") or metadata.get("evidence") or "DETECTED").upper()
    if evidence not in {"DECLARED", "DETECTED", "INFERRED", "UNKNOWN"}:
        evidence = "UNKNOWN"

    location = path
    if line:
        location += f":{line}"
        if end_line and str(end_line) != str(line):
            location += f"–{end_line}"

    facts = [
        f'<div><dt>Type</dt><dd>{_escape(kind)}</dd></div>',
        f'<div><dt>Evidence</dt><dd><span class="badge {evidence.lower()}">{_escape(evidence)}</span></dd></div>',
    ]
    if signature and signature != name:
        facts.append(f'<div><dt>Signature</dt><dd><code>{_escape(signature)}</code></dd></div>')
    if qualified_name != name:
        facts.append(f'<div><dt>Qualified name</dt><dd><code>{_escape(qualified_name)}</code></dd></div>')
    if module:
        facts.append(f'<div><dt>Module</dt><dd><code>{_escape(module)}</code></dd></div>')
    if location:
        facts.append(f'<div><dt>Source</dt><dd><code>{_escape(location)}</code></dd></div>')

    search_parts = [name, kind, qualified_name, path, module, documentation, signature, language]
    search_text = " ".join(part for part in search_parts if part).casefold()

    return (
        f'<article class="entity-explorer-item entity-item" id="{entity_id}" '
        f'data-entity-search="{html.escape(search_text, quote=True)}" '
        f'data-entity-kind="{html.escape(kind.casefold(), quote=True)}">'
        '<div class="entity-explorer-row">'
        '<div class="entity-explorer-primary">'
        f'<strong class="entity-row-name">{_escape(name)}</strong>'
        f'<span class="entity-type-tag">{_escape(kind)}</span>'
        '</div>'
        '<div class="entity-explorer-meta">'
        + (f'<span>{_escape(path)}</span>' if path else '<span class="muted">Source path unavailable</span>')
        + f'<span>{_escape(language)}</span>'
        '</div>'
        f'<button class="entity-disclosure-button" type="button" aria-expanded="false" '
        f'aria-controls="{panel_id}">Expand <span aria-hidden="true">↓</span></button>'
        '</div>'
        f'<div class="entity-expanded-view" id="{panel_id}" hidden>'
        '<div class="entity-detail-label">Purpose</div>'
        + (f'<p class="entity-expanded-description">{_escape(documentation)}</p>' if documentation
           else '<p class="muted">No description available yet.</p>')
        + '<dl class="entity-expanded-facts">' + "".join(facts) + '</dl>'
        + _members(item)
        + _related_relationships(project, item)
        + _source_excerpt(item)
        + '</div>'
        '</article>'
    )


def _render_entity_explorer(project: Project) -> str:
    entities = _collect_entities(project)
    cards = "".join(_render_entity_card(project, item, index) for index, item in enumerate(entities))
    total = len(entities)
    if not cards:
        cards = '<div class="empty-state entity-explorer-initial-empty">No project entities were detected.</div>'
    return (
        '<div class="entity-explorer" data-entity-explorer>'
        '<div class="entity-explorer-tools">'
        '<label for="entity-search">Search project entities</label>'
        '<div class="entity-search-row">'
        '<input id="entity-search" type="search" autocomplete="off" '
        'placeholder="Search name, type, path, signature, or description" '
        'aria-describedby="entity-search-status">'
        '<button type="button" class="entity-search-clear" aria-label="Clear entity search" disabled>Clear</button>'
        '</div>'
        f'<p class="entity-search-status" id="entity-search-status" role="status" aria-live="polite"><strong>{total}</strong> entities</p>'
        '</div>'
        '<div class="entity-explorer-list">' + cards + '</div>'
        '<div class="empty-state entity-search-empty" hidden>No entities match this search. Try a name, type, file path, or description.</div>'
        '</div>'
    )


ENTITY_EXPLORER_SCRIPT = r"""
<script>
(() => {
  const explorer = document.querySelector('[data-entity-explorer]');
  if (!explorer) return;
  const input = explorer.querySelector('#entity-search');
  const clear = explorer.querySelector('.entity-search-clear');
  const status = explorer.querySelector('.entity-search-status');
  const empty = explorer.querySelector('.entity-search-empty');
  const items = Array.from(explorer.querySelectorAll('.entity-explorer-item'));

  const update = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let matches = 0;
    for (const item of items) {
      const visible = !query || (item.dataset.entitySearch || '').includes(query);
      item.hidden = !visible;
      if (visible) matches += 1;
    }
    clear.disabled = !input.value;
    empty.hidden = matches !== 0 || items.length === 0;
    status.innerHTML = `<strong>${matches}</strong> ${matches === 1 ? 'entity' : 'entities'}${query ? ` matching “${escapeHtml(input.value.trim())}”` : ''}`;
  };

  const escapeHtml = value => value.replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  input.addEventListener('input', update);
  clear.addEventListener('click', () => {
    input.value = '';
    update();
    input.focus();
  });

  explorer.addEventListener('click', event => {
    const button = event.target.closest('.entity-disclosure-button');
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


def render_entities_page(project: Project) -> str:
    body = (
        '<section class="subpage-header card">'
        '<div class="kicker">Barkly Docs · Project entities</div>'
        '<h1>Entities</h1>'
        '<p>Search the project model, then expand an entity to understand its purpose, source, members, and recorded relationships.</p>'
        '</section>'
        '<section class="section entity-explorer-section card">'
        '<h2>Entity explorer</h2>'
        '<div class="section-subtitle">Descriptions and relationships reflect the documentation and evidence already present in the shared project model.</div>'
        + _render_entity_explorer(project)
        + '</section>'
        + ENTITY_EXPLORER_SCRIPT
    )
    return _page_shell(f"Entities — {_project_name(project)}", "entities", body)


__all__ = ["render_entities_page"]
