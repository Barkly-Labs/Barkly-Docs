from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.discovery import ProjectDiscovery
from model.project import ClassNode, FileNode, FunctionNode, MethodNode, ModuleNode, Project
from readers.java import JavaReader
from readers.javascript import JavaScriptReader
from readers.python import PythonReader
from readers.ruby import RubyReader
from readers.rust import RustReader


def test_project_discovery_finds_supported_files_and_skips_ignored_dirs(tmp_path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    (source_dir / "ui.js").write_text("export function run() { return 1; }\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore me\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("console.log('ignore me')\n", encoding="utf-8")

    result = ProjectDiscovery(
        [PythonReader(), JavaScriptReader()],
    ).analyze(tmp_path, name="fixture")

    processed = {path.name for path in result.processed_files}
    assert {"app.py", "ui.js"}.issubset(processed)
    assert "notes.txt" not in processed
    assert not any(path.name == "pkg.js" for path in result.processed_files)
    assert result.project.name == "fixture"


def test_readers_are_selected_for_the_right_file_types():
    readers = [PythonReader(), JavaScriptReader(), JavaReader(), RubyReader(), RustReader()]

    by_extension = {
        ".py": PythonReader,
        ".js": JavaScriptReader,
        ".java": JavaReader,
        ".rb": RubyReader,
        ".rs": RustReader,
    }

    for extension, reader_type in by_extension.items():
        selected = next(reader for reader in readers if reader.can_read(Path(f"sample{extension}")))
        assert isinstance(selected, reader_type)

    assert not PythonReader().can_read(Path("sample.txt"))


def test_project_summary_is_consistent():
    project = Project(name="demo", root="/tmp/demo")
    project.add_file(FileNode(path="/tmp/demo/app.py", language="Python"))
    project.add_module(ModuleNode(name="app", path="/tmp/demo/app.py", language="Python"))
    project.add_function(FunctionNode(name="hello", path="/tmp/demo/app.py", language="Python"))
    project.add_method(
        MethodNode(name="run", path="/tmp/demo/app.py", language="Python", class_name="Thing")
    )
    project.add_class(ClassNode(name="Thing", path="/tmp/demo/app.py", language="Python"))

    summary = project.summary()
    assert summary["files"] == 1
    assert summary["modules"] == 1
    assert summary["functions"] == 1
    assert summary["methods"] == 1
    assert summary["classes"] == 1


def test_python_reader_extracts_functions_classes_and_variables(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text(
        """
VALUE = 7


def greet(name: str) -> str:
    \"\"\"Return a greeting.\"\"\"
    return f\"hello {name}\"


class Greeter:
    def format(self, name: str) -> str:
        return greet(name)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    project = Project(name="demo", root=str(tmp_path))
    result = PythonReader().read(path, project)

    assert result.success is True
    assert not result.errors
    assert {function.name for function in project.functions} == {"greet"}
    assert {class_node.name for class_node in project.classes} == {"Greeter"}
    assert {method.name for method in project.methods} == {"format"}
    variable_names = {variable.name for variable in project.variables}
    assert "VALUE" in variable_names


def test_supported_readers_do_not_crash_on_ordinary_source_files(tmp_path):
    cases = [
        (
            PythonReader(),
            "demo.py",
            "def double(value):\n    return value * 2\n",
        ),
        (
            JavaScriptReader(),
            "demo.js",
            "export function double(value) { return value * 2; }\n",
        ),
        (
            JavaReader(),
            "Demo.java",
            "public class Demo { public int doubleValue(int value) { return value * 2; } }\n",
        ),
        (
            RubyReader(),
            "demo.rb",
            "class Demo\n  def double(value)\n    value * 2\n  end\nend\n",
        ),
        (
            RustReader(),
            "demo.rs",
            "pub struct Demo { value: i32 }\n\nimpl Demo { pub fn double(&self) -> i32 { self.value * 2 } }\n",
        ),
    ]

    for reader, filename, source_text in cases:
        path = tmp_path / filename
        path.write_text(source_text, encoding="utf-8")
        result = reader.read(path, Project(name="demo", root=str(tmp_path)))
        assert result.success is True, (filename, result.errors)


def test_cli_runs_on_a_small_project_and_returns_zero(tmp_path):
    project_dir = tmp_path / "fixture"
    project_dir.mkdir()
    (project_dir / "example.py").write_text(
        "def run():\n    return 7\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "cli", str(project_dir), "--name", "Fixture"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "BARKLY DOCS" in result.stdout
    assert "Project: Fixture" in result.stdout
