from pathlib import Path

from analysis.discovery import ProjectDiscovery
from readers.python import PythonReader
from readers.python_dependencies import PythonDependencyReader
from rendering.html import render_project_website


def test_requirements_manifest_survives_real_discovery_model_and_html(tmp_path: Path):
    root = tmp_path / "sample"
    root.mkdir()
    manifest = root / "requirements-app.txt"
    manifest.write_text("requests>=2.32\nrich~=13.9\n", encoding="utf-8")
    (root / "app.py").write_text("import requests\n", encoding="utf-8")

    result = ProjectDiscovery([PythonDependencyReader(), PythonReader()]).analyze(root)

    assert manifest in result.processed_files
    found = {dep.name: dep for dep in result.project.dependencies}
    assert found["requests"].version == ">=2.32"
    assert found["rich"].version == "~=13.9"
    assert Path(found["requests"].source) == manifest

    output = tmp_path / "site"
    render_project_website(result.project, output)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Dependencies" in html
    assert "requests" in html
    assert "rich" in html
    assert "&gt;=2.32" in html
    assert "~=13.9" in html
    assert "requirements-app.txt" in html
