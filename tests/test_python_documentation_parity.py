from pathlib import Path

from model.project import Project
from readers.python import PythonReader
from readers.ruby import RubyReader
from rendering.entities_page import render_entities_page


def scan(tmp_path: Path, source: str):
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")
    project = Project(name="python-docs", root=str(tmp_path))
    result = PythonReader().read(path, project)
    return result, project, path


def test_python_declared_docs_qualified_names_and_annotations(tmp_path):
    source = '''# -*- coding: utf-8 -*-
"""Module summary — Unicode 🐍."""

class Outer:
    """Outer docs."""
    class Inner:
        """Inner docs."""
        @classmethod
        async def build(cls, value: str = "x") -> dict[str, str]:
            """Build data.

            Args:
                value: Input value.
            Returns:
                Built mapping.
            Raises:
                ValueError: On invalid input.
            """
            return {"value": value}

    @property
    def name(self) -> str:
        """Visible name."""
        return "x"

    @name.setter
    def name(self, value: str):
        """Set the visible name."""
        pass

def outer(flag: bool):
    """Outer function."""
    def inner(count: int) -> int:
        """Nested docs."""
        return count
    return inner(1)
'''
    result, project, _ = scan(tmp_path, source)
    assert result.success
    assert project.modules[0].documentation == "Module summary — Unicode 🐍."
    assert project.modules[0].metadata["documentation_evidence"] == "DECLARED"
    inner_class = next(c for c in project.classes if c.name == "Inner")
    assert inner_class.metadata["qualified_name"] == "Outer.Inner"
    build = next(m for m in project.methods if m.name == "build")
    assert build.class_name == "Outer.Inner"
    assert build.async_function is True
    assert build.metadata["method_kind"] == "class_method"
    docs = build.metadata["documentation_format"]
    assert docs["params"]["value"] == {"type": "str", "description": "Input value."}
    assert docs["returns"]["type"] == "dict[str, str]"
    assert docs["raises"][0]["type"] == "ValueError"
    getter, setter = [m for m in project.methods if m.name == "name"]
    assert getter.metadata["property_role"] == "getter"
    assert setter.metadata["property_role"] == "setter"
    assert setter.metadata["property_name"] == "name"
    nested = next(f for f in project.functions if f.name == "inner")
    assert nested.metadata["qualified_name"] == "outer.inner"
    assert nested.documentation == "Nested docs."


def test_google_numpy_and_rst_structured_docstrings(tmp_path):
    source = '''def google(path: str) -> dict:
    """Load configuration.

    Args:
        path: Config path.
    Returns:
        Parsed configuration.
    Raises:
        FileNotFoundError: Missing file.
    Examples:
        google("x")
    Deprecated:
        Use load() instead.
    """

def numpy(value):
    """Normalize.

    Parameters
    ----------
    value : str
        Value to normalize.

    Returns
    -------
    str
        Normalized value.
    """

def rst(value: int):
    """Calculate.

    :param value: Input value.
    :type value: int
    :return: Calculated result.
    :rtype: int
    :raises ValueError: Invalid input.
    :note: Stable API.
    :warning: Expensive operation.
    :author: Barkly Labs
    :version: 1.2
    """
'''
    result, project, _ = scan(tmp_path, source)
    assert result.success
    by_name = {f.name: f for f in project.functions}
    google = by_name["google"].metadata["documentation_format"]
    assert google["params"]["path"]["description"] == "Config path."
    assert google["returns"]["type"] == "dict"
    assert google["examples"] == ['google("x")']
    assert google["deprecated"] == ["Use load() instead."]
    numpy = by_name["numpy"].metadata["documentation_format"]
    assert numpy["params"]["value"] == {"type": "str", "description": "Value to normalize."}
    assert numpy["returns"] == {"type": "str", "description": "Normalized value."}
    rst = by_name["rst"].metadata["documentation_format"]
    assert rst["raises"][0]["type"] == "ValueError"
    assert rst["notes"] == ["Stable API."]
    assert rst["warnings"] == ["Expensive operation."]
    assert rst["authors"] == ["Barkly Labs"]
    assert rst["version"] == ["1.2"]


def test_docstring_position_invalid_source_and_no_execution(tmp_path):
    marker = tmp_path / "executed.txt"
    source = f'''import pathlib
pathlib.Path({str(marker)!r}).write_text("bad")
"""This is not a module docstring."""

def safe():
    """Declared docs."""
    return 1
'''
    result, project, _ = scan(tmp_path, source)
    assert result.success
    assert project.modules[0].documentation is None
    assert not marker.exists()

    bad = tmp_path / "broken.py"
    bad.write_text("def broken(:\n    pass\n", encoding="utf-8")
    bad_project = Project(name="bad", root=str(tmp_path))
    bad_result = PythonReader().read(bad, bad_project)
    assert bad_result.success is False
    assert bad_project.files[0].metadata["parse_error"]["line"] == 1


def test_python_documentation_reaches_shared_entity_renderer_safely(tmp_path):
    result, project, _ = scan(tmp_path, '''class Service:\n    """Service <unsafe> & useful."""\n    def run(self, value: str) -> str:\n        """Run <work> & return it."""\n        return value\n''')
    assert result.success
    html = render_entities_page(project)
    assert "Service &lt;unsafe&gt; &amp; useful." in html
    assert "Run &lt;work&gt; &amp; return it." in html
    assert "Service.run" in html


def test_ruby_and_python_share_declared_documentation_contract(tmp_path):
    py_result, py_project, _ = scan(tmp_path, 'def load(path):\n    """Load data."""\n    return path\n')
    ruby_path = tmp_path / "sample.rb"
    ruby_path.write_text("# Load data.\ndef load(path)\n  path\nend\n", encoding="utf-8")
    ruby_project = Project(name="ruby-docs", root=str(tmp_path))
    ruby_result = RubyReader().read(ruby_path, ruby_project)
    assert py_result.success and ruby_result.success
    py = py_project.functions[0]
    rb = ruby_project.functions[0]
    assert py.documentation == rb.documentation == "Load data."
    assert py.metadata["documentation_evidence"] == rb.metadata["documentation_evidence"] == "DECLARED"
    assert py.metadata["documentation_line_start"] is not None
    assert rb.metadata["documentation_line_start"] is not None
