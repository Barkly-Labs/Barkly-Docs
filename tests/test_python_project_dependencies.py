from pathlib import Path

from analysis.discovery import ProjectDiscovery
from readers.python import PythonReader
from readers.python_dependencies import PythonDependencyReader
from rendering.index_page import render_index


def scan(root: Path):
    return ProjectDiscovery([PythonDependencyReader(), PythonReader()]).analyze(root).project


def test_pyproject_pep621_optional_build_poetry_and_import_evidence(tmp_path):
    (tmp_path / "pyproject.toml").write_text('''
[build-system]
requires = ["setuptools>=68"]
[project]
name = "demo"
dependencies = ["requests>=2; python_version >= '3.10'", "PyYAML>=6"]
[project.optional-dependencies]
test = ["pytest>=8"]
[tool.poetry.group.docs.dependencies]
mkdocs = "^1.6"
''', encoding="utf-8")
    (tmp_path / "app.py").write_text("import requests\nimport yaml\nimport os\n", encoding="utf-8")
    p = scan(tmp_path)
    deps = {(d.name, d.kind, (d.metadata or {}).get("group")): d for d in p.dependencies}
    assert ("requests", "runtime", None) in deps
    assert ("pytest", "optional", "test") in deps
    assert ("setuptools", "build-system", None) in deps
    assert ("mkdocs", "development", "docs") in deps
    assert deps[("PyYAML", "runtime", None)].metadata["import_evidence"] == ["yaml"]
    imports = {i.target: i for i in p.imports}
    assert imports["os"].metadata["dependency_scope"] == "standard_library"
    assert imports["yaml"].metadata["declared_dependency"] == "PyYAML"
    assert deps[("requests", "runtime", None)].metadata["marker"] == "python_version >= '3.10'"


def test_requirements_setup_cfg_and_static_setup_py_without_execution(tmp_path):
    (tmp_path / "requirements.txt").write_text("urllib3==2.2\n-r extra.txt\n-c constraints.txt\n-e git+https://example.invalid/acme.git#egg=acme\n", encoding="utf-8")
    (tmp_path / "extra.txt").write_text("rich>=13\n", encoding="utf-8")
    (tmp_path / "constraints.txt").write_text("urllib3<3\n", encoding="utf-8")
    (tmp_path / "setup.cfg").write_text("[options]\ninstall_requires =\n    click>=8\n[options.extras_require]\ndocs =\n    sphinx>=7\n", encoding="utf-8")
    marker = tmp_path / "EXECUTED"
    (tmp_path / "setup.py").write_text(f'''from setuptools import setup\nopen({str(marker)!r}, "w").write("bad")\nREQS=["httpx>=0.27"]\nsetup(install_requires=REQS, extras_require={{"test": ["pytest>=8"]}})\n''', encoding="utf-8")
    p=scan(tmp_path)
    assert not marker.exists()
    names={d.name for d in p.dependencies}
    assert {"urllib3","rich","acme","click","sphinx","httpx","pytest"} <= names
    constraint=[d for d in p.dependencies if d.source.endswith("constraints.txt")][0]
    assert constraint.metadata["constraint"] is True
    editable=[d for d in p.dependencies if d.name=="acme"][0]
    assert editable.metadata["editable"] is True and editable.metadata["source_type"] == "git"


