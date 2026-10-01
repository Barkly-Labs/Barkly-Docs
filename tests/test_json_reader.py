from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.discovery import ProjectDiscovery
from model.project import Project
from rendering.html import render_project_website
from readers.java import JavaReader
from readers.json import JSONReader
from readers.python import PythonReader


def test_json_reader_extracts_nested_objects_arrays_and_primitives(tmp_path):
    path = tmp_path / "settings.json"
    payload = {
        "name": "Barkly",
        "enabled": True,
        "count": 3,
        "empty_object": {},
        "items": [
            {"id": 1, "label": "alpha"},
            {"id": 2, "empty_array": []},
        ],
        "note": None,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    project = Project(name="demo", root=str(tmp_path))
    result = JSONReader().read(path, project)

    assert result.success is True
    assert not result.errors
    assert project.summary()["files"] == 1
    assert {node.metadata.get("path") for node in project.data} >= {"$", "$.name", "$.enabled", "$.count", "$.items[0].id", "$.items[1].empty_array"}
    assert any(node.metadata.get("path") == "$.name" and node.value_type == "string" for node in project.data)
    assert any(node.metadata.get("path") == "$.enabled" and node.value_type == "boolean" for node in project.data)
    assert any(node.metadata.get("path") == "$.note" and node.value_type == "null" for node in project.data)
    assert any(node.metadata.get("path") == "$.empty_object" and node.kind == "object" for node in project.data)
    assert any(node.metadata.get("path") == "$.items" and node.kind == "array" for node in project.data)


def test_json_reader_handles_empty_objects_arrays_and_unicode(tmp_path):
    path = tmp_path / "unicode.json"
    payload = {
        "empty_object": {},
        "empty_array": [],
        "greeting": "Héllo 🌍",
        "nested": {"emoji": "🙂", "value": "naïve"},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    project = Project(name="demo", root=str(tmp_path))
    result = JSONReader().read(path, project)

    assert result.success is True
    assert any(node.metadata.get("path") == "$.empty_object" and node.keys == [] for node in project.data)
    assert any(node.metadata.get("path") == "$.empty_array" and node.keys == [] for node in project.data)
    assert any(node.metadata.get("path") == "$.greeting" and node.value == "Héllo 🌍" for node in project.data)
    assert any(node.metadata.get("path") == "$.nested.emoji" and node.value == "🙂" for node in project.data)


def test_json_reader_reports_malformed_json_without_crashing(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"name": "value"', encoding="utf-8")

    project = Project(name="demo", root=str(tmp_path))
    result = JSONReader().read(path, project)

    assert result.success is False
    assert result.warnings
    assert "Could not parse JSON file" in result.warnings[0]
    assert project.summary()["files"] == 1


def test_json_reader_duplicate_processing_does_not_inflate_totals(tmp_path):
    path = tmp_path / "config.json"
    payload = {"service": {"name": "barkly", "ports": [8080, 8081]}}
    path.write_text(json.dumps(payload), encoding="utf-8")

    project = Project(name="demo", root=str(tmp_path))
    reader = JSONReader()
    reader.read(path, project)
    reader.read(path, project)

    assert project.summary()["files"] == 1
    assert project.summary()["classes"] == 0
    assert project.summary()["functions"] == 0
    assert project.summary()["methods"] == 0
    assert len(project.data) == 6


def test_json_reader_html_output_includes_data_paths(tmp_path):
    path = tmp_path / "project.json"
    payload = {"settings": {"debug": False, "version": "1.2.3"}, "items": [1, 2, 3]}
    path.write_text(json.dumps(payload), encoding="utf-8")

    project = ProjectDiscovery([JSONReader()]).analyze(tmp_path, name="fixture").project
    render_project_website(project, tmp_path / "site")
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")

    assert "JSON data" in html
    assert "$.settings" in html
    assert "$.items" in html
    assert "boolean" in html


def test_json_reader_keeps_existing_python_and_java_counts_unchanged(tmp_path):
    py_path = tmp_path / "math_ops.py"
    py_path.write_text(
        "def square(value):\n"
        "    return value * value\n\n\n"
        "class Counter:\n"
        "    def add(self, left, right):\n"
        "        return left + right\n",
        encoding="utf-8",
    )
    java_path = tmp_path / "TypeCounter.java"
    java_path.write_text(
        "public class TypeCounter {\n"
        "    public TypeCounter() {}\n"
        "    public int add(int left, int right) {\n"
        "        return left + right;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    python_project = Project(name="python", root=str(tmp_path))
    PythonReader().read(py_path, python_project)
    assert python_project.summary()["functions"] == 1
    assert python_project.summary()["classes"] == 1
    assert python_project.summary()["methods"] == 1

    java_project = Project(name="java", root=str(tmp_path))
    JavaReader().read(java_path, java_project)
    assert java_project.summary()["classes"] == 1
    assert java_project.summary()["methods"] == 2
    assert {method.name for method in java_project.methods} == {"TypeCounter", "add"}
