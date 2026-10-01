from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cli.terminal import build_terminal


def test_terminal_header_and_progress_rendering(capsys):
    terminal = build_terminal(
        project_name="demo",
        root="/tmp/demo",
        no_progress=False,
        quiet=False,
        no_color=True,
    )
    terminal.render_header()
    terminal.render_progress(
        stage="analysis.java",
        current=5,
        total=10,
        current_file="src/example/App.java",
        counts={"files": 5, "relationships": 12},
    )
    captured = capsys.readouterr()
    assert "BARKLY LABS" in captured.out
    assert "demo" in captured.out
    assert "analysis.java" in captured.out
    assert "src/example/App.java" in captured.out


def test_terminal_supports_jsonl_logging(tmp_path):
    log_path = tmp_path / "events.jsonl"
    terminal = build_terminal(
        project_name="demo",
        root=str(tmp_path),
        quiet=True,
        no_progress=True,
        log_file=log_path,
        log_format="jsonl",
    )
    terminal.stage_start("discovery")
    terminal.stage_complete("discovery", discovered=2)
    terminal.close()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    payload = json.loads(lines[0])
    assert payload["event"] == "discovery.start"
    assert payload["run_id"]
    assert payload["project"] == "demo"


def test_terminal_handles_quiet_and_redirected_output():
    terminal = build_terminal(
        project_name="demo",
        root="/tmp/demo",
        quiet=True,
        no_progress=True,
    )
    terminal.render_header()
    terminal.stage_start("discovery")
    terminal.close()


def test_terminal_noninteractive_no_progress_mode():
    terminal = build_terminal(
        project_name="demo",
        root="/tmp/demo",
        no_progress=True,
        quiet=False,
        no_color=True,
    )
    terminal.render_progress(stage="analysis", current=1, total=2)
    terminal.close()


def test_terminal_final_report_formats_warning_counts():
    terminal = build_terminal(
        project_name="demo",
        root="/tmp/demo",
        quiet=False,
        no_color=True,
        no_progress=True,
    )
    class FakeResult:
        processed_files = ["a.py"]
        skipped_files = ["b.txt"]
        errors = ["bad file"]
        warnings = ["warn 1"]
    class FakeProject:
        def summary(self):
            return {"classes": 1, "functions": 2, "methods": 3, "relationships": 4}
    terminal.final_report(result=FakeResult(), output_dir="/tmp/site", project=FakeProject(), warnings=["warn 1"], errors=["bad file"])
    terminal.close()
