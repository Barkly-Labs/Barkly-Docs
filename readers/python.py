"""
Barkly Docs
Python Reader

Statically analyzes Python source files and translates them
into the Barkly Project Model.

This reader NEVER imports or executes the target project.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .base import LanguageReader, ReaderResult

from ..model.project import (
    Project,
    FileNode,
    ModuleNode,
    FunctionNode,
    MethodNode,
    ClassNode,
    VariableNode,
    ImportNode,
    DocumentationNode,
)


class PythonReader(LanguageReader):
    """
    Reader for Python source files.
    """

    language = "Python"
    extensions = (".py", ".pyw")
    version = "0.1.0"

    # ========================================================
    # READ
    # ========================================================

    def read(
        self,
        path: Path,
        project: Project,
    ) -> ReaderResult:

        warnings: list[str] = []
        errors: list[str] = []

        try:
            source = self.read_text(path)

        except OSError as exc:
            return ReaderResult(
                success=False,
                project=project,
                errors=[
                    f"Unable to read {path}: {exc}"
                ],
            )

        # ----------------------------------------------------
        # PARSE
        # ----------------------------------------------------

        try:
            tree = ast.parse(
                source,
                filename=str(path),
            )

        except SyntaxError as exc:
            return ReaderResult(
                success=False,
                project=project,
                errors=[
                    (
                        f"Python syntax error in {path}: "
                        f"line {exc.lineno}: {exc.msg}"
                    )
                ],
            )

        # ----------------------------------------------------
        # FILE
        # ----------------------------------------------------

        file_node = FileNode(
            path=str(path),
            language="Python",
        )

        project.files.append(file_node)

        # ----------------------------------------------------
        # MODULE
        # ----------------------------------------------------

        module_name = self._module_name(path)

        module = ModuleNode(
            name=module_name,
            path=str(path),
        )

        project.modules.append(module)

        # ----------------------------------------------------
        # MODULE DOCSTRING
        # ----------------------------------------------------

        module_doc = ast.get_docstring(tree)

        if module_doc:
            documentation = DocumentationNode(
                name=f"{module_name} documentation",
                content=module_doc,
                source_file=str(path),
            )

            project.documentation.append(documentation)

        # ----------------------------------------------------
        # WALK TOP LEVEL
        # ----------------------------------------------------

        for node in tree.body:
            self._read_node(
                node=node,
                project=project,
                path=path,
                module_name=module_name,
                parent_class=None,
                warnings=warnings,
            )

        return ReaderResult(
            success=True,
            project=project,
            warnings=warnings,
            metadata={
                "language": "Python",
                "file": str(path),
                "module": module_name,
            },
        )

    # ========================================================
    # NODE DISPATCH
    # ========================================================

    def _read_node(
        self,
        node: ast.AST,
        project: Project,
        path: Path,
        module_name: str,
        parent_class: str | None,
        warnings: list[str],
    ) -> None:

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._read_function(
                node,
                project,
                path,
                parent_class,
            )
            return

        if isinstance(node, ast.ClassDef):
            self._read_class(
                node,
                project,
                path,
                module_name,
                warnings,
            )
            return

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            self._read_import(
                node,
                project,
                path,
            )
            return

        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            self._read_variable(
                node,
                project,
                path,
            )
            return

    # ========================================================
    # FUNCTIONS
    # ========================================================

    def _read_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        project: Project,
        path: Path,
        parent_class: str | None,
    ) -> None:

        docstring = ast.get_docstring(node)

        if parent_class:
            method = MethodNode(
                name=node.name,
                class_name=parent_class,
                source_file=str(path),
                line=node.lineno,
                documentation=docstring,
            )

            project.methods.append(method)

        else:
            function = FunctionNode(
                name=node.name,
                source_file=str(path),
                line=node.lineno,
                documentation=docstring,
                async_function=isinstance(
                    node,
                    ast.AsyncFunctionDef,
                ),
            )

            project.functions.append(function)

            if docstring:
                project.documentation.append(
                    DocumentationNode(
                        name=f"{node.name} documentation",
                        content=docstring,
                        source_file=str(path),
                    )
                )

    # ========================================================
    # CLASSES
    # ========================================================

    def _read_class(
        self,
        node: ast.ClassDef,
        project: Project,
        path: Path,
        module_name: str,
        warnings: list[str],
    ) -> None:

        bases = []

        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                warnings.append(
                    f"Could not resolve base class "
                    f"for {node.name}"
                )

        docstring = ast.get_docstring(node)

        class_node = ClassNode(
            name=node.name,
            module=module_name,
            source_file=str(path),
            line=node.lineno,
            documentation=docstring,
            bases=bases,
        )

        project.classes.append(class_node)

        if docstring:
            project.documentation.append(
                DocumentationNode(
                    name=f"{node.name} documentation",
                    content=docstring,
                    source_file=str(path),
                )
            )

        # Read class contents.
        for child in node.body:
            self._read_node(
                node=child,
                project=project,
                path=path,
                module_name=module_name,
                parent_class=node.name,
                warnings=warnings,
            )

    # ========================================================
    # IMPORTS
    # ========================================================

    def _read_import(
        self,
        node: ast.Import | ast.ImportFrom,
        project: Project,
        path: Path,
    ) -> None:

        if isinstance(node, ast.Import):

            for alias in node.names:

                project.imports.append(
                    ImportNode(
                        name=alias.name,
                        alias=alias.asname,
                        source_file=str(path),
                        line=node.lineno,
                    )
                )

        else:

            module = node.module or ""

            for alias in node.names:

                name = (
                    f"{module}.{alias.name}"
                    if module
                    else alias.name
                )

                project.imports.append(
                    ImportNode(
                        name=name,
                        alias=alias.asname,
                        source_file=str(path),
                        line=node.lineno,
                    )
                )

    # ========================================================
    # VARIABLES
    # ========================================================

    def _read_variable(
        self,
        node: ast.Assign | ast.AnnAssign,
        project: Project,
        path: Path,
    ) -> None:

        if isinstance(node, ast.Assign):
            targets = node.targets

        else:
            targets = [node.target]

        for target in targets:

            if isinstance(target, ast.Name):

                project.variables.append(
                    VariableNode(
                        name=target.id,
                        source_file=str(path),
                        line=node.lineno,
                    )
                )

    # ========================================================
    # MODULE NAME
    # ========================================================

    @staticmethod
    def _module_name(path: Path) -> str:

        if path.name == "__init__.py":
            return path.parent.name

        return path.stem