def test_lock_conda_malformed_and_html_rendering(tmp_path):
    (tmp_path / "Pipfile.lock").write_text('{"default":{"requests":{"version":"==2.32.3","hashes":["sha256:abc"]}}}', encoding="utf-8")
    (tmp_path / "environment.yml").write_text("name: demo\ndependencies:\n  - python=3.12\n  - numpy=2.0\n  - pip:\n    - flask>=3\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("import flask\n", encoding="utf-8")
    p=scan(tmp_path)
    locked=[d for d in p.dependencies if d.name=="requests"][0]
    assert locked.metadata["locked"] is True and locked.version == "==2.32.3"
    numpy=[d for d in p.dependencies if d.name=="numpy"][0]
    assert numpy.metadata["environment_manager"] == "conda"
    html=render_index(p)
    assert "Dependencies" in html and "Static import evidence" in html and "flask" in html
    assert "Pipfile.lock" in html and "Locked / resolved version evidence" in html


def test_monorepo_ignored_virtualenv_is_not_scanned(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="root"\ndependencies=["requests"]\n', encoding="utf-8")
    sub=tmp_path/"packages"/"tool"; sub.mkdir(parents=True)
    (sub/"pyproject.toml").write_text('[project]\nname="tool"\ndependencies=["click"]\n', encoding="utf-8")
    bad=tmp_path/".venv"; bad.mkdir(); (bad/"requirements.txt").write_text("evilpkg\n", encoding="utf-8")
    p=scan(tmp_path)
    assert {d.name for d in p.dependencies} == {"requests","click"}
    assert all(".venv" not in d.source for d in p.dependencies)

def test_pipfile_poetry_lock_pdm_and_malformed_manifest(tmp_path):
    (tmp_path / "Pipfile").write_text('[packages]\nrequests = "==2.32.3"\n[dev-packages]\npytest = "*"\n', encoding="utf-8")
    (tmp_path / "poetry.lock").write_text('[[package]]\nname = "idna"\nversion = "3.8"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('''[project]\nname="demo"\ndependencies=["requests>=2"]\n[tool.pdm.dev-dependencies]\ntest=["coverage>=7"]\n''', encoding="utf-8")
    p=scan(tmp_path)
    by_name={d.name: d for d in p.dependencies}
    assert by_name["requests"].metadata["direct"] is True
    assert any(d.name == "pytest" and d.kind == "development" for d in p.dependencies)
    assert any(d.name == "coverage" and d.kind == "development" and d.metadata["group"] == "test" for d in p.dependencies)
    lock=[d for d in p.dependencies if d.name == "idna"][0]
    assert lock.metadata["locked"] is True and lock.metadata["direct"] is None

    broken=tmp_path / "packages"; broken.mkdir()
    (broken / "pyproject.toml").write_text("[project\nthis is not toml", encoding="utf-8")
    result=ProjectDiscovery([PythonDependencyReader(), PythonReader()]).analyze(tmp_path)
    assert any("Could not fully parse dependency manifest" in warning for warning in result.warnings)


def test_requirement_url_marker_and_graph_dependency_node(tmp_path):
    (tmp_path / "requirements.txt").write_text('demo @ https://example.invalid/demo.whl ; python_version >= "3.11"\nPillow>=10\n', encoding="utf-8")
    (tmp_path / "app.py").write_text("from PIL import Image\n", encoding="utf-8")
    result=ProjectDiscovery([PythonDependencyReader(), PythonReader()]).analyze(tmp_path)
    p=result.project
    demo=[d for d in p.dependencies if d.name == "demo"][0]
    assert demo.metadata["source_type"] == "url"
    assert demo.metadata["marker"] == 'python_version >= "3.11"'
    pillow=[d for d in p.dependencies if d.name == "Pillow"][0]
    assert pillow.metadata["import_evidence"] == ["PIL"]
    assert p.imports[0].metadata["dependency_scope"] == "external_python"


def test_import_alias_evidence_is_selective_preserves_metadata_and_direct_html(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "PyYAML>=6\nPillow>=10\nrich>=13\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "import yaml\nfrom PIL import Image\n",
        encoding="utf-8",
    )

    p = scan(tmp_path)
    deps = {d.name: d for d in p.dependencies}

    assert deps["PyYAML"].metadata["import_evidence"] == ["yaml"]
    assert deps["Pillow"].metadata["import_evidence"] == ["PIL"]
    assert "import_evidence" not in deps["rich"].metadata
    assert "import_observed" not in deps["rich"].metadata
    assert deps["PyYAML"].metadata["declaration"] == "PyYAML>=6"
    assert deps["PyYAML"].metadata["source_type"] == "registry"

    html = render_index(p)
    assert "Static import evidence" in html
    assert "yaml" in html
    assert "PIL" in html
    assert "Not observed; this does not prove the dependency is unused." in html
    assert "&gt;=6" in html
    assert "&gt;=10" in html
