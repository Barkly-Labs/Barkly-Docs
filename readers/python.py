"""
Barkly Docs
Python Reader

Static Python source analysis using Python's standard-library AST.

The reader translates Python source code into the shared Barkly
Project Model.

IMPORTANT:
- Source code is never imported.
- Source code is never executed.
- Analysis is deterministic.
- Syntax errors are recorded as warnings instead of crashing
  the entire project analysis.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from ..model.project import (
    ClassNode,
    FileNode,
    FunctionNode,
    ImportNode,
    MethodNode,
    ModuleNode,
    Project,
    VariableNode,
)

from .base import LanguageReader


class PythonReader(LanguageReader):
    """
    Static reader for Python source files.
    """

    language = "Python"
    extensions = (".py", ".pyw")

    # ============================================================
    # READER INTERFACE
    # ============================================================

    def can_read(self, path: str | Path) -> bool:
        """
        Return True when this reader supports the supplied file.
        """
        return Path(path).suffix.lower() in self.extensions

    def analyze(
        self,
        path: str | Path,
        project: Project | None = None,
    ) -> Project:
        """
        Analyze a Python file.

        If a Project is supplied, discovered structures are added
        to that project.

        Otherwise a new Project is created.
        """
        source_path = Path(path)

        if project is None:
            project = Project(
                name=source_path.stem,
                root=str(source_path.parent),
            )

        self.read(source_path, project)

        return project

    def read(
        self,
        path: str | Path,
        project: Project,
    ) -> FileNode:
        """
        Read and statically analyze one Python file.
        """
        source_path = Path(path)

        # --------------------------------------------------------
        # READ SOURCE
        # --------------------------------------------------------

        try:
            source = source_path.read_text(encoding="utf-8")

        except UnicodeDecodeError:
            source = source_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            project.warnings.append(
                f"Python reader used replacement decoding for "
                f"{source_path}"
            )

        except OSError as exc:
            project.warnings.append(
                f"Could not read Python file {source_path}: {exc}"
            )

            file_node = FileNode(
                path=str(source_path),
                language=self.language,
            )

            project.add_file(file_node)

            return file_node

        # --------------------------------------------------------
        # FILE NODE
        # --------------------------------------------------------

        file_node = FileNode(
            path=str(source_path),
            language=self.language,
            size=len(source.encode("utf-8")),
        )

        project.add_file(file_node)

        # --------------------------------------------------------
        # PARSE AST
        # --------------------------------------------------------

        try:
            tree = ast.parse(
                source,
                filename=str(source_path),
                type_comments=True,
            )

        except SyntaxError as exc:
            project.warnings.append(
                f"Could not parse Python file {source_path}: "
                f"{exc.msg} at line {exc.lineno}"
            )

            file_node.metadata["parse_error"] = {
                "message": exc.msg,
                "line": exc.lineno,
                "column": exc.offset,
            }

            return file_node

        # --------------------------------------------------------
        # MODULE
        # --------------------------------------------------------

        module_name = self._module_name(source_path)

        module_node = ModuleNode(
            name=module_name,
            path=str(source_path),
            language=self.language,
            documentation=ast.get_docstring(tree),
            metadata={
                "parser": "python.ast",
                "source": "static",
            },
        )

        project.add_module(module_node)

        file_node.modules.append(module_name)

        # --------------------------------------------------------
        # MODULE CONTENT
        # --------------------------------------------------------

        self._read_module_body(
            tree.body,
            source_path,
            project,
            file_node,
            module_node,
        )

        return file_node

    # ============================================================
    # MODULE
    # ============================================================

    def _read_module_body(
        self,
        nodes: list[ast.stmt],
        path: Path,
        project: Project,
        file_node: FileNode,
        module_node: ModuleNode,
    ) -> None:
        """
        Read declarations from a Python module.
        """

        for node in nodes:

            # ----------------------------------------------------
            # FUNCTIONS
            # ----------------------------------------------------

            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                function = self._function_node(
                    node,
                    path,
                    class_name=None,
                )

                project.functions.append(function)
                file_node.functions.append(function.name)
                module_node.functions.append(function.name)

            # ----------------------------------------------------
            # CLASSES
            # ----------------------------------------------------

            elif isinstance(node, ast.ClassDef):
                class_node = self._class_node(
                    node,
                    path,
                    project,
                    file_node,
                    module_node,
                )

                project.classes.append(class_node)
                file_node.classes.append(class_node.name)
                module_node.classes.append(class_node.name)

            # ----------------------------------------------------
            # IMPORTS
            # ----------------------------------------------------

            elif isinstance(node, ast.Import):
                self._read_import(
                    node,
                    path,
                    project,
                    module_node,
                )

            elif isinstance(node, ast.ImportFrom):
                self._read_import(
                    node,
                    path,
                    project,
                    module_node,
                )

            # ----------------------------------------------------
            # VARIABLES
            # ----------------------------------------------------

            elif isinstance(
                node,
                (ast.Assign, ast.AnnAssign),
            ):
                self._read_variables(
                    node,
                    path,
                    project,
                )

    # ============================================================
    # FUNCTIONS / METHODS
    # ============================================================

    def _function_node(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        path: Path,
        class_name: str | None,
    ) -> FunctionNode | MethodNode:
        """
        Convert a Python function or method into a Barkly node.
        """

        parameters = [
            self._format_argument(argument)
            for argument in (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
            )
        ]

        # *args
        if node.args.vararg:
            parameters.append(
                "*" + self._format_argument(node.args.vararg)
            )

        # **kwargs
        if node.args.kwarg:
            parameters.append(
                "**" + self._format_argument(node.args.kwarg)
            )

        decorators = [
            self._safe_unparse(decorator)
            for decorator in node.decorator_list
        ]

        return_type = (
            self._safe_unparse(node.returns)
            if node.returns is not None
            else None
        )

        metadata: dict[str, Any] = {
            "node_type": type(node).__name__,
            "source": "static",
        }

        if node.type_comment:
            metadata["type_comment"] = node.type_comment

        # --------------------------------------------------------
        # METHOD
        # --------------------------------------------------------

        if class_name is not None:
            return MethodNode(
                name=node.name,
                path=str(path),
                language=self.language,
                parameters=parameters,
                return_type=return_type,
                decorators=decorators,
                documentation=ast.get_docstring(node),
                line_start=getattr(node, "lineno", None),
                line_end=getattr(node, "end_lineno", None),
                async_function=isinstance(
                    node,
                    ast.AsyncFunctionDef,
                ),
                class_name=class_name,
                metadata=metadata,
            )

        # --------------------------------------------------------
        # FUNCTION
        # --------------------------------------------------------

        return FunctionNode(
            name=node.name,
            path=str(path),
            language=self.language,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            documentation=ast.get_docstring(node),
            line_start=getattr(node, "lineno", None),
            line_end=getattr(node, "end_lineno", None),
            async_function=isinstance(
                node,
                ast.AsyncFunctionDef,
            ),
            metadata=metadata,
        )

    # ============================================================
    # CLASSES
    # ============================================================

    def _class_node(
        self,
        node: ast.ClassDef,
        path: Path,
        project: Project,
        file_node: FileNode,
        module_node: ModuleNode,
    ) -> ClassNode:
        """
        Convert a Python class into a Barkly ClassNode.
        """

        bases = [
            self._safe_unparse(base)
            for base in node.bases
        ]

        decorators = [
            self._safe_unparse(decorator)
            for decorator in node.decorator_list
        ]

        class_node = ClassNode(
            name=node.name,
            path=str(path),
            language=self.language,
            bases=bases,
            decorators=decorators,
            documentation=ast.get_docstring(node),
            line_start=getattr(node, "lineno", None),
            line_end=getattr(node, "end_lineno", None),
            metadata={
                "node_type": "ClassDef",
                "source": "static",
            },
        )

        # --------------------------------------------------------
        # CLASS MEMBERS
        # --------------------------------------------------------

        for child in node.body:

            # ----------------------------------------------------
            # METHODS
            # ----------------------------------------------------

            if isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                method = self._function_node(
                    child,
                    path,
                    class_name=node.name,
                )

                project.methods.append(method)

                class_node.methods.append(
                    method.name
                )

            # ----------------------------------------------------
            # CLASS ATTRIBUTES
            # ----------------------------------------------------

            elif isinstance(
                child,
                (ast.Assign, ast.AnnAssign),
            ):
                attributes = self._assignment_names(child)

                for name in attributes:
                    class_node.attributes.append(name)

        return class_node

    # ============================================================
    # IMPORTS
    # ============================================================

    def _read_import(
        self,
        node: ast.Import | ast.ImportFrom,
        path: Path,
        project: Project,
        module_node: ModuleNode,
    ) -> None:
        """
        Convert Python imports into ImportNode objects.
        """

        if isinstance(node, ast.Import):

            for alias in node.names:
                imported_name = alias.name

                import_node = ImportNode(
                    source_file=str(path),
                    target=imported_name,
                    language=self.language,
                    names=[imported_name],
                    alias=alias.asname,
                    metadata={
                        "kind": "import",
                        "level": 0,
                    },
                )

                project.add_import(import_node)

                module_node.imports.append(
                    imported_name
                )

        else:
            module_name = node.module or ""

            for alias in node.names:
                imported_name = (
                    f"{'.' * node.level}"
                    f"{module_name}"
                )

                if alias.name != "*":
                    if imported_name:
                        imported_name += "."

                    imported_name += alias.name

                import_node = ImportNode(
                    source_file=str(path),
                    target=imported_name,
                    language=self.language,
                    names=[alias.name],
                    alias=alias.asname,
                    metadata={
                        "kind": "from_import",
                        "level": node.level,
                        "module": node.module,
                    },
                )

                project.add_import(import_node)

                module_node.imports.append(
                    imported_name
                )

    # ============================================================
    # VARIABLES
    # ============================================================

    def _read_variables(
        self,
        node: ast.Assign | ast.AnnAssign,
        path: Path,
        project: Project,
    ) -> None:
        """
        Convert meaningful Python assignments into VariableNodes.
        """

        names = self._assignment_names(node)

        annotation = None
        value = None

        if isinstance(node, ast.AnnAssign):
            annotation = self._safe_unparse(
                node.annotation
            )

            if node.value is not None:
                value = self._safe_unparse(
                    node.value
                )

        elif isinstance(node, ast.Assign):
            if node.value is not None:
                value = self._safe_unparse(
                    node.value
                )

        for name in names:

            # Python convention:
            # ALL_CAPS names are treated as constants.
            constant = (
                name.isupper()
                and any(character.isalpha() for character in name)
            )

            project.variables.append(
                VariableNode(
                    name=name,
                    path=str(path),
                    language=self.language,
                    type=annotation,
                    value=value,
                    constant=constant,
                    line=getattr(node, "lineno", None),
                    metadata={
                        "source": "static",
                    },
                )
            )

    # ============================================================
    # HELPERS
    # ============================================================

    def _assignment_names(
        self,
        node: ast.Assign | ast.AnnAssign,
    ) -> list[str]:
        """
        Extract variable names from an assignment.
        """

        targets: list[ast.expr] = []

        if isinstance(node, ast.Assign):
            targets = node.targets

        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]

        names: list[str] = []

        for target in targets:

            if isinstance(target, ast.Name):
                names.append(target.id)

            elif isinstance(target, (ast.Tuple, ast.List)):
                for element in target.elts:
                    if isinstance(element, ast.Name):
                        names.append(element.id)

        return names

    def _format_argument(
        self,
        argument: ast.arg,
    ) -> str:
        """
        Format a Python function parameter while preserving
        its annotation when available.
        """

        name = argument.arg

        if argument.annotation is None:
            return name

        annotation = self._safe_unparse(
            argument.annotation
        )

        return f"{name}: {annotation}"

    def _safe_unparse(
        self,
        node: ast.AST,
    ) -> str:
        """
        Convert an AST expression back into readable source.

        ast.unparse is deterministic and does not execute code.
        """

        try:
            return ast.unparse(node)

        except Exception:
            return "<unavailable>"

    def _module_name(
        self,
        path: Path,
    ) -> str:
        """
        Produce a stable module name from a Python path.
        """

        if path.name == "__init__.py":
            return path.parent.name

        return path.stem
