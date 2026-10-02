"""
BARKLY DOCS
JSON Reader

Static JSON data-file analysis using Python's standard library json module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from model.project import DataNode, FileNode, ModuleNode, Project

from .base import LanguageReader, ReaderResult


class JSONReader(LanguageReader):
    """Static reader for JSON data files."""

    language = "JSON"
    extensions = (".json",)
    version = "0.1.0"

    def read(self, path: Path, project: Project) -> ReaderResult:
        path = Path(path)
        warnings: list[str] = []
        errors: list[str] = []

        try:
            source = self.read_text(path)
        except OSError as exc:
            message = f"Could not read JSON file {path}: {exc}"
            errors.append(message)
            return ReaderResult(
                success=False,
                project=project,
                warnings=warnings,
                errors=errors,
                metadata={
                    "language": self.language,
                    "reader_version": self.version,
                    "path": str(path),
                },
            )

        file_node = FileNode(
            path=str(path),
            language=self.language,
            size=len(source.encode("utf-8")),
        )
        project.add_file(file_node)

        module_name = path.stem or path.name
        module_node = ModuleNode(
            name=module_name,
            path=str(path),
            language=self.language,
            documentation=None,
            metadata={
                "parser": "json",
                "source": "static",
            },
        )
        project.add_module(module_node)
        file_node.modules.append(module_name)

        try:
            payload = json.loads(source)
        except json.JSONDecodeError as exc:
            message = f"Could not parse JSON file {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}"
            warnings.append(message)
            file_node.metadata["parse_error"] = {
                "message": exc.msg,
                "line": exc.lineno,
                "column": exc.colno,
            }
            return ReaderResult(
                success=False,
                project=project,
                warnings=warnings,
                errors=errors,
                metadata={
                    "language": self.language,
                    "reader_version": self.version,
                    "path": str(path),
                    "parse_error": True,
                },
            )

        self._add_json_values(project, file_node, path, payload, path_name="$")

        return ReaderResult(
            success=True,
            project=project,
            warnings=warnings,
            errors=errors,
            metadata={
                "language": self.language,
                "reader_version": self.version,
                "path": str(path),
                "parser": "json",
                "static_analysis": True,
                "data_nodes": len(project.data),
            },
        )

    def _primitive_type(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int | float):
            return "number"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    def _display_name(self, path: str) -> str:
        if path == "$":
            return "$"
        if path.startswith("$"):
            path = path[1:]
        if path.startswith("."):
            path = path[1:]
        return path or "$"

    def _add_json_values(
        self,
        project: Project,
        file_node: FileNode,
        file_path: Path,
        value: Any,
        *,
        path_name: str,
    ) -> None:
        if isinstance(value, dict):
            keys = list(value.keys())
            node = DataNode(
                name=self._display_name(path_name),
                path=str(file_path),
                language=self.language,
                kind="object",
                value_type="object",
                keys=[str(item) for item in keys],
                metadata={
                    "file": str(file_path),
                    "path": path_name,
                },
            )
            project.add_data(node)
            for key, child in value.items():
                child_path = f"{path_name}.{key}" if path_name != "$" else f"$.{key}"
                self._add_json_values(
                    project, file_node, file_path, child, path_name=child_path
                )
            return

        if isinstance(value, list):
            keys = [f"[{index}]" for index in range(len(value))]
            node = DataNode(
                name=self._display_name(path_name),
                path=str(file_path),
                language=self.language,
                kind="array",
                value_type="array",
                keys=keys,
                metadata={
                    "file": str(file_path),
                    "path": path_name,
                    "length": len(value),
                },
            )
            project.add_data(node)
            for index, child in enumerate(value):
                child_path = f"{path_name}[{index}]"
                self._add_json_values(
                    project, file_node, file_path, child, path_name=child_path
                )
            return

        node = DataNode(
            name=self._display_name(path_name),
            path=str(file_path),
            language=self.language,
            kind=self._primitive_type(value),
            value_type=self._primitive_type(value),
            value=None if value is None else str(value),
            metadata={
                "file": str(file_path),
                "path": path_name,
            },
        )
        project.add_data(node)
