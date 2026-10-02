
from __future__ import annotations

import threading
import urllib.request
from pathlib import Path

import pytest

from cli.main import build_preview_server, ensure_website_generated
from model.project import Project
pytestmark = pytest.mark.slow



def _make_project(root: Path, name: str, marker: str) -> Project:
    root.mkdir(parents=True)
    (root / "README.md").write_text(f"# {name}\n\n{marker}\n", encoding="utf-8")
    return Project(name=name, root=str(root.resolve()))


def _start(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def _get(server) -> str:
    host, port = server.server_address[:2]
    with urllib.request.urlopen(f"http://{host}:{port}/", timeout=5) as response:
        return response.read().decode("utf-8")


def test_old_project_server_cannot_capture_new_project_preview(tmp_path):
    a = _make_project(tmp_path / "A", "PROJECT-A", "README-A-ONLY")
    b = _make_project(tmp_path / "B", "PROJECT-B", "README-B-ONLY")
    out_a = ensure_website_generated(a, Path(a.root) / ".barkly-docs-site")
    out_b = ensure_website_generated(b, Path(b.root) / ".barkly-docs-site")

    server_a = build_preview_server(out_a, host="127.0.0.1", port=0)
    _start(server_a)
    occupied_port = int(server_a.server_address[1])

    # This models a second Barkly launch while the first preview still owns
    # the preferred/default address.
    server_b = build_preview_server(
        out_b,
        host="127.0.0.1",
        port=occupied_port,
        allow_port_fallback=True,
    )
    _start(server_b)
    try:
        response_a = _get(server_a)
        response_b = _get(server_b)
        assert "PROJECT-A" in response_a
        assert "PROJECT-B" not in response_a
        assert "PROJECT-B" in response_b
        assert "PROJECT-A" not in response_b
        assert server_a.server_address[1] != server_b.server_address[1]
        assert server_b.document_root == out_b.resolve()
        assert server_b.last_resolved_file == (out_b / "index.html").resolve()
    finally:
        server_a.shutdown(); server_a.server_close()
        server_b.shutdown(); server_b.server_close()


def test_explicit_port_collision_still_errors(tmp_path):
    a = _make_project(tmp_path / "A", "A", "A-ONLY")
    out = ensure_website_generated(a, tmp_path / "site")
    first = build_preview_server(out, host="127.0.0.1", port=0)
    _start(first)
    port = int(first.server_address[1])
    try:
        with pytest.raises(RuntimeError):
            build_preview_server(
                out, host="127.0.0.1", port=port, allow_port_fallback=False
            )
    finally:
        first.shutdown(); first.server_close()


def test_regeneration_changes_content_actually_served(tmp_path):
    b = _make_project(tmp_path / "B", "PROJECT-B", "B-VERSION-ONE")
    out = ensure_website_generated(b, Path(b.root) / ".barkly-docs-site")
    server = build_preview_server(out, host="127.0.0.1", port=0)
    _start(server)
    try:
        assert "B-VERSION-ONE" in _get(server)
        (Path(b.root) / "README.md").write_text(
            "# PROJECT-B\n\nB-VERSION-TWO\n", encoding="utf-8"
        )
        ensure_website_generated(b, out)
        response = _get(server)
        assert "B-VERSION-TWO" in response
        assert "B-VERSION-ONE" not in response
        assert server.last_resolved_file == (out / "index.html").resolve()
    finally:
        server.shutdown(); server.server_close()


def test_different_working_directory_does_not_change_server_root(tmp_path, monkeypatch):
    launch = tmp_path / "launch"; other = tmp_path / "other"
    launch.mkdir(); other.mkdir()
    project = _make_project(tmp_path / "P", "PROJECT-P", "P-ONLY")
    monkeypatch.chdir(launch)
    out = ensure_website_generated(project, Path("generated"))
    server = build_preview_server(out, host="127.0.0.1", port=0)
    _start(server)
    try:
        monkeypatch.chdir(other)
        assert "PROJECT-P" in _get(server)
        assert server.document_root == (launch / "generated").resolve()
        assert server.last_resolved_file == (launch / "generated" / "index.html").resolve()
    finally:
        server.shutdown(); server.server_close()


def test_existing_sections_readme_and_spider_assets_remain(tmp_path):
    project = _make_project(tmp_path / "P", "PRESERVE", "README-PRESERVE")
    out = ensure_website_generated(project, tmp_path / "site")
    index = (out / "index.html").read_text(encoding="utf-8")
    for section in (
        "Classes", "Functions", "Methods", "Modules", "Dependencies",
        "Relationships", "JSON", "Other project files",
    ):
        assert section in index
    assert "README-PRESERVE" in index
    assert (out / "relation-map.html").is_file()
    assert (out / "assets" / "relation-map.js").is_file()
