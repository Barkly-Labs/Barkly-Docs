"""

BARKLY DOCS

Rust Reader

Static Rust source reader for Barkly Docs.

This reader does not execute Rust code. It extracts structural

information from Rust source files and maps that information into

the Barkly Project Model.

"""

from __future__ import annotations

import re

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

    VariableNode,

)

from readers.base import LanguageReader, ReaderResult

class RustReader(LanguageReader):

    """

    Static reader for Rust source files.

    """

    language = "Rust"

    extensions = (".rs",)

    version = "0.1.0"

    # ------------------------------------------------------------

    # PUBLIC API

    # ------------------------------------------------------------

    def read(

        self,

        path: Path,

        project: Project,

    ) -> ReaderResult:

        """

        Read one Rust source file into the Barkly Project Model.

        """

        warnings: list[str] = []

        errors: list[str] = []

        try:

            source = self.read_text(path)

        except Exception as exc:

            return ReaderResult(

                success=False,

                project=project,

                warnings=[],

                errors=[f"{path}: unable to read Rust source: {exc}"],

                metadata={

                    "language": self.language,

                    "reader_version": self.version,

                },

            )

        # --------------------------------------------------------

        # FILE

        # --------------------------------------------------------

        file_node = FileNode(

            path=str(path),

            language=self.language,

            size=len(source.encode("utf-8")),

        )

        project.add_file(file_node)

        # --------------------------------------------------------

        # MODULE

        # --------------------------------------------------------

        module_node = ModuleNode(

            name=self._module_name(path),

            path=str(path),

            language=self.language,

            documentation=self._module_documentation(source),

            metadata={

                "rust_file": True,

                "reader": self.version,

            },

        )

        project.add_module(module_node)

        # --------------------------------------------------------

        # DOCUMENTATION COMMENTS

        # --------------------------------------------------------

        documentation = self._extract_documentation(source)

        if documentation:

            module_node.documentation = documentation

        # --------------------------------------------------------
        # USE / IMPORTS
        # --------------------------------------------------------

        for match in self._USE_RE.finditer(source):
            statement = match.group("statement").strip()
            line = self._line_number(source, match.start())

            # Expand every concrete import represented by a Rust use tree.
            for target, alias in self._expand_use_statement(statement):
                project.add_import(
                    ImportNode(
                        source_file=str(path),
                        target=target,
                        language=self.language,
                        names=[target],
                        alias=alias,
                        metadata={
                            "rust_statement": statement,
                            "rust_target": target,
                            "line": line,
                        },
                    )
                )

        # --------------------------------------------------------

        # MODULE DECLARATIONS

        # --------------------------------------------------------

        for match in self._MOD_RE.finditer(source):

            name = match.group("name")

            line = self._line_number(

                source,

                match.start(),

            )

            project.add_module(

                ModuleNode(

                    name=name,

                    path=str(path),

                    language=self.language,

                    documentation=None,

                    metadata={

                        "rust_module": True,

                        "visibility": self._visibility(match.group("visibility")),

                        "line": line,

                    },

                )

            )

        # --------------------------------------------------------

        # STRUCTS

        # --------------------------------------------------------

        for match in self._STRUCT_RE.finditer(source):

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

            node = ClassNode(

                name=name,

                path=str(path),

                language=self.language,

                documentation=None,

                metadata={

                    "rust_kind": "struct",

                    "visibility": self._visibility(match.group("visibility")),

                    "generics": match.group("generics") or "",

                    "line_start": line_start,

                    "line_end": line_end,

                    "fields": self._parse_struct_fields(body),

                },

            )

            project.add_class(node)

        # --------------------------------------------------------

        # ENUMS

        # --------------------------------------------------------

        for match in self._ENUM_RE.finditer(source):

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

            node = ClassNode(

                name=name,

                path=str(path),

                language=self.language,

                documentation=None,

                metadata={

                    "rust_kind": "enum",

                    "visibility": self._visibility(match.group("visibility")),

                    "generics": match.group("generics") or "",

                    "line_start": line_start,

                    "line_end": line_end,

                    "variants": self._parse_enum_variants(body),

                },

            )

            project.add_class(node)

        # --------------------------------------------------------

        # TRAITS

        # --------------------------------------------------------

        for match in self._TRAIT_RE.finditer(source):

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

            node = ClassNode(

                name=name,

                path=str(path),

                language=self.language,

                documentation=None,

                metadata={

                    "rust_kind": "trait",

                    "visibility": self._visibility(match.group("visibility")),

                    "generics": match.group("generics") or "",

                    "line_start": line_start,

                    "line_end": line_end,

                    "methods": self._extract_trait_methods(body),

                },

            )

            project.add_class(node)

        # --------------------------------------------------------

        # FUNCTIONS

        # --------------------------------------------------------

        for match in self._FUNCTION_RE.finditer(source):

            name = match.group("name")

            # Avoid treating methods inside impl blocks as ordinary

            # top-level functions when possible.

            if self._inside_impl(source, match.start()):

                continue

            line_start = self._line_number(

                source,

                match.start(),

            )

            line_end = self._line_number(

                source,

                match.end(),

            )

            parameters = self._parse_parameters(match.group("parameters") or "")

            function_node = FunctionNode(

                name=name,

                path=str(path),

                language=self.language,

                parameters=parameters,

                return_type=match.group("return_type"),

                decorators=[],

                documentation=None,

                line_start=line_start,

                line_end=line_end,

                metadata={

                    "rust_kind": "function",

                    "visibility": self._visibility(match.group("visibility")),

                    "async": bool(match.group("async")),

                    "unsafe": bool(match.group("unsafe")),

                    "extern": bool(match.group("extern")),

                    "generics": match.group("generics") or "",

                },

            )

            project.add_function(function_node)

        # --------------------------------------------------------

        # IMPL BLOCKS / METHODS

        # --------------------------------------------------------

        for match in self._IMPL_RE.finditer(source):

            type_name = match.group("type_name")

            body = match.group("body") or ""

            impl_line = self._line_number(

                source,

                match.start(),

            )

            for method in self._FUNCTION_RE.finditer(body):

                name = method.group("name")

                parameters = self._parse_parameters(method.group("parameters") or "")

                relative_start = match.start("body") + method.start()

                relative_end = match.start("body") + method.end()

                line_start = self._line_number(

                    source,

                    relative_start,

                )

                line_end = self._line_number(

                    source,

                    relative_end,

                )

                method_node = MethodNode(

                    name=name,

                    path=str(path),

                    language=self.language,

                    parameters=parameters,

                    return_type=method.group("return_type"),

                    decorators=[],

                    documentation=None,

                    line_start=line_start,

                    line_end=line_end,

                    class_name=type_name,

                    metadata={

                        "rust_kind": "impl_method",

                        "visibility": self._visibility(method.group("visibility")),

                        "async": bool(method.group("async")),

                        "unsafe": bool(method.group("unsafe")),

                        "generics": method.group("generics") or "",

                        "impl_line": impl_line,

                    },

                )

                project.add_method(method_node)

        # --------------------------------------------------------

        # CONSTANTS / STATICS

        # --------------------------------------------------------

        for match in self._CONSTANT_RE.finditer(source):

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

                    type=match.group("type"),

                    value=value.strip(),

                    constant=True,

                    line=line,

                    metadata={

                        "rust_kind": (

                            "static" if match.group("keyword") == "static" else "const"

                        ),

                        "visibility": self._visibility(match.group("visibility")),

                    },

                )

            )

        # --------------------------------------------------------

        # TYPE ALIASES

        # --------------------------------------------------------

        type_alias_count = 0

        for match in self._TYPE_RE.finditer(source):

            type_alias_count += 1

            warnings.append(

                f"{path}:{self._line_number(source, match.start())}: "

                f"Rust type alias '{match.group('name')}' "

                f"is preserved in metadata."

            )

        # --------------------------------------------------------

        # ATTRIBUTES

        # --------------------------------------------------------

        attributes = self._extract_attributes(source)

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

                "parser": "static-regex-structural",

                "static_analysis": True,

                "rust_attributes": attributes,

                "type_aliases": type_alias_count,

            },

        )

    # ============================================================

    # REGULAR EXPRESSIONS

    # ============================================================

    _USE_RE = re.compile(
        r"(?ms)^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+"
        r"(?P<statement>.*?);"
    )

    _MOD_RE = re.compile(

        r"(?m)^\s*(?P<visibility>pub(?:\([^)]*\))?\s+)?"

        r"mod\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:;|\{)"

    )

    _STRUCT_RE = re.compile(

        r"(?s)"

        r"(?P<visibility>pub(?:\([^)]*\))?\s+)?"

        r"struct\s+"

        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"

        r"\s*(?P<generics><[^>{}]*>)?"

        r"(?:\s+where[^{]+)?"

        r"\s*\{(?P<body>.*?)\}"

    )

    _ENUM_RE = re.compile(

        r"(?s)"

        r"(?P<visibility>pub(?:\([^)]*\))?\s+)?"

        r"enum\s+"

        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"

        r"\s*(?P<generics><[^>{}]*>)?"

        r"(?:\s+where[^{]+)?"

        r"\s*\{(?P<body>.*?)\}"

    )

    _TRAIT_RE = re.compile(

        r"(?s)"

        r"(?P<visibility>pub(?:\([^)]*\))?\s+)?"

        r"trait\s+"

        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"

        r"\s*(?P<generics><[^>{}]*>)?"

        r"(?:\s+where[^{]+)?"

        r"\s*\{(?P<body>.*?)\}"

    )

    _IMPL_RE = re.compile(

        r"(?s)"

        r"impl"

        r"(?:\s*<[^>{}]*>)?"

        r"\s+"

        r"(?P<type_name>"

        r"[A-Za-z_][A-Za-z0-9_:]*(?:\s*<[^>{}]*>)?"

        r")"

        r"(?:\s+for\s+[^{]+)?"

        r"\s*\{(?P<body>.*?)\}"

    )

    _FUNCTION_RE = re.compile(

        r"(?s)"

        r"(?P<visibility>pub(?:\([^)]*\))?\s+)?"

        r"(?P<async>async\s+)?"

        r"(?P<unsafe>unsafe\s+)?"

        r"(?P<extern>extern\s+)?"

        r"fn\s+"

        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"

        r"\s*(?P<generics><[^>{}]*>)?"

        r"\s*\((?P<parameters>.*?)\)"

        r"\s*(?:->\s*(?P<return_type>[^{]+))?"

        r"\s*(?:where[^{]+)?"

        r"\{"

    )

    _CONSTANT_RE = re.compile(

        r"(?m)^\s*"

        r"(?P<visibility>pub(?:\([^)]*\))?\s+)?"

        r"(?P<keyword>const|static)"

        r"\s+"

        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"

        r"\s*:\s*"

        r"(?P<type>[^=;]+)"

        r"=\s*"

        r"(?P<value>[^;]+);"

    )

    _TYPE_RE = re.compile(

        r"(?m)^\s*"

        r"(?:pub(?:\([^)]*\))?\s+)?"

        r"type\s+"

        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"

    )

    # ============================================================

    # HELPERS

    # ============================================================

    @staticmethod

    def _module_name(path: Path) -> str:

        """

        Return a reasonable Rust module name.

        """

        if path.stem == "lib":

            return "lib"

        if path.stem == "main":

            return "main"

        return path.stem

    @staticmethod

    def _line_number(

        source: str,

        offset: int,

    ) -> int:

        """

        Convert a character offset into a 1-based line number.

        """

        return source.count("\n", 0, offset) + 1

    @staticmethod

    def _visibility(

        value: str | None,

    ) -> str:

        """

        Normalize Rust visibility.

        """

        if not value:

            return "private"

        return value.strip()

    @classmethod
    def _expand_use_statement(
        cls, statement: str
    ) -> list[tuple[str, str | None]]:
        """Expand grouped/nested Rust use trees into concrete imports."""
        statement = " ".join(statement.strip().split())
        if not statement:
            return []

        result: list[tuple[str, str | None]] = []
        seen: set[tuple[str, str | None]] = set()
        for target, alias in cls._expand_use_tree(statement, ""):
            target = target.strip(": ")
            item = (target, alias)
            if target and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @classmethod
    def _expand_use_tree(
        cls, tree: str, prefix: str
    ) -> list[tuple[str, str | None]]:
        tree = tree.strip()
        if not tree:
            return []

        brace = cls._find_use_group(tree)
        if brace >= 0:
            close = cls._matching_use_brace(tree, brace)
            if close < 0:
                return [cls._split_use_alias(cls._join_use_path(prefix, tree))]

            head = tree[:brace].strip()
            if head.endswith("::"):
                head = head[:-2]
            base = cls._join_use_path(prefix, head)

            results: list[tuple[str, str | None]] = []
            for child in cls._split_top_level(tree[brace + 1:close], ","):
                child = child.strip()
                if not child:
                    continue
                if child == "self":
                    if base:
                        results.append((base, None))
                else:
                    results.extend(cls._expand_use_tree(child, base))
            return results

        target, alias = cls._split_use_alias(cls._join_use_path(prefix, tree))
        if target.endswith("::self"):
            target = target[:-6]
        return [(target, alias)]

    @staticmethod
    def _join_use_path(prefix: str, value: str) -> str:
        prefix = prefix.strip().rstrip(":")
        value = value.strip().lstrip(":")
        if not prefix:
            return value
        if not value:
            return prefix
        return f"{prefix}::{value}"

    @staticmethod
    def _split_use_alias(value: str) -> tuple[str, str | None]:
        match = re.match(
            r"^(?P<target>.+?)\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)$",
            value.strip(),
        )
        if match:
            return match.group("target").strip(), match.group("alias")
        return value.strip(), None

    @staticmethod
    def _find_use_group(text: str) -> int:
        paren = bracket = angle = 0
        for index, character in enumerate(text):
            if character == "{" and paren == bracket == angle == 0:
                return index
            if character == "(":
                paren += 1
            elif character == ")":
                paren = max(0, paren - 1)
            elif character == "[":
                bracket += 1
            elif character == "]":
                bracket = max(0, bracket - 1)
            elif character == "<":
                angle += 1
            elif character == ">":
                angle = max(0, angle - 1)
        return -1

    @staticmethod
    def _matching_use_brace(text: str, opening: int) -> int:
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    return index
        return -1

    @staticmethod

    def _parse_parameters(

        parameters: str,

    ) -> list[str]:

        """

        Preserve Rust parameters as strings.

        Rust parameter syntax can be complex, so this first reader

        intentionally preserves the declarations instead of trying

        to completely normalize them.

        """

        if not parameters.strip():

            return []

        parts: list[str] = []

        current: list[str] = []

        depth = 0

        for character in parameters:

            if character in "([{<":

                depth += 1

            elif character in ")]}>":

                depth = max(0, depth - 1)

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

    def _parse_struct_fields(

        body: str,

    ) -> list[str]:

        """

        Extract top-level struct field declarations.

        """

        fields: list[str] = []

        for part in RustReader._split_top_level(body, ","):

            value = part.strip()

            if value:

                fields.append(value)

        return fields

    @staticmethod

    def _parse_enum_variants(

        body: str,

    ) -> list[str]:

        """

        Extract enum variants while preserving their declarations.

        """

        variants: list[str] = []

        for part in RustReader._split_top_level(body, ","):

            value = part.strip()

            if value:

                variants.append(value)

        return variants

    @staticmethod

    def _extract_trait_methods(

        body: str,

    ) -> list[str]:

        """

        Extract method names from a trait body.

        """

        return [match.group("name") for match in RustReader._FUNCTION_RE.finditer(body)]

    @staticmethod

    def _split_top_level(

        text: str,

        delimiter: str,

    ) -> list[str]:

        """

        Split text while respecting nested Rust delimiters.

        """

        result: list[str] = []

        current: list[str] = []

        depth = 0

        for character in text:

            if character in "([{<":

                depth += 1

            elif character in ")]}>":

                depth = max(0, depth - 1)

            if character == delimiter and depth == 0:

                result.append("".join(current))

                current = []

                continue

            current.append(character)

        result.append("".join(current))

        return result

    @staticmethod

    def _extract_documentation(

        source: str,

    ) -> str | None:

        """

        Extract Rust /// documentation comments.

        """

        lines: list[str] = []

        for line in source.splitlines():

            stripped = line.strip()

            if stripped.startswith("///"):

                lines.append(stripped[3:].lstrip())

        if not lines:

            return None

        return "\n".join(lines)

    @staticmethod

    def _module_documentation(

        source: str,

    ) -> str | None:

        """

        Extract //! crate/module documentation.

        """

        lines: list[str] = []

        for line in source.splitlines():

            stripped = line.strip()

            if stripped.startswith("//!"):

                lines.append(stripped[3:].lstrip())

        if not lines:

            return None

        return "\n".join(lines)

    @staticmethod

    def _extract_attributes(

        source: str,

    ) -> list[str]:

        """

        Extract Rust attributes such as #[derive(...)].

        """

        return [

            match.group(0).strip()

            for match in re.finditer(

                r"(?m)^\s*#\[[^\n]+\]",

                source,

            )

        ]

    @staticmethod

    def _inside_impl(

        source: str,

        offset: int,

    ) -> bool:

        """

        Conservative check for whether an offset occurs inside

        an impl block.

        This intentionally avoids pretending to be a complete Rust

        parser. The full impl parser separately handles methods.

        """

        prefix = source[:offset]

        impl_count = len(re.findall(r"\bimpl\b", prefix))

        closing_count = prefix.count("}")

        opening_count = prefix.count("{")

        return impl_count > 0 and opening_count > closing_count
