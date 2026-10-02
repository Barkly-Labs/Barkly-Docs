from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


class BarklyTerminal:
    """Reusable terminal display and pipeline logger for Barkly Docs."""

    def __init__(
        self,
        project_name: str,
        root: str,
        *,
        quiet: bool = False,
        verbose: bool = False,
        no_color: bool = False,
        no_progress: bool = False,
        log_file: str | Path | None = None,
        log_format: str = "text",
    ) -> None:
        self.project_name = project_name
        self.root = root
        self.quiet = quiet
        self.verbose = verbose
        self.no_color = no_color
        self.no_progress = no_progress
        self.log_file = Path(log_file) if log_file is not None else None
        self.log_format = log_format.lower()
        self.run_id = uuid.uuid4().hex
        self.started_at = time.perf_counter()
        self._json_handle = None
        self._logger = logging.getLogger(f"barkly.{self.run_id}")
        self._logger.handlers.clear()
        self._logger.propagate = False
        self._logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

        if self.log_file is not None:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._json_handle = self.log_file.open("a", encoding="utf-8")

        if not quiet:
            stream = logging.StreamHandler(sys.stdout)
            stream.setLevel(logging.DEBUG if self.verbose else logging.INFO)
            stream.setFormatter(
                _TextFormatter(color=not no_color and self._supports_color())
            )
            self._logger.addHandler(stream)

        self._terminal_enabled = (
            not quiet and not no_progress and sys.stdout is not None
        )
        self._interactive_terminal = bool(
            hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        )
        self._last_line = ""

    def _supports_color(self) -> bool:
        if self.no_color:
            return False
        if not hasattr(sys.stdout, "isatty"):
            return False
        return bool(sys.stdout.isatty())

    def _safe_text(self, text: str) -> str:
        try:
            stream = sys.stdout
            if hasattr(stream, "encoding") and stream.encoding:
                text.encode(stream.encoding)
            return text
        except (AttributeError, UnicodeEncodeError, ValueError):
            return text.encode("ascii", "replace").decode("ascii")

    def _print_safe(
        self, text: str = "", *, end: str = "\n", flush: bool = False
    ) -> None:
        safe = self._safe_text(text)
        try:
            print(safe, end=end, flush=flush)
        except UnicodeEncodeError:
            fallback = safe.encode("ascii", "replace").decode("ascii")
            print(fallback, end=end, flush=flush)

    def _iso_now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _emit_text(self, level: int, event: str, **fields: Any) -> None:
        if self.quiet and not self.log_file:
            return
        message = event
        if "message" in fields and fields["message"]:
            message = fields["message"]
        parts = [self._iso_now(), logging.getLevelName(level).upper(), event]
        if message and message != event:
            parts.append(message)
        for key, value in fields.items():
            if key in {"event", "message", "stage_id", "parent_stage_id", "level"}:
                continue
            if value is None:
                continue
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value, sort_keys=True, default=str)
            parts.append(f"{key}={value}")
        text = " ".join(str(part) for part in parts)
        if self.log_file is not None and self.log_format == "jsonl":
            payload = {
                "timestamp": self._iso_now(),
                "level": logging.getLevelName(level),
                "event": event,
                "run_id": self.run_id,
                "project": self.project_name,
                "root": self.root,
            }
            for key, value in fields.items():
                if key == "message":
                    payload["message"] = value
                else:
                    payload[key] = value
            if self._json_handle is not None:
                self._json_handle.write(
                    json.dumps(payload, sort_keys=True, default=str) + "\n"
                )
                self._json_handle.flush()
        if not self.quiet or self.log_file:
            self._logger.log(level, text)

    def event(self, event: str, level: str = "INFO", **fields: Any) -> None:
        """Emit a pipeline event."""

        normalized = str(level).upper()
        value = {
            "timestamp": self._iso_now(),
            "event": event,
            "run_id": self.run_id,
            "project": self.project_name,
            "root": self.root,
        }
        if "stage_id" in fields:
            value["stage_id"] = fields["stage_id"]
        if "parent_stage_id" in fields:
            value["parent_stage_id"] = fields["parent_stage_id"]
        if "message" in fields:
            value["message"] = fields["message"]
        for key, val in fields.items():
            if key in {"message", "stage_id", "parent_stage_id"}:
                continue
            value[key] = val

        if self.log_file is not None and self.log_format == "jsonl":
            self._json_handle.write(
                json.dumps(value, sort_keys=True, default=str) + "\n"
            )
            self._json_handle.flush()

        if self.quiet and self.log_file is None:
            return

        if normalized == "SUCCESS":
            log_level = SUCCESS
        elif normalized == "DEBUG":
            log_level = logging.DEBUG
        elif normalized == "WARNING":
            log_level = logging.WARNING
        elif normalized == "ERROR":
            log_level = logging.ERROR
        else:
            log_level = logging.INFO

        parts = [logging.getLevelName(log_level).upper(), event]
        if "message" in value:
            parts.append(str(value["message"]))
        for key in sorted(value):
            if key in {
                "timestamp",
                "event",
                "run_id",
                "project",
                "root",
                "message",
                "stage_id",
                "parent_stage_id",
            }:
                continue
            parts.append(f"{key}={value[key]}")
        self._logger.log(log_level, " ".join(str(part) for part in parts))

    def stage_start(
        self, stage_id: str, parent_stage_id: str | None = None, **counts: Any
    ) -> None:
        self.event(
            f"{stage_id}.start",
            level="INFO",
            stage_id=stage_id,
            parent_stage_id=parent_stage_id,
            counts=counts,
            message=f"Starting {stage_id}",
        )

    def stage_complete(
        self, stage_id: str, parent_stage_id: str | None = None, **counts: Any
    ) -> None:
        self.event(
            f"{stage_id}.complete",
            level="SUCCESS",
            stage_id=stage_id,
            parent_stage_id=parent_stage_id,
            counts=counts,
            message=f"Completed {stage_id}",
        )

    def file_event(
        self,
        *,
        path: str | os.PathLike[str],
        file_type: str,
        reader_name: str,
        status: str,
        phase: str,
        **fields: Any,
    ) -> None:
        relative_path = str(path)
        if hasattr(path, "as_posix"):
            relative_path = (
                os.path.relpath(str(path), self.root)
                if os.path.isabs(str(path))
                else str(path)
            )
        payload = {
            "file": relative_path,
            "language": file_type,
            "reader": reader_name,
            "status": status,
            "phase": phase,
        }
        payload.update(fields)
        level = "INFO"
        if status == "failed":
            level = "ERROR"
        elif status == "partial":
            level = "WARNING"
        elif status == "skipped":
            level = "WARNING"
        elif status == "complete":
            level = "SUCCESS"
        self.event(f"file.{status}", level=level, **payload)

    def render_header(self) -> None:
        if self.quiet or self.no_progress:
            return
        if self._terminal_enabled:
            self._print_safe("╭──────────────────────────────────────────────────────╮")
            self._print_safe("│ BARKLY LABS · BARKLY DOCS                           │")
            self._print_safe("│ Static Source Analysis & Documentation              │")
            self._print_safe("╰──────────────────────────────────────────────────────╯")
            self._print_safe("")
            self._print_safe(f"Project: {self.project_name}")
            self._print_safe(f"Root:    {self.root}")
            self._print_safe("")
        else:
            self._print_safe(
                f"BARKLY LABS · BARKLY DOCS | {self.project_name} | {self.root}"
            )

    def render_progress(
        self,
        *,
        stage: str,
        current: int | None = None,
        total: int | None = None,
        current_file: str | None = None,
        counts: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if self.quiet or self.no_progress:
            return
        if not self._terminal_enabled:
            if current_file or stage:
                self._print_safe(
                    f"[{stage}] {current_file or 'processing'} ({current or 0}/{total or 0})"
                )
            return
        if total is not None and total > 0:
            percentage = int((current or 0) / total * 100) if current is not None else 0
            filled = max(0, min(20, int((percentage / 100) * 20)))
            bar = "█" * filled + "░" * (20 - filled)
            line = f"{bar} {percentage}%"
        else:
            line = "⏳ working"
        info = [f"Stage: {stage}"]
        if current is not None and total is not None:
            info.append(f"Files: {current}/{total}")
        if current_file:
            info.append(f"Current: {current_file}")
        if counts:
            for key, value in counts.items():
                if isinstance(value, (int, float)):
                    info.append(f"{key.title()}: {value}")
        self._print_safe(f"\r{line} | {' | '.join(info)}", end="", flush=True)

    def clear_progress(self) -> None:
        if self.quiet or self.no_progress or not self._terminal_enabled:
            return
        print("\r" + " " * 140 + "\r", end="", flush=True)

    def final_report(
        self,
        *,
        result: Any,
        output_dir: str | None = None,
        project: Any | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        if self.quiet and self.log_file is None:
            return
        self._print_safe("")
        self._print_safe("╭──────────────────────────────────────────────╮")
        self._print_safe("│ BARKLY DOCS · ANALYSIS REPORT                │")
        self._print_safe("╰──────────────────────────────────────────────╯")
        self._print_safe("")
        self._print_safe(f"Project: {self.project_name}")
        if project is not None:
            self._print_safe(
                f"Status:  {'COMPLETED' if not errors else 'COMPLETED WITH WARNINGS'}"
            )
        self._print_safe("")
        self._print_safe("Source files")
        self._print_safe(
            f"  Discovered: {len(result.processed_files) + len(result.skipped_files) if result is not None else 0}"
        )
        self._print_safe(
            f"  Analyzed:   {len(result.processed_files) if result is not None else 0}"
        )
        self._print_safe(
            f"  Skipped:    {len(result.skipped_files) if result is not None else 0}"
        )
        self._print_safe(
            f"  Failed:     {len(result.errors) if result is not None else 0}"
        )
        self._print_safe("")
        if project is not None:
            summary = project.summary()
            self._print_safe("Declarations")
            self._print_safe(f"  Classes:      {summary.get('classes', 0)}")
            self._print_safe(f"  Functions:    {summary.get('functions', 0)}")
            self._print_safe(f"  Methods:      {summary.get('methods', 0)}")
            self._print_safe(f"  Relationships:{summary.get('relationships', 0)}")
            self._print_safe("")
        if output_dir is not None:
            self._print_safe(f"Output: {output_dir}")
        if warnings:
            self._print_safe(f"Warnings: {len(warnings)}")
        if errors:
            self._print_safe(f"Errors: {len(errors)}")
        self._print_safe("")

    def close(self) -> None:
        if self._json_handle is not None:
            self._json_handle.close()
        for handler in list(self._logger.handlers):
            handler.flush()
            handler.close()
        self._logger.handlers.clear()


def build_terminal(
    *,
    project_name: str,
    root: str,
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
    no_progress: bool = False,
    log_file: str | Path | None = None,
    log_format: str = "text",
) -> BarklyTerminal:
    return BarklyTerminal(
        project_name=project_name,
        root=root,
        quiet=quiet,
        verbose=verbose,
        no_color=no_color,
        no_progress=no_progress,
        log_file=log_file,
        log_format=log_format,
    )


class _TextFormatter(logging.Formatter):
    def __init__(self, color: bool = True) -> None:
        super().__init__("%(message)s")
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        color = {
            logging.DEBUG: "\033[36m",
            logging.INFO: "\033[37m",
            SUCCESS: "\033[32m",
            logging.WARNING: "\033[33m",
            logging.ERROR: "\033[31m",
        }
        prefix = color.get(record.levelno, "") if self.color else ""
        suffix = "\033[0m" if self.color else ""
        return f"{prefix}{super().format(record)}{suffix}"
