from pathlib import Path

from barkly_docs.analyzers.docx import parse_docx


def test_module_imports():
    assert parse_docx is not None
