"""
BARKLY DOCS
Command Line Interface

Initial project analysis command.
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from analysis.discovery import ProjectDiscovery
from cli.terminal import build_terminal
from readers.python import PythonReader
from readers.rust import RustReader
from readers.javascript import JavaScriptReader
from readers.ruby import RubyReader
from readers.java import JavaReader
from readers.json import JSONReader
from rendering.html import render_project_website

DEFAULT_PREVIEW_HOST = "127.0.0.1"
DEFAULT_PREVIEW_PORT = 8000
DEFAULT_OUTPUT_DIR = ".barkly-docs-site"


def build_parser() -> argparse.ArgumentParser:
    """
    Build the Barkly Docs command-line parser.
    """

    parser = argparse.ArgumentParser(
        prog="barkly-docs",
        description=(
            "Analyze a software project and build " "the Barkly Project Model."
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
        help="Launch the generated HTML website using the built-in preview server.",
    )

    parser.add_argument(
        "--generate-only",
        action="store_true",
        help=(
            "Generate the documentation without starting the preview "
            "server or opening a browser."
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

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed diagnostic and pipeline logging.",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "Suppress the interactive terminal display but keep processing "
            "and log-file output active."
        ),
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output for terminal messages.",
    )

    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the live progress bar while keeping regular logs active.",
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Use process-based parallel parsing for independent source files.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Override the number of worker processes used by parallel discovery. "
            "Defaults to CPU core count when parallel is enabled."
        ),
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Write a timestamped pipeline log to the given file path.",
    )

    parser.add_argument(
        "--log-format",
        choices=("text", "jsonl"),
        default="text",
        help="Choose the format for the log output file; terminal logs remain human-readable.",
    )

    return parser


def validate_preview_landing_page(output_dir: Path) -> Path:
    """Validate that a generated landing page exists before a preview opens."""

    if output_dir is None:
        raise FileNotFoundError(
            "No output directory was provided for preview generation."
        )

    landing_page = Path(output_dir) / "index.html"

    if not landing_page.exists() or not landing_page.is_file():
        raise FileNotFoundError(
            "Landing page not found. Generate the documentation first "
            "using --generate-only or run Barkly Docs normally."
        )

    return landing_page


def ensure_website_generated(
    project_obj,
    output_dir: Path | None,
) -> Path:
    """Generate HTML output when the site has not yet been created."""

    if output_dir is None:
        raise FileNotFoundError("No output directory supplied for the HTML website.")

    output_dir = Path(output_dir)
    landing_page = output_dir / "index.html"

    if not landing_page.exists():
        render_project_website(project_obj, output_dir)

    validate_preview_landing_page(output_dir)

    return output_dir


def build_preview_server(
    output_dir: Path,
    host: str = DEFAULT_PREVIEW_HOST,
    port: int = DEFAULT_PREVIEW_PORT,
) -> ThreadingHTTPServer:
    """Build a local HTTP server rooted at the generated documentation directory."""

    validate_preview_landing_page(output_dir)

    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(
                *args,
                directory=str(Path(output_dir).resolve()),
                **kwargs,
            )

        def log_message(self, format: str, *args) -> None:  # noqa: A003, ARG002
            return

    try:
        server = ThreadingHTTPServer((host, port), QuietHandler)
    except OSError as exc:
        raise RuntimeError(
            f"Port {port} is unavailable on {host}. "
            "Choose a different port with --port."
        ) from exc

    return server


def main() -> int:
    """
    Run Barkly Docs.
    """

    parser = build_parser()
    args = parser.parse_args()

    if not args.project.exists():
        print(
            f"Project path does not exist: {args.project}",
            file=sys.stderr,
        )
        return 2

    if not args.project.is_dir():
        print(
            f"Project path is not a directory: {args.project}",
            file=sys.stderr,
        )
        return 2

    project_name = args.name or args.project.name

    terminal = build_terminal(
        project_name=project_name,
        root=str(args.project.resolve()),
        quiet=args.quiet,
        verbose=args.verbose,
        no_color=args.no_color,
        no_progress=args.no_progress,
        log_file=args.log_file,
        log_format=args.log_format,
    )

    terminal.render_header()
    terminal.stage_start(
        "cli.init",
        project=str(args.project.resolve()),
    )

    terminal.event(
        "cli.config",
        level="INFO",
        args={
            "verbose": args.verbose,
            "quiet": args.quiet,
            "no_color": args.no_color,
            "no_progress": args.no_progress,
            "log_format": args.log_format,
            "log_file": str(args.log_file) if args.log_file else None,
        },
    )

    readers = [
        PythonReader(),
        RustReader(),
        JavaScriptReader(),
        RubyReader(),
        JavaReader(),
        JSONReader(),
    ]

    discovery = ProjectDiscovery(readers=readers)
    start_ts = time.perf_counter()

    try:
        result = discovery.analyze(
            root=args.project,
            name=args.name,
            event_logger=terminal,
            progress_callback=terminal.render_progress,
            parallel=args.parallel,
            workers=args.workers,
        )

    except KeyboardInterrupt:
        terminal.event(
            "pipeline.interrupted",
            level="WARNING",
            message="Processing interrupted by user.",
        )
        terminal.clear_progress()
        terminal.close()
        return 130

    except Exception as exc:
        terminal.event(
            "pipeline.fatal",
            level="ERROR",
            message=str(exc),
            error=repr(exc),
        )
        terminal.clear_progress()
        terminal.close()
        return 2

    terminal.stage_complete(
        "cli.init",
        duration_ms=int((time.perf_counter() - start_ts) * 1000),
    )

    project = result.project

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

    print(f"Processed files: {len(result.processed_files)}")
    print(f"Skipped files:   {len(result.skipped_files)}")
    print(f"Warnings:        {len(result.warnings)}")
    print(f"Errors:          {len(result.errors)}")

    if result.warnings:
        print()
        print("WARNINGS")
        print("-" * 50)

        for warning in result.warnings:
            print(f"- {warning}")

    if result.errors:
        print()
        print("ERRORS")
        print("-" * 50)

        for error in result.errors:
            print(f"X {error}")

    # Generate the complete Barkly Docs HTML website.
    # The native HTML/SVG architecture graph is part of this website.
    # No Docker container or external architecture service is required.
    output_dir = (
        Path(args.output)
        if args.output is not None
        else args.project.resolve() / DEFAULT_OUTPUT_DIR
    )

    try:
        terminal.stage_start(
            "rendering.html",
            output=str(output_dir),
        )

        output_dir = ensure_website_generated(project, output_dir)

        output_files = render_project_website(
            project,
            output_dir,
        )

        terminal.stage_complete(
            "rendering.html",
            pages=len(output_files),
            output=str(output_dir),
        )

        print()
        print("HTML WEBSITE")
        print("-" * 50)

        print(f"Output directory: {output_dir}")

        if len(output_files) > 0:
            print(f"Index page:       {output_files[0]}")

        if len(output_files) > 1:
            print(f"Entities page:    {output_files[1]}")

        if len(output_files) > 2:
            print(f"Relationships:    {output_files[2]}")

    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        terminal.event(
            "rendering.html.failed",
            level="ERROR",
            error=str(exc),
            message="HTML generation failed.",
        )

        print()
        print("HTML WEBSITE ERROR")
        print("-" * 50)
        print(exc)

        terminal.close()
        return 1

    # Generate-only mode writes the site without opening a browser
    # or starting the local HTTP server.
    if args.generate_only:
        terminal.final_report(
            result=result,
            output_dir=str(output_dir),
            project=project,
            warnings=result.warnings,
            errors=result.errors,
        )

        terminal.close()
        print()

        return 0 if not result.errors else 1

    # Serve the generated website directly from Barkly Docs.
    server = None

    try:
        preview_url = f"http://{args.host}:{args.port}/"

        server = build_preview_server(
            output_dir,
            host=args.host,
            port=args.port,
        )

        print()
        print("BARKLY DOCS IS READY")
        print("-" * 50)
        print(f"Documentation: {preview_url}")
        print(f"Output:        {output_dir}")
        print("Server:        Built-in HTML preview")
        print("Press Ctrl+C to stop the server.")

        terminal.close()

        try:
            webbrowser.open(preview_url)
        except Exception as exc:
            print(f"Could not open the browser automatically: {exc}")
            print(f"Open {preview_url} in your browser.")

        try:
            server.serve_forever()

        except KeyboardInterrupt:
            print()
            print("Barkly Docs preview server stopped.")

        finally:
            server.server_close()

        return 0

    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        terminal.event(
            "launch.failed",
            level="ERROR",
            error=str(exc),
            message="HTML preview server could not start.",
        )

        print()
        print("BARKLY DOCS LAUNCH ERROR")
        print("-" * 50)
        print(exc)
        print(f"The generated HTML files remain available in: {output_dir}")

        if server is not None:
            server.server_close()

        terminal.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
