from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyzers.docx import parse_docx
from .analyzers.python import analyze_python
from .renderers.html import render_document


def _init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "docs").mkdir(exist_ok=True)
    print(f"Initialized Barkly Docs workspace: {path.resolve()}")


def _generate(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    python_files = sorted(source.rglob("*.py"))
    modules = [analyze_python(p) for p in python_files if ".git" not in p.parts and "docs" not in p.parts]
    manifest = {"generator": "barkly-docs", "version": "0.1.0", "source": str(source), "modules": modules, "documents": []}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    index = output / "index.html"
    cards = "".join(f'<li>{m["file"]}: {len(m["functions"])} functions, {len(m["classes"])} classes</li>' for m in modules)
    index.write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>Barkly Docs</title></head><body><h1>Barkly Docs</h1><ul>{cards}</ul></body></html>", encoding="utf-8")
    print(f"Generated {index}")


def _document(source: Path, output: Path, document_type: str) -> None:
    document = parse_docx(source, document_type=document_type)
    target = render_document(document, output)
    print(f"Generated {target}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="barkly-docs", description="Human-centered documentation infrastructure for Barkly Labs.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("path", nargs="?", default=".")

    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--source", default=".")
    p_gen.add_argument("--output", default="docs")
    p_gen.add_argument("--name", default=None)

    p_doc = sub.add_parser("document")
    p_doc.add_argument("source")
    p_doc.add_argument("--output", required=True)
    p_doc.add_argument("--type", default="functional-requirements")

    args = parser.parse_args(argv)
    if args.command == "init":
        _init(Path(args.path))
    elif args.command == "generate":
        _generate(Path(args.source), Path(args.output))
    elif args.command == "document":
        _document(Path(args.source), Path(args.output), args.type)
    return 0
