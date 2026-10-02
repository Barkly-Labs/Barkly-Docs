"""
BARKLY DOCS

JavaScript Reader

Static JavaScript source reader for Barkly Docs.

This reader does not execute JavaScript code. It extracts
structural information from JavaScript source files and maps
that information into the Barkly Project Model.

Design principle:

    JavaScript Source
        ↓
    JavaScript Reader
        ↓
    Barkly Project Model
        ↓
    Documentation / Graph / Website / CYN-X
"""

from __future__ import annotations

import re
from pathlib import Path

from model.project import (
    ClassNode,
    DocumentationNode,
    ExportNode,
    FileNode,
    FunctionNode,
    ImportNode,
    MethodNode,
    ModuleNode,
    Project,
    RelationshipNode,
    VariableNode,
)
from readers.base import LanguageReader, ReaderResult


class JavaScriptReader(LanguageReader):
    """
    Static reader for JavaScript source files.

    Supported:
        .js
        .mjs
        .cjs

    This is intentionally a lightweight structural reader.
    It does not execute JavaScript and does not require Node.js.
    """

    language = "JavaScript"
    extensions = (".js", ".mjs", ".cjs")
    version = "0.2.0"

    def read(self, path: Path, project: Project) -> ReaderResult:
        warnings: list[str] = []
        errors: list[str] = []

        # ------------------------------------------------------------
        # READ SOURCE
        # ------------------------------------------------------------

        try:
            source = self.read_text(path)
        except Exception as exc:
            return ReaderResult(
                success=False,
                project=project,
                warnings=[],
                errors=[f"{path}: unable to read JavaScript source: {exc}"],
                metadata={
                    "language": self.language,
                    "reader_version": self.version,
                },
            )

        # ------------------------------------------------------------
        # FILE
        # ------------------------------------------------------------

        file_node = FileNode(
            path=str(path),
            language=self.language,
            size=len(source.encode("utf-8")),
        )

        project.add_file(file_node)

        # ------------------------------------------------------------
        # MODULE
        # ------------------------------------------------------------

        module_name = self._module_name(path)

        module_node = ModuleNode(
            name=module_name,
            path=str(path),
            language=self.language,
            documentation=self._extract_documentation(source),
            metadata={
                "javascript_file": True,
                "reader": self.version,
                "module_system": self._detect_module_system(source),
            },
        )

        project.add_module(module_node)

        # ------------------------------------------------------------
        # IMPORTS — ESM
        # ------------------------------------------------------------

        for match in self._IMPORT_FROM_RE.finditer(source):
            statement = match.group(0).strip()
            target = match.group("target")

            names = self._parse_import_names(match.group("names"))

            line = self._line_number(
                source,
                match.start(),
            )

            import_node = ImportNode(
                source_file=str(path),
                target=target,
                language=self.language,
                names=names,
                alias=None,
                metadata={
                    "javascript_statement": statement,
                    "line": line,
                    "module_system": "esm",
                },
            )

            project.add_import(import_node)

            project.add_relationship(
                RelationshipNode(
                    source=str(path),
                    target=target,
                    kind="imports",
                    source_file=str(path),
                    metadata={
                        "language": self.language,
                        "names": names,
                        "module_system": "esm",
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # IMPORTS — SIDE EFFECT ESM
        # ------------------------------------------------------------

        for match in self._IMPORT_SIDE_EFFECT_RE.finditer(source):
            statement = match.group(0).strip()
            target = match.group("target")

            line = self._line_number(
                source,
                match.start(),
            )

            import_node = ImportNode(
                source_file=str(path),
                target=target,
                language=self.language,
                names=[],
                alias=None,
                metadata={
                    "javascript_statement": statement,
                    "line": line,
                    "module_system": "esm",
                    "side_effect_only": True,
                },
            )

            project.add_import(import_node)

            project.add_relationship(
                RelationshipNode(
                    source=str(path),
                    target=target,
                    kind="imports",
                    source_file=str(path),
                    metadata={
                        "language": self.language,
                        "module_system": "esm",
                        "side_effect_only": True,
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # IMPORTS — COMMONJS require()
        # ------------------------------------------------------------

        for match in self._REQUIRE_RE.finditer(source):
            target = match.group("target")
            alias = match.group("alias")

            line = self._line_number(
                source,
                match.start(),
            )

            import_node = ImportNode(
                source_file=str(path),
                target=target,
                language=self.language,
                names=[],
                alias=alias,
                metadata={
                    "javascript_statement": match.group(0).strip(),
                    "line": line,
                    "module_system": "commonjs",
                },
            )

            project.add_import(import_node)

            project.add_relationship(
                RelationshipNode(
                    source=str(path),
                    target=target,
                    kind="imports",
                    source_file=str(path),
                    metadata={
                        "language": self.language,
                        "alias": alias,
                        "module_system": "commonjs",
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # EXPORTS — DECLARATIONS
        # ------------------------------------------------------------

        for match in self._EXPORT_DECLARATION_RE.finditer(source):
            name = match.group("name")
            kind = match.group("kind")

            default_export = bool(match.group("default"))

            line = self._line_number(
                source,
                match.start(),
            )

            export_node = ExportNode(
                source_file=str(path),
                name=name,
                language=self.language,
                kind=kind,
                metadata={
                    "line": line,
                    "default": default_export,
                    "javascript_kind": "declaration",
                },
            )

            project.add_export(export_node)

            project.add_relationship(
                RelationshipNode(
                    source=f"{path}:{name}",
                    target=name,
                    kind="exports",
                    source_file=str(path),
                    metadata={
                        "language": self.language,
                        "default": default_export,
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # EXPORTS — NAMED LISTS / RE-EXPORTS
        # ------------------------------------------------------------

        for match in self._EXPORT_LIST_RE.finditer(source):
            names = self._parse_export_names(match.group("names"))

            target = match.group("target")

            line = self._line_number(
                source,
                match.start(),
            )

            for name, alias in names:
                exported_name = alias or name

                export_node = ExportNode(
                    source_file=str(path),
                    name=exported_name,
                    language=self.language,
                    kind="named",
                    metadata={
                        "line": line,
                        "local_name": name,
                        "alias": alias,
                        "reexport_target": target,
                    },
                )

                project.add_export(export_node)

                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{name}",
                        target=target or exported_name,
                        kind="exports",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "alias": alias,
                            "reexport": bool(target),
                            "line": line,
                        },
                    )
                )

        # ------------------------------------------------------------
        # EXPORTS — CommonJS module.exports
        # ------------------------------------------------------------

        for match in self._MODULE_EXPORTS_RE.finditer(source):
            name = match.group("name")

            line = self._line_number(
                source,
                match.start(),
            )

            project.add_export(
                ExportNode(
                    source_file=str(path),
                    name=name,
                    language=self.language,
                    kind="commonjs",
                    metadata={
                        "line": line,
                        "javascript_kind": "module.exports",
                    },
                )
            )

            project.add_relationship(
                RelationshipNode(
                    source=f"{path}:{name}",
                    target=name,
                    kind="exports",
                    source_file=str(path),
                    metadata={
                        "language": self.language,
                        "module_system": "commonjs",
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # EXPORTS — CommonJS exports.foo
        # ------------------------------------------------------------

        for match in self._COMMONJS_EXPORT_RE.finditer(source):
            name = match.group("name")

            line = self._line_number(
                source,
                match.start(),
            )

            project.add_export(
                ExportNode(
                    source_file=str(path),
                    name=name,
                    language=self.language,
                    kind="commonjs",
                    metadata={
                        "line": line,
                        "javascript_kind": "exports.property",
                    },
                )
            )

            project.add_relationship(
                RelationshipNode(
                    source=f"{path}:{name}",
                    target=name,
                    kind="exports",
                    source_file=str(path),
                    metadata={
                        "language": self.language,
                        "module_system": "commonjs",
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # CLASSES
        # ------------------------------------------------------------

        for match in self._CLASS_RE.finditer(source):
            name = match.group("name")
            body = match.group("body") or ""

            line_start = self._line_number(
                source,
                match.start(),
            )

            line_end = self._line_number(
                source,
                match.end(),
            )

            methods = self._extract_class_methods(body)

            documentation = self._extract_jsdoc_before(
                source,
                match.start(),
            )

            node = ClassNode(
                name=name,
                path=str(path),
                language=self.language,
                bases=self._parse_extends(match.group("extends")),
                decorators=[],
                methods=methods,
                attributes=self._extract_class_fields(body),
                documentation=documentation,
                line_start=line_start,
                line_end=line_end,
                metadata={
                    "javascript_kind": "class",
                    "exported": bool(match.group("export")),
                    "default_export": bool(match.group("default")),
                    "line_start": line_start,
                    "line_end": line_end,
                },
            )

            project.add_class(node)

            # --------------------------------------------------------
            # CLASS INHERITANCE RELATIONSHIPS
            # --------------------------------------------------------

            for base in node.bases:
                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{name}",
                        target=base,
                        kind="inherits",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "javascript_kind": "class_inheritance",
                            "line": line_start,
                        },
                    )
                )

            # --------------------------------------------------------
            # CLASS METHODS
            # --------------------------------------------------------

            for method_match in self._CLASS_METHOD_RE.finditer(body):
                method_name = method_match.group("name")

                relative_start = match.start("body") + method_match.start()

                relative_end = match.start("body") + method_match.end()

                method_line_start = self._line_number(
                    source,
                    relative_start,
                )

                method_line_end = self._line_number(
                    source,
                    relative_end,
                )

                method_documentation = self._extract_jsdoc_before(
                    body,
                    method_match.start(),
                )

                method_node = MethodNode(
                    name=method_name,
                    path=str(path),
                    language=self.language,
                    parameters=self._parse_parameters(
                        method_match.group("parameters") or ""
                    ),
                    return_type=None,
                    decorators=[],
                    documentation=method_documentation,
                    line_start=method_line_start,
                    line_end=method_line_end,
                    class_name=name,
                    metadata={
                        "javascript_kind": "class_method",
                        "static": bool(method_match.group("static")),
                        "async": bool(method_match.group("async")),
                        "getter": bool(method_match.group("getter")),
                        "setter": bool(method_match.group("setter")),
                    },
                )

                project.add_method(method_node)

                # ----------------------------------------------------
                # CLASS → METHOD RELATIONSHIP
                # ----------------------------------------------------

                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{name}",
                        target=f"{path}:{method_name}",
                        kind="contains",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "javascript_kind": "class_method",
                            "line": method_line_start,
                        },
                    )
                )

        # ------------------------------------------------------------
        # NORMAL FUNCTIONS
        # ------------------------------------------------------------

        for match in self._FUNCTION_RE.finditer(source):
            name = match.group("name")

            line_start = self._line_number(
                source,
                match.start(),
            )

            line_end = self._line_number(
                source,
                match.end(),
            )

            documentation = self._extract_jsdoc_before(
                source,
                match.start(),
            )

            function_node = FunctionNode(
                name=name,
                path=str(path),
                language=self.language,
                parameters=self._parse_parameters(match.group("parameters") or ""),
                return_type=None,
                decorators=[],
                documentation=documentation,
                line_start=line_start,
                line_end=line_end,
                async_function=bool(match.group("async")),
                metadata={
                    "javascript_kind": "function",
                    "exported": bool(match.group("export")),
                    "default_export": bool(match.group("default")),
                    "generator": bool(match.group("generator")),
                },
            )

            project.add_function(function_node)

        # ------------------------------------------------------------
        # ARROW FUNCTIONS
        # ------------------------------------------------------------

        for match in self._ARROW_FUNCTION_RE.finditer(source):
            name = match.group("name")

            if match.group("parameters") is not None:
                raw_parameters = match.group("parameters")
            else:
                raw_parameters = match.group("single_parameter") or ""

            line_start = self._line_number(
                source,
                match.start(),
            )

            line_end = self._line_number(
                source,
                match.end(),
            )

            documentation = self._extract_jsdoc_before(
                source,
                match.start(),
            )

            function_node = FunctionNode(
                name=name,
                path=str(path),
                language=self.language,
                parameters=self._parse_parameters(raw_parameters),
                return_type=None,
                decorators=[],
                documentation=documentation,
                line_start=line_start,
                line_end=line_end,
                async_function=bool(match.group("async")),
                metadata={
                    "javascript_kind": "arrow_function",
                    "exported": False,
                },
            )

            project.add_function(function_node)

        # ------------------------------------------------------------
        # VARIABLES
        # ------------------------------------------------------------

        for match in self._VARIABLE_RE.finditer(source):
            keyword = match.group("keyword")
            name = match.group("name")
            value = match.group("value")

            line = self._line_number(
                source,
                match.start(),
            )

            project.add_variable(
                VariableNode(
                    name=name,
                    path=str(path),
                    language=self.language,
                    type=None,
                    value=(value.strip() if value else None),
                    constant=keyword == "const",
                    line=line,
                    metadata={
                        "javascript_kind": "variable",
                        "declaration": keyword,
                    },
                )
            )

        # ------------------------------------------------------------
        # DOCUMENTATION / JSDOC
        # ------------------------------------------------------------

        for match in self._JSDOC_RE.finditer(source):
            documentation = self._clean_jsdoc(match.group("doc"))

            if not documentation:
                continue

            line = self._line_number(
                source,
                match.start(),
            )

            project.add_documentation(
                DocumentationNode(
                    title=self._documentation_title(documentation),
                    path=str(path),
                    kind="jsdoc",
                    headings=[],
                    links=[],
                    metadata={
                        "language": self.language,
                        "line": line,
                        "text": documentation,
                    },
                )
            )

        # ------------------------------------------------------------
        # READER RESULT
        # ------------------------------------------------------------

        return ReaderResult(
            success=True,
            project=project,
            warnings=warnings,
            errors=errors,
            metadata={
                "language": self.language,
                "reader_version": self.version,
                "path": str(path),
                "parser": "static-regex-structural",
                "static_analysis": True,
                "module_system": self._detect_module_system(source),
            },
        )

    # ================================================================
    # REGEX PATTERNS
    # ================================================================

    _IMPORT_FROM_RE = re.compile(r"""(?m)^\s*
        import\s+
        (?P<names>.+?)
        \s+from\s+
        ["'](?P<target>[^"']+)["']
        \s*;?
        """)

    _IMPORT_SIDE_EFFECT_RE = re.compile(r"""(?m)^\s*
        import\s+
        ["'](?P<target>[^"']+)["']
        \s*;?
        """)

    _REQUIRE_RE = re.compile(r"""(?m)^\s*
        (?:(?:const|let|var)\s+)?
        (?P<alias>[A-Za-z_$][\w$]*)
        \s*=\s*
        require\(
            \s*["'](?P<target>[^"']+)["']
        \s*\)
        """)

    _EXPORT_DECLARATION_RE = re.compile(r"""(?m)^\s*
        export\s+
        (?P<default>default\s+)?
        (?P<kind>class|function|const|let|var)
        \s+
        (?P<name>[A-Za-z_$][\w$]*)
        """)

    _EXPORT_LIST_RE = re.compile(r"""(?m)^\s*
        export\s*
        \{\s*
        (?P<names>[^}]+)
        \s*\}
        (?:
            \s*from\s*
            ["'](?P<target>[^"']+)["']
        )?
        \s*;?
        """)

    _MODULE_EXPORTS_RE = re.compile(r"""(?m)^\s*
        module\.exports\s*=\s*
        (?P<name>[A-Za-z_$][\w$]*)
        """)

    _COMMONJS_EXPORT_RE = re.compile(r"""(?m)^\s*
        exports\.
        (?P<name>[A-Za-z_$][\w$]*)
        \s*=
        """)

    _CLASS_RE = re.compile(r"""(?s)
        (?P<export>export\s+)?
        (?P<default>default\s+)?
        class\s+
        (?P<name>[A-Za-z_$][\w$]*)
        (?:
            \s+extends\s+
            (?P<extends>[^{]+)
        )?
        \s*\{
            (?P<body>.*?)
        \}
        """)

    _CLASS_METHOD_RE = re.compile(r"""(?m)
        ^\s*
        (?P<static>static\s+)?
        (?P<async>async\s+)?
        (?P<getter>get\s+)?
        (?P<setter>set\s+)?
        (?P<name>[A-Za-z_$][\w$]*)
        \s*\(
            (?P<parameters>[^)]*)
        \)
        \s*\{
        """)

    _FUNCTION_RE = re.compile(r"""(?m)
        ^\s*
        (?P<export>export\s+)?
        (?P<default>default\s+)?
        (?P<async>async\s+)?
        function
        (?P<generator>\*)?
        \s+
        (?P<name>[A-Za-z_$][\w$]*)
        \s*\(
            (?P<parameters>[^)]*)
        \)
        \s*\{
        """)

    _ARROW_FUNCTION_RE = re.compile(r"""(?m)
        ^\s*
        (?P<async>async\s+)?
        (?:
            const\s+
        )?
        (?P<name>[A-Za-z_$][\w$]*)
        \s*=\s*
        (?:
            \((?P<parameters>[^)]*)\)
            |
            (?P<single_parameter>[A-Za-z_$][\w$]*)
        )
        \s*=>""")

    _VARIABLE_RE = re.compile(r"""(?m)
        ^\s*
        (?P<keyword>const|let|var)
        \s+
        (?P<name>[A-Za-z_$][\w$]*)
        (?:\s*=\s*(?P<value>[^;\n]+))?
        \s*;?
        """)

    _JSDOC_RE = re.compile(
        r"""/\*\*(?P<doc>.*?)\*/""",
        re.DOTALL,
    )

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _module_name(path: Path) -> str:
        return path.stem

    @staticmethod
    def _line_number(
        source: str,
        offset: int,
    ) -> int:
        return (
            source.count(
                "\n",
                0,
                offset,
            )
            + 1
        )

    @staticmethod
    def _parse_parameters(
        parameters: str,
    ) -> list[str]:
        if not parameters.strip():
            return []

        parts: list[str] = []
        current: list[str] = []
        depth = 0

        for character in parameters:
            if character in "([{":
                depth += 1

            elif character in ")]}":
                depth = max(
                    0,
                    depth - 1,
                )

            if character == "," and depth == 0:
                value = "".join(current).strip()

                if value:
                    parts.append(value)

                current = []
                continue

            current.append(character)

        value = "".join(current).strip()

        if value:
            parts.append(value)

        return parts

    @staticmethod
    def _parse_import_names(
        names: str,
    ) -> list[str]:
        names = names.strip()

        if names.startswith("{"):
            return [
                item.strip() for item in names.strip("{} ").split(",") if item.strip()
            ]

        if "," in names:
            first, rest = names.split(
                ",",
                1,
            )

            result = [first.strip()]

            rest = rest.strip()

            if rest.startswith("{"):
                result.extend(
                    item.strip()
                    for item in rest.strip("{} ").split(",")
                    if item.strip()
                )

            return result

        return [names]

    @staticmethod
    def _parse_export_names(
        names: str,
    ) -> list[tuple[str, str | None]]:
        result: list[tuple[str, str | None]] = []

        for item in names.split(","):
            item = item.strip()

            if not item:
                continue

            if re.search(
                r"\s+as\s+",
                item,
            ):
                name, alias = re.split(
                    r"\s+as\s+",
                    item,
                    maxsplit=1,
                )

                result.append(
                    (
                        name.strip(),
                        alias.strip(),
                    )
                )

            else:
                result.append(
                    (
                        item,
                        None,
                    )
                )

        return result

    @staticmethod
    def _parse_extends(
        extends: str | None,
    ) -> list[str]:
        if not extends:
            return []

        return [item.strip() for item in extends.split(",") if item.strip()]

    @staticmethod
    def _extract_class_methods(
        body: str,
    ) -> list[str]:
        return [
            match.group("name")
            for match in JavaScriptReader._CLASS_METHOD_RE.finditer(body)
        ]

    @staticmethod
    def _extract_class_fields(
        body: str,
    ) -> list[str]:
        fields: list[str] = []

        for line in body.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if "(" in stripped:
                continue

            if stripped.startswith("//"):
                continue

            match = re.match(
                r"(?:static\s+)?" r"([A-Za-z_$][\w$]*)" r"\s*(?:=|;)",
                stripped,
            )

            if match:
                fields.append(match.group(1))

        return fields

    @staticmethod
    def _extract_documentation(
        source: str,
    ) -> str | None:
        lines: list[str] = []

        for line in source.splitlines():
            stripped = line.strip()

            if stripped.startswith("/**"):
                content = stripped[3:].strip()

                if content:
                    lines.append(content)

            elif stripped.startswith("*"):
                content = stripped[1:].strip()

                if content:
                    lines.append(content)

            elif stripped.startswith("///"):
                lines.append(stripped[3:].lstrip())

        if not lines:
            return None

        return "\n".join(lines)

    @staticmethod
    def _extract_jsdoc_before(
        source: str,
        offset: int,
    ) -> str | None:
        before = source[:offset]

        match = re.search(
            r"/\*\*(?P<doc>.*?)\*/\s*$",
            before,
            re.DOTALL,
        )

        if not match:
            return None

        return JavaScriptReader._clean_jsdoc(match.group("doc"))

    @staticmethod
    def _clean_jsdoc(
        documentation: str,
    ) -> str:
        lines: list[str] = []

        for line in documentation.splitlines():
            line = line.strip()

            if line.startswith("*"):
                line = line[1:].strip()

            if line:
                lines.append(line)

        return "\n".join(lines).strip()

    @staticmethod
    def _documentation_title(
        documentation: str,
    ) -> str:
        for line in documentation.splitlines():
            line = line.strip()

            if not line.startswith("@"):
                return line[:120]

        return "JavaScript Documentation"

    @staticmethod
    def _detect_module_system(
        source: str,
    ) -> str:
        has_esm = bool(
            re.search(
                r"\b(?:import|export)\b",
                source,
            )
        )

        has_commonjs = bool(
            re.search(
                r"\brequire\s*\(" r"|\bmodule\.exports\b" r"|\bexports\.",
                source,
            )
        )

        if has_esm and has_commonjs:
            return "mixed"

        if has_esm:
            return "esm"

        if has_commonjs:
            return "commonjs"

        return "unknown"
