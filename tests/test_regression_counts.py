from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.discovery import ProjectDiscovery
from model.project import Project
from rendering.html import render_project_website
from readers.java import JavaReader
from readers.python import PythonReader


def _build_mixed_fixture(root: Path) -> None:
    package_dir = root / "pkg"
    package_dir.mkdir(parents=True)

    (package_dir / "math_ops.py").write_text(
        "def square(value):\n"
        "    return value * value\n\n\n"
        "class Counter:\n"
        "    def add(self, left, right):\n"
        "        return left + right\n\n"
        "    def reset(self):\n"
        "        return 0\n",
        encoding="utf-8",
    )

    (package_dir / "TypeCounter.java").write_text(
        "public class TypeCounter {\n"
        "    public TypeCounter() {}\n"
        "    public int add(int left, int right) {\n"
        "        return left + right;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )


def test_fixture_counts_are_correct_per_file_and_project_wide(tmp_path):
    _build_mixed_fixture(tmp_path)

    python_project = Project(name="python", root=str(tmp_path))
    python_path = tmp_path / "pkg" / "math_ops.py"
    PythonReader().read(python_path, python_project)
    assert python_project.summary()["files"] == 1
    assert python_project.summary()["functions"] == 1
    assert python_project.summary()["classes"] == 1
    assert python_project.summary()["methods"] == 2

    java_project = Project(name="java", root=str(tmp_path))
    java_path = tmp_path / "pkg" / "TypeCounter.java"
    JavaReader().read(java_path, java_project)
    assert java_project.summary()["files"] == 1
    assert java_project.summary()["classes"] == 1
    assert java_project.summary()["methods"] == 2
    assert {method.name for method in java_project.methods} == {"TypeCounter", "add"}

    aggregate = Project(name="aggregate", root=str(tmp_path))
    PythonReader().read(python_path, aggregate)
    JavaReader().read(java_path, aggregate)
    assert aggregate.summary()["files"] == 2
    assert aggregate.summary()["classes"] == 2
    assert aggregate.summary()["functions"] == 1
    assert aggregate.summary()["methods"] == 4


def test_duplicate_file_processing_does_not_inflate_totals(tmp_path):
    _build_mixed_fixture(tmp_path)
    path = tmp_path / "pkg" / "math_ops.py"

    project = Project(name="duplicate-check", root=str(tmp_path))
    reader = PythonReader()
    reader.read(path, project)
    reader.read(path, project)

    assert project.summary()["files"] == 1
    assert project.summary()["functions"] == 1
    assert project.summary()["classes"] == 1
    assert project.summary()["methods"] == 2


def test_html_summary_matches_project_model(tmp_path):
    _build_mixed_fixture(tmp_path)
    discovery = ProjectDiscovery([PythonReader(), JavaReader()])
    result = discovery.analyze(tmp_path, name="fixture")

    render_project_website(result.project, tmp_path / "site")
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    summary = result.project.summary()

    assert f">{summary['files']}" in html
    assert f">{summary['classes']}" in html
    assert f">{summary['functions']}" in html
    assert f">{summary['methods']}" in html
    assert f">{summary['relationships']}" in html


def test_parallel_and_sequential_analysis_are_equivalent(tmp_path):
    _build_mixed_fixture(tmp_path)
    discovery = ProjectDiscovery([PythonReader(), JavaReader()])

    sequential = discovery.analyze(tmp_path, name="fixture-seq", parallel=False)
    parallel = discovery.analyze(tmp_path, name="fixture-parallel", parallel=True, workers=2)

    assert [path.name for path in sequential.processed_files] == [path.name for path in parallel.processed_files]
    assert sequential.project.summary() == parallel.project.summary()
    assert len(sequential.project.relationships) == len(parallel.project.relationships)
