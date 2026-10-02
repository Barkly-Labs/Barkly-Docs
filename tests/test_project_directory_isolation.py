
from __future__ import annotations

import functools
import threading
import urllib.request
from pathlib import Path

from cli.main import build_preview_server, ensure_website_generated
from model.project import Project


def _project(root: Path, name: str) -> Project:
    root.mkdir(parents=True, exist_ok=True)
    return Project(name=name, root=str(root.resolve()))


def test_relative_output_is_canonicalized_from_different_working_directory(tmp_path, monkeypatch):
    launch_dir = tmp_path / "launch"
    launch_dir.mkdir()
    project_dir = tmp_path / "projects" / "alpha"
    project = _project(project_dir, "Alpha")
    (project_dir / "README.md").write_text("# Alpha\n\nALPHA-FRESH", encoding="utf-8")

    monkeypatch.chdir(launch_dir)
    output = ensure_website_generated(project, Path("relative-output"))

    assert output == (launch_dir / "relative-output").resolve()
    assert (output / "index.html").is_file()
    assert "ALPHA-FRESH" in (output / "index.html").read_text(encoding="utf-8")


def test_two_projects_do_not_reuse_previous_project_html(tmp_path):
    output = tmp_path / "site"
    a = _project(tmp_path / "a", "Project A")
    b = _project(tmp_path / "b", "Project B")
    (Path(a.root) / "README.md").write_text("# Project A\n\nONLY-A-CONTENT", encoding="utf-8")
    (Path(b.root) / "README.md").write_text("# Project B\n\nONLY-B-CONTENT", encoding="utf-8")

    ensure_website_generated(a, output)
    first = (output / "index.html").read_text(encoding="utf-8")
    ensure_website_generated(b, output)
    second = (output / "index.html").read_text(encoding="utf-8")

    assert "ONLY-A-CONTENT" in first
    assert "ONLY-B-CONTENT" in second
    assert "ONLY-A-CONTENT" not in second


def test_server_root_is_frozen_to_generated_output(tmp_path, monkeypatch):
    launch_dir = tmp_path / "launch"
    other_dir = tmp_path / "other"
    launch_dir.mkdir()
    other_dir.mkdir()
    output = launch_dir / "site"
    output.mkdir()
    (output / "index.html").write_text("EXPECTED-SERVED-PROJECT", encoding="utf-8")
    wrong = other_dir / "site"
    wrong.mkdir()
    (wrong / "index.html").write_text("STALE-WRONG-PROJECT", encoding="utf-8")

    monkeypatch.chdir(launch_dir)
    server = build_preview_server(Path("site"), host="127.0.0.1", port=0)
    try:
        # This is the regression condition: cwd changes after server construction.
        monkeypatch.chdir(other_dir)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address[:2]
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=5) as response:
            body = response.read().decode("utf-8")
        assert "EXPECTED-SERVED-PROJECT" in body
        assert "STALE-WRONG-PROJECT" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_regeneration_serves_fresh_readme_content(tmp_path):
    project_dir = tmp_path / "fresh"
    project = _project(project_dir, "Fresh")
    readme = project_dir / "README.md"
    output = tmp_path / "site"

    readme.write_text("# Fresh\n\nVERSION-ONE", encoding="utf-8")
    ensure_website_generated(project, output)
    assert "VERSION-ONE" in (output / "index.html").read_text(encoding="utf-8")

    readme.write_text("# Fresh\n\nVERSION-TWO", encoding="utf-8")
    ensure_website_generated(project, output)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "VERSION-TWO" in html
    assert "VERSION-ONE" not in html


def test_existing_pages_sections_assets_and_relationship_map_remain(tmp_path):
    project_dir = tmp_path / "preserve"
    project = _project(project_dir, "Preserve")
    (project_dir / "README.md").write_text("# Preserve\n\nREADME-CONTENT", encoding="utf-8")
    output = ensure_website_generated(project, tmp_path / "site")

    index = (output / "index.html").read_text(encoding="utf-8")
    relation_map = (output / "relation-map.html").read_text(encoding="utf-8")
    for section in (
        "Classes", "Functions", "Methods", "Modules", "Dependencies",
        "Relationships", "JSON", "Other project files",
    ):
        assert section in index

    assert "README-CONTENT" in index
    assert (output / "assets" / "site.css").is_file()
    assert (output / "assets" / "relation-map.js").is_file()
    assert "relationship" in relation_map.lower()
