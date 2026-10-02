"""
BARKLY DOCS
Python Reader

Static Python source analysis using Python's standard-library AST.

The reader translates Python source code into the shared Barkly
Project Model.

IMPORTANT:
- Source code is never imported.
- Source code is never executed.
- Analysis is deterministic.
- Syntax errors are reported through ReaderResult.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from model.project import (
    ClassNode,
    FileNode,
    FunctionNode,
    ImportNode,
    MethodNode,
    ModuleNode,
    Project,
    RelationshipNode,
    VariableNode,
)

from .base import LanguageReader, ReaderResult


class PythonReader(LanguageReader):
    """
    Static reader for Python source files.
    """

    language = "Python"
    extensions = (".py", ".pyw")
    version = "0.1.0"

    # ============================================================
    # READ
    # ============================================================

    def read(
        self,
        path: Path,
        project: Project,
    ) -> ReaderResult:
        """
        Analyze one Python source file and add the discovered
        structures to the supplied Project.

        The target Python project is NEVER imported or executed.
        """

        path = Path(path)

        warnings: list[str] = []
        errors: list[str] = []

        # --------------------------------------------------------
        # READ SOURCE
        # --------------------------------------------------------

        try:
            source = self.read_text(path)

        except OSError as exc:
            error = (
                f"Could not read Python file "
                f"{path}: {exc}"
            )

            errors.append(error)

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

        # --------------------------------------------------------
        # FILE NODE
        # --------------------------------------------------------

        file_node = FileNode(
            path=str(path),
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
                filename=str(path),
                type_comments=True,
            )

        except SyntaxError as exc:
            warning = (
                f"Could not parse Python file "
                f"{path}: {exc.msg}"
            )

            if exc.lineno is not None:
                warning += f" at line {exc.lineno}"

            warnings.append(warning)

            file_node.metadata["parse_error"] = {
                "message": exc.msg,
                "line": exc.lineno,
                "column": exc.offset,
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

        # --------------------------------------------------------
        # MODULE
        # --------------------------------------------------------

        module_name = self._module_name(path)

        module_node = ModuleNode(
            name=module_name,
            path=str(path),
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
            nodes=tree.body,
            path=path,
            project=project,
            file_node=file_node,
            module_node=module_node,
        )

        # --------------------------------------------------------
        # RESULT
        # --------------------------------------------------------

        return ReaderResult(
            success=True,
            project=project,
            warnings=warnings,
            errors=errors,
            metadata={
                "language": self.language,
                "reader_version": self.version,
                "path": str(path),
                "parser": "python.ast",
                "static_analysis": True,
            },
        )

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
                    node=node,
                    path=path,
                    class_name=None,
                )

                project.add_function(function)
                self._record_call_relationships(
                    node=node,
                    path=path,
                    project=project,
                    source_name=node.name,
                )
                file_node.functions.append(function.name)
                module_node.functions.append(function.name)

            # ----------------------------------------------------
            # CLASSES
            # ----------------------------------------------------

            elif isinstance(node, ast.ClassDef):

                class_node = self._class_node(
                    node=node,
                    path=path,
                    project=project,
                    file_node=file_node,
                    module_node=module_node,
                )

                project.add_class(class_node)
                file_node.classes.append(class_node.name)
                module_node.classes.append(class_node.name)

            # ----------------------------------------------------
            # IMPORTS
            # ----------------------------------------------------

            elif isinstance(node, ast.Import):

                self._read_import(
                    node=node,
                    path=path,
                    project=project,
                    module_node=module_node,
                )

            elif isinstance(node, ast.ImportFrom):

                self._read_import(
                    node=node,
                    path=path,
                    project=project,
                    module_node=module_node,
                )

            # ----------------------------------------------------
            # VARIABLES
            # ----------------------------------------------------

            elif isinstance(
                node,
                (ast.Assign, ast.AnnAssign),
            ):

                self._read_variables(
                    node=node,
                    path=path,
                    project=project,
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

        source_name = (
            f"{class_name}.{node.name}"
            if class_name is not None
            else node.name
        )

        parameters = [
            self._format_argument(argument)
            for argument in (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
            )
        ]

        # --------------------------------------------------------
        # *args
        # --------------------------------------------------------

        if node.args.vararg:

            parameters.append(
                "*" + self._format_argument(
                    node.args.vararg
                )
            )

        # --------------------------------------------------------
        # **kwargs
        # --------------------------------------------------------

        if node.args.kwarg:

            parameters.append(
                "**" + self._format_argument(
                    node.args.kwarg
                )
            )

        # --------------------------------------------------------
        # DECORATORS
        # --------------------------------------------------------

        decorators = [
            self._safe_unparse(decorator)
            for decorator in node.decorator_list
        ]

        # --------------------------------------------------------
        # RETURN TYPE
        # --------------------------------------------------------

        return_type = (
            self._safe_unparse(node.returns)
            if node.returns is not None
            else None
        )

        # --------------------------------------------------------
        # METADATA
        # --------------------------------------------------------

        metadata: dict[str, Any] = {
            "node_type": type(node).__name__,
            "source": "static",
            "line_start": getattr(
                node,
                "lineno",
                None,
            ),
            "line_end": getattr(
                node,
                "end_lineno",
                None,
            ),
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
                line_start=getattr(
                    node,
                    "lineno",
                    None,
                ),
                line_end=getattr(
                    node,
                    "end_lineno",
                    None,
                ),
                async_function=isinstance(
                    node,
                    ast.AsyncFunctionDef,
                ),
                class_name=class_name,
                metadata={**metadata, "qualified_name": source_name},
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
            line_start=getattr(
                node,
                "lineno",
                None,
            ),
            line_end=getattr(
                node,
                "end_lineno",
                None,
            ),
            async_function=isinstance(
                node,
                ast.AsyncFunctionDef,
            ),
            metadata={**metadata, "qualified_name": source_name},
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
            line_start=getattr(
                node,
                "lineno",
                None,
            ),
            line_end=getattr(
                node,
                "end_lineno",
                None,
            ),
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
                    node=child,
                    path=path,
                    class_name=node.name,
                )

                project.add_method(method)
                self._record_call_relationships(
                    node=child,
                    path=path,
                    project=project,
                    source_name=f"{node.name}.{child.name}",
                )

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

                attributes = self._assignment_names(
                    child
                )

                for name in attributes:

                    class_node.attributes.append(
                        name
                    )

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

        # --------------------------------------------------------
        # import foo
        # --------------------------------------------------------

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

                project.add_import(
                    import_node
                )

                module_node.imports.append(
                    imported_name
                )

        # --------------------------------------------------------
        # from foo import bar
        # --------------------------------------------------------

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

                project.add_import(
                    import_node
                )

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
        Convert Python assignments into VariableNodes.
        """

        names = self._assignment_names(node)

        annotation = None
        value = None

        # --------------------------------------------------------
        # Annotated assignment
        # --------------------------------------------------------

        if isinstance(node, ast.AnnAssign):

            annotation = self._safe_unparse(
                node.annotation
            )

            if node.value is not None:

                value = self._safe_unparse(
                    node.value
                )

        # --------------------------------------------------------
        # Normal assignment
        # --------------------------------------------------------

        elif isinstance(node, ast.Assign):

            if node.value is not None:

                value = self._safe_unparse(
                    node.value
                )

        # --------------------------------------------------------
        # CREATE VARIABLES
        # --------------------------------------------------------

        for name in names:

            constant = (
                name.isupper()
                and any(
                    character.isalpha()
                    for character in name
                )
            )

            project.add_variable(
                VariableNode(
                    name=name,
                    path=str(path),
                    language=self.language,
                    type=annotation,
                    value=value,
                    constant=constant,
                    line=getattr(
                        node,
                        "lineno",
                        None,
                    ),
                    metadata={
                        "source": "static",
                    },
                )
            )

    # ============================================================
    # CALL RELATIONSHIPS
    # ============================================================

    def _record_call_relationships(
        self,
        node: ast.AST,
        path: Path,
        project: Project | None,
        source_name: str,
    ) -> None:
        """
        Record statically discovered function and method calls.

        This is intentionally conservative: it only records direct calls
        that are visible in the AST and does not execute the target code.
        """

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            target_name = self._call_target_name(child.func)
            if not target_name:
                continue

            # Resolve common instance/class-qualified calls within the caller's
            # class. For example, MyClass.run calling self.refresh() should
            # produce MyClass.run -> MyClass.refresh, not MyClass.run -> self.refresh.
            if source_name and "." in source_name:
                caller_class = source_name.rsplit(".", 1)[0]
                if target_name.startswith("self.") or target_name.startswith("cls."):
                    target_name = f"{caller_class}.{target_name.split('.', 1)[1]}"

            if project is None:
                continue

            project.add_relationship(
                RelationshipNode(
                    source=source_name,
                    target=target_name,
                    kind="calls",
                    source_file=str(path),
                    evidence="DETECTED",
                    source_location={
                        "line": getattr(child, "lineno", None),
                        "column": getattr(child, "col_offset", None),
                    },
                )
            )

    def _call_target_name(self, node: ast.AST | None) -> str | None:
        """Resolve a callable target name from a call expression."""

        if node is None:
            return None

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            attr_name = self._call_target_name(node.value)
            if attr_name:
                return f"{attr_name}.{node.attr}"
            return node.attr

        if isinstance(node, ast.Call):
            return self._call_target_name(node.func)

        return None

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

        if isinstance(node, ast.Assign):

            targets = node.targets

        else:

            targets = [node.target]

        names: list[str] = []

        for target in targets:

            if isinstance(
                target,
                ast.Name,
            ):

                names.append(
                    target.id
                )

            elif isinstance(
                target,
                (ast.Tuple, ast.List),
            ):

                for element in target.elts:

                    if isinstance(
                        element,
                        ast.Name,
                    ):

                        names.append(
                            element.id
                        )

        return names

    # ============================================================
    # ARGUMENT FORMATTING
    # ============================================================

    def _format_argument(
        self,
        argument: ast.arg,
    ) -> str:
        """
        Format a Python function parameter while preserving
        its annotation.
        """

        name = argument.arg

        if argument.annotation is None:
            return name

        annotation = self._safe_unparse(
            argument.annotation
        )

        return f"{name}: {annotation}"

    # ============================================================
    # SAFE AST UNPARSE
    # ============================================================

    def _safe_unparse(
        self,
        node: ast.AST,
    ) -> str:
        """
        Convert an AST node back into readable source text.

        ast.unparse() does not execute the target code.
        """

        try:
            return ast.unparse(node)

        except Exception:
            return "<unavailable>"

    # ============================================================
    # MODULE NAME
    # ============================================================

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