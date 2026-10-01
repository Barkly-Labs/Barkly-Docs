"""
BARKLY DOCS
Command Line Interface

Initial project analysis command.
"""

from __future__ import annotations

import argparse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from analysis.discovery import ProjectDiscovery
from readers.python import PythonReader
from readers.rust import RustReader
from readers.javascript import JavaScriptReader
from readers.ruby import RubyReader
from readers.java import JavaReader
from rendering.html import render_project_website

DEFAULT_PREVIEW_HOST = "127.0.0.1"
DEFAULT_PREVIEW_PORT = 8000


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

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Optional output directory for the generated HTML website.",
    )

    parser.add_argument(
        "--serve",
        action="store_true",
        help=(
            "Generate the website and serve it locally on "
            f"{DEFAULT_PREVIEW_HOST}:{DEFAULT_PREVIEW_PORT}."
        ),
    )

    parser.add_argument(
        "--host",
        default=DEFAULT_PREVIEW_HOST,
        help="Local host interface used for preview serving. Defaults to 127.0.0.1.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PREVIEW_PORT,
        help="Local port used for the preview server.",
    )

    return parser


def validate_preview_landing_page(output_dir: Path) -> Path:
    """Validate that a generated landing page exists before a preview opens."""

    if output_dir is None:
        raise FileNotFoundError("No output directory was provided for preview generation.")

    landing_page = Path(output_dir) / "index.html"
    if not landing_page.exists() or not landing_page.is_file():
        raise FileNotFoundError(
            "Landing page not found. Generate the documentation first using "
            "--output or --serve."
        )

    return landing_page


def ensure_website_generated(project_obj, output_dir: Path | None) -> Path:
    """Generate HTML output when the site has not yet been created."""

    if output_dir is None:
        raise FileNotFoundError("No output directory supplied for the HTML website.")

    output_dir = Path(output_dir)
    landing_page = output_dir / "index.html"

    if not landing_page.exists():
        render_project_website(project_obj, output_dir)

    validate_preview_landing_page(output_dir)
    return output_dir


def build_preview_server(output_dir: Path, host: str = DEFAULT_PREVIEW_HOST, port: int = DEFAULT_PREVIEW_PORT):
    """Start a local HTTP server rooted at the generated documentation directory."""

    validate_preview_landing_page(output_dir)

    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(output_dir), **kwargs)

        def log_message(self, format: str, *args) -> None:  # noqa: A003, ARG002
            return

    try:
        server = ThreadingHTTPServer((host, port), QuietHandler)
    except OSError as exc:
        raise RuntimeError(
            f"Port {port} is already in use on {host}. Choose a different port with --port."
        ) from exc

    return server


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
        RubyReader(),
        JavaReader(),
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
            print(f"- {warning}")

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    if result.errors:

        print()
        print("ERRORS")
        print("-" * 50)

        for error in result.errors:
            print(f"X {error}")

    output_dir = None
    if args.output is not None:
        output_dir = Path(args.output)
    elif args.serve:
        output_dir = args.project.resolve() / ".barkly-docs-site"

    if output_dir is not None:
        try:
            output_dir = ensure_website_generated(project, output_dir)
            output_files = render_project_website(project, output_dir)
            print()
            print("HTML WEBSITE")
            print("-" * 50)
            print(f"Output directory: {output_dir}")
            print(f"Index page:       {output_files[0]}")
            print(f"Entities page:    {output_files[1]}")
            print(f"Relationships:    {output_files[2]}")
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            print()
            print("HTML WEBSITE ERROR")
            print("-" * 50)
            print(f"{exc}")
            return 1

    if args.serve:
        try:
            server = build_preview_server(output_dir, host=args.host, port=args.port)
            url = f"http://{args.host}:{args.port}/"
            print()
            print("LOCAL WEBSITE PREVIEW")
            print("-" * 50)
            print(f"URL: {url}")
            print(f"Directory: {output_dir}")
            print("Press Ctrl+C to stop the preview.")

            if webbrowser.open(url):
                print("Opened the landing page in your default browser.")
            else:
                print("Open the URL above in your browser to view the generated website.")

            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print()
                print("Stopping preview server...")
            finally:
                server.server_close()
                print("Preview server stopped.")

            return 0
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            print()
            print("LOCAL WEBSITE ERROR")
            print("-" * 50)
            print(f"{exc}")
            return 1

    print()

    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())