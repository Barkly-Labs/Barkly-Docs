from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cli.terminal import BarklyTerminal
from analysis.discovery import ProjectDiscovery
from model.project import Project
from readers.java import JavaReader


def test_file_level_counts_are_emitted_and_distinct(tmp_path):
    # Prepare three Java files with different declarations.
    a = tmp_path / "A.java"
    a.write_text(
        "public class A {\n    public A() {}\n    public void m1() {}\n}\n",
        encoding="utf-8",
    )

    b = tmp_path / "B.java"
    b.write_text(
        "public class B {\n    public B() {}\n    public void m1() {}\n    public void m2() {}\n}\n",
        encoding="utf-8",
    )

    c = tmp_path / "C.java"
    c.write_text(
        "public class C {\n    public C() {}\n}\n",
        encoding="utf-8",
    )

    log_file = tmp_path / "events.jsonl"
    term = BarklyTerminal(
        project_name="fixture",
        root=str(tmp_path),
        log_file=str(log_file),
        log_format="jsonl",
        quiet=False,
    )

    discovery = ProjectDiscovery([JavaReader()])
    result = discovery.analyze(tmp_path, name="fixture", event_logger=term)

    # Read the JSONL file and collect file events.
    lines = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    file_events = [l for l in lines if l.get("event", "").startswith("file.")]

    # There should be at least 3 file.complete events (one per Java file)
    per_file = {ev.get("file"): ev.get("counts", {}) for ev in file_events}

    assert str(a.name) in per_file
    assert str(b.name) in per_file
    assert str(c.name) in per_file

    # Check per-file per_file counts for classes and methods
    assert per_file[str(a.name)]["per_file"]["classes"] == 1
    assert per_file[str(a.name)]["per_file"]["methods"] == 2  # constructor + m1

    assert per_file[str(b.name)]["per_file"]["classes"] == 1
    assert per_file[str(b.name)]["per_file"]["methods"] == 3  # constructor + m1 + m2

    assert per_file[str(c.name)]["per_file"]["classes"] == 1
    assert per_file[str(c.name)]["per_file"]["methods"] == 1  # constructor only

    # Project totals should equal combined counts (classes:3, methods:6)
    # Find the last file.complete event and inspect project totals.
    complete_events = [ev for ev in file_events if ev.get("event") == "file.complete"]
    assert complete_events, "no file.complete events logged"
    last_complete = complete_events[-1]
    project_totals = last_complete.get("counts", {}).get("project")
    assert project_totals is not None
    assert project_totals["classes"] == 3
    assert project_totals["methods"] == 6

    # Re-run the discovery and ensure per-file counts are stable and
    # project totals do not double-count duplicates (deduplication enforced by model).
    discovery.analyze(tmp_path, name="fixture", event_logger=term)
    lines2 = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    file_events2 = [l for l in lines2 if l.get("event", "").startswith("file.")]
    complete_events2 = [ev for ev in file_events2 if ev.get("event") == "file.complete"]
    assert complete_events2, "no file.complete events after rerun"
    last2 = complete_events2[-1]
    project_totals2 = last2.get("counts", {}).get("project")
    assert project_totals2["classes"] == 3
    assert project_totals2["methods"] == 6
