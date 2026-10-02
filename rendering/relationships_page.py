from __future__ import annotations

from model.project import Project
from rendering.html import (
    _page_shell,
    _project_name,
    _render_relationships,
)


def render_relationships_page(project: Project) -> str:
    body = (
        '<section class="subpage-header">'
        '<div class="kicker">Barkly Docs · Project relationships</div>'
        "<h1>Relationships</h1>"
        "<p>Evidence-labeled relationships between project entities.</p>"
        "</section>"
        '<section class="section">'
        "<h2>Relationship inventory</h2>"
        + _render_relationships(project)
        + "</section>"
    )
    return _page_shell(f"Relationships — {_project_name(project)}", "relationships", body)

__all__ = ["render_relationships_page"]
