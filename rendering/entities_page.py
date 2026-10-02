from __future__ import annotations

from model.project import Project
from rendering.html import (
    _page_shell,
    _project_name,
    _render_entity_summary,
    _render_method_reference,
)


def render_entities_page(project: Project) -> str:
    body = (
        '<section class="subpage-header">'
        '<div class="kicker">Barkly Docs · Project entities</div>'
        "<h1>Entities</h1>"
        "<p>Classes, functions, and methods discovered in the project model.</p>"
        "</section>"
        '<section class="section">'
        "<h2>Entity overview</h2>"
        + _render_entity_summary(project)
        + "</section>"
        + '<section class="section">'
        "<h2>Method and function reference</h2>"
        '<div class="section-subtitle">Source-level signatures and documentation recovered from the shared model.</div>'
        + _render_method_reference(project)
        + "</section>"
    )
    return _page_shell(f"Entities — {_project_name(project)}", "entities", body)

__all__ = ["render_entities_page"]
