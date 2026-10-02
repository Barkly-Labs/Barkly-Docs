from __future__ import annotations

from model.project import Project
from rendering.html import (
    _collect_project_entities,
    _collect_relationships,
    _escape,
    _evidence_summary,
    _languages,
    _page_shell,
    _project_description,
    _project_name,
    _readme_path,
    _render_entity_group,
    _render_index_data_section,
    _render_json_data,
    _render_other_files,
    _render_readme,
    _render_readme_title_image,
    _render_relationship_group,
    _render_three_layer_architecture,
    _stat_card,
)


def render_index(project: Project, graph_generated: bool = True) -> str:
    description = _project_description(project)
    languages = _languages(project)
    title_image = _render_readme_title_image(project)
    hero_class = "card hero-main has-readme-image" if title_image else "card hero-main"
    project_summary = (
        f'<div class="{hero_class}">'
        + '<div class="kicker">Project documentation</div>'
        + f"<h1>{_escape(_project_name(project))}</h1>"
        + f"<p>{_escape(description)}</p>"
        + title_image
        + "</div>"
    )
    stats = (
        '<div class="card metrics">'
        + _stat_card("Files", str(len(project.files)))
        + _stat_card("Modules", str(len(project.modules)))
        + _stat_card("Classes", str(len(project.classes)))
        + _stat_card("Functions", str(len(project.functions)))
        + _stat_card("Methods", str(len(project.methods)))
        + _stat_card("Relationships", str(len(project.relationships)))
        + "</div>"
    )

    # Human-first orientation: answer the basic project questions before exposing
    # architecture and source-level detail. No project data is removed.
    overview = (
        '<section class="index-glance" aria-labelledby="at-a-glance-title">'
        '<div class="index-glance-head"><div>'
        '<h2 id="at-a-glance-title">Project at a glance</h2>'
        '<p>Start here. The essential project facts are grouped together so the page can be understood before exploring implementation detail.</p>'
        '</div></div>'
        '<div class="index-glance-grid">'
        f'<article class="index-glance-card"><h3>Languages</h3><p>{_escape(", ".join(languages) if languages else "Unknown")}</p></article>'
        f'<article class="index-glance-card"><h3>Documentation</h3><p>{_escape("README present" if _readme_path(project) else "README not discovered")}</p></article>'
        f'<article class="index-glance-card"><h3>Project root</h3><p>{_escape(project.root)}</p></article>'
        '<article class="index-glance-card"><h3>Analysis basis</h3><p>Static project evidence with declared, detected, inferred, and unknown states kept separate.</p></article>'
        '</div>'
        '<div class="index-evidence">'
        '<h3>Evidence and limits</h3>'
        '<p>Confidence stays visible without competing with the main project summary.</p>'
        + _evidence_summary(project)
        + '</div>'
        '</section>'
    )

    documentation = (
        '<details class="card documentation-card">'
        '<summary>'
        '<div class="documentation-card-heading">'
        '<div class="documentation-card-title">'
        '<h2>Documentation references</h2>'
        '<div class="section-subtitle">Read the project README and its preserved Markdown structure when you need source documentation.</div>'
        '</div>'
        '<span class="documentation-card-action" aria-hidden="true">View documentation ↓</span>'
        '</div>'
        '</summary>'
        '<div class="documentation-card-body">'
        + _render_readme(project)
        + '<div class="tile" style="margin-top:12px;"><h3>Evidence labels</h3><p>DECLARED = explicitly stated in source or project metadata; DETECTED = directly identified through static analysis; INFERRED = derived but not directly observed; UNKNOWN = not established by available evidence.</p></div>'
        + '</div></details>'
    )

    other_files_section = _render_index_data_section(
        "Other project files",
        "All discovered non-JSON files, kept separate so file browsing stays predictable.",
        "Explore files",
        _render_other_files(project),
    )
    classes_section = _render_index_data_section(
        "Classes",
        "Discovered classes in one consistent source-oriented view.",
        "Explore classes",
        _render_entity_group(_collect_project_entities(project, "classes"), "No classes were discovered."),
    )

    functions_section = _render_index_data_section(
        "Functions",
        "Discovered functions kept separate from classes and file data.",
        "Explore functions",
        _render_entity_group(_collect_project_entities(project, "functions"), "No functions were discovered."),
    )

    methods_section = _render_index_data_section(
        "Methods",
        "Methods are grouped separately so class behavior is easier to scan.",
        "Explore methods",
        _render_entity_group(_collect_project_entities(project, "methods"), "No methods were discovered."),
    )

    modules_section = _render_index_data_section(
        "Modules",
        "Detected modules and source units that organize the project.",
        "Explore modules",
        _render_entity_group(_collect_project_entities(project, "modules"), "No modules were discovered."),
    )

    endpoints_section = _render_index_data_section(
        "Endpoints",
        "Detected application entry points, with methods and source locations preserved as static-analysis evidence.",
        "Explore endpoints",
        _render_entity_group(_collect_project_entities(project, "endpoints"), "No endpoints were discovered."),
    )

    dependencies_section = _render_index_data_section(
        "Dependencies",
        "Project dependencies are separated from source entities and relationships.",
        "Explore dependencies",
        _render_entity_group(_collect_project_entities(project, "dependencies"), "No dependencies were discovered."),
    )

    relationships_section = _render_index_data_section(
        "Relationships",
        "Detected connections between project entities, kept distinct from inferred meaning.",
        "Explore relationships",
        _render_relationship_group(_collect_relationships(project)),
    )

    json_section = _render_index_data_section(
        "JSON",
        "JSON files only. Source symbols and other file types stay in their own sections.",
        "Explore JSON",
        _render_json_data(project),
    )

    body = (
        f'<section class="hero">{project_summary}{stats}</section>'
        f'{overview}'
        f'{_render_three_layer_architecture(project)}'
        f'{documentation}'
        '<div class="index-deep-label">Reference layer</div>'
        '<h2 class="index-deep-title">Deeper project detail</h2>'
        '<p class="index-deep-copy">The overview stays calm by default. Classes, functions, methods, modules, endpoints, dependencies, relationships, JSON, and files are separated into predictable sections so each type of project data has one clear place.</p>'
        f'<div class="index-human-flow">{classes_section}{functions_section}{methods_section}{modules_section}{endpoints_section}{dependencies_section}{relationships_section}{json_section}{other_files_section}</div>'
    )
    return _page_shell(
        f"{_project_name(project)} — Barkly Docs",
        "index",
        body,
    )

__all__ = ["render_index"]
