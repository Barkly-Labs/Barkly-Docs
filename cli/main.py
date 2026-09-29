"""
BARKLY DOCS
Command Line Interface

Initial project analysis command.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from analysis.discovery import ProjectDiscovery
from readers.python import PythonReader
from readers.rust import RustReader
from readers.javascript import JavaScriptReader


def build_parser() -> argparse.ArgumentParser:
    """
    Build the Barkly Docs command-line parser.
    """

    parser = argparse.ArgumentParser(
        prog="barkly-docs",
        description=(
            "Analyze a software project and build "
            "the Barkly Project Model."
        ),
    )

    parser.add_argument(
        "project",
        type=Path,
        help="Path to the project to analyze.",
    )

    parser.add_argument(
        "--name",
        default=None,
        help="Optional project name.",
    )

    return parser


def main() -> int:
    """
    Run Barkly Docs.
    """

    parser = build_parser()

    args = parser.parse_args()

    # --------------------------------------------------------
    # REGISTER READERS
    # --------------------------------------------------------

    readers = [
        PythonReader(),
        RustReader(),
        JavaScriptReader(),
    ]

    # --------------------------------------------------------
    # DISCOVER PROJECT
    # --------------------------------------------------------

    discovery = ProjectDiscovery(
        readers=readers,
    )

    result = discovery.analyze(
        root=args.project,
        name=args.name,
    )

    project = result.project

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    print()
    print("BARKLY DOCS")
    print("=" * 50)
    print()
    print(f"Project: {project.name}")
    print(f"Root:    {project.root}")
    print()

    print("PROJECT SUMMARY")
    print("-" * 50)

    for key, value in project.summary().items():
        print(f"{key:20} {value}")

    print()

    print("DISCOVERY")
    print("-" * 50)

    print(
        f"Processed files: "
        f"{len(result.processed_files)}"
    )

    print(
        f"Skipped files:   "
        f"{len(result.skipped_files)}"
    )

    print(
        f"Warnings:        "
        f"{len(result.warnings)}"
    )

    print(
        f"Errors:          "
        f"{len(result.errors)}"
    )

    # --------------------------------------------------------
    # WARNINGS
    # --------------------------------------------------------

    if result.warnings:

        print()
        print("WARNINGS")
        print("-" * 50)

        for warning in result.warnings:
            print(f"⚠ {warning}")

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    if result.errors:

        print()
        print("ERRORS")
        print("-" * 50)

        for error in result.errors:
            print(f"✗ {error}")

    print()

    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())