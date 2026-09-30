"""
BARKLY DOCS

Ruby Reader

Static Ruby source reader for Barkly Docs.

This reader does not execute Ruby code. It extracts
structural information from Ruby source files and maps
that information into the Barkly Project Model.

Design principle:

    Ruby Source

        ↓

    Ruby Reader

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


class RubyReader(LanguageReader):
    """
    Static reader for Ruby source files.

    Supported:

        .rb
        .rake
        .gemspec

    This reader is intentionally static.

    It does not:

        - execute Ruby
        - load Ruby files
        - require gems
        - invoke Bundler
        - instantiate application objects
        - require a Ruby runtime

    It extracts structural information from source text and
    maps that information into the Barkly Project Model.
    """

    language = "Ruby"
    extensions = (".rb", ".rake", ".gemspec")
    version = "0.1.0"

    # ================================================================
    # READER
    # ================================================================

    def read(
        self,
        path: Path,
        project: Project,
    ) -> ReaderResult:

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
                errors=[
                    f"{path}: unable to read Ruby source: {exc}"
                ],
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
                "ruby_file": True,
                "reader": self.version,
                "ruby_kind": "source_file",
            },
        )

        project.add_module(module_node)

        # ------------------------------------------------------------
        # REQUIRES
        # ------------------------------------------------------------

        for match in self._REQUIRE_RE.finditer(source):

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
                    "ruby_statement": match.group(0).strip(),
                    "line": line,
                    "module_system": "ruby_require",
                    "require_kind": "require",
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
                        "require_kind": "require",
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # REQUIRE RELATIVE
        # ------------------------------------------------------------

        for match in self._REQUIRE_RELATIVE_RE.finditer(source):

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
                    "ruby_statement": match.group(0).strip(),
                    "line": line,
                    "module_system": "ruby_require",
                    "require_kind": "require_relative",
                    "relative": True,
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
                        "require_kind": "require_relative",
                        "relative": True,
                        "line": line,
                    },
                )
            )

        # ------------------------------------------------------------
        # MODULES
        # ------------------------------------------------------------

        structures = self._scan_structures(source)

        for structure in structures:

            if structure["kind"] != "module":
                continue

            name = structure["name"]

            line_start = structure["line_start"]
            line_end = structure["line_end"]

            documentation = self._extract_documentation_before(
                source,
                structure["offset"],
            )

            node = ModuleNode(
                name=name,
                path=str(path),
                language=self.language,
                documentation=documentation,
                metadata={
                    "ruby_kind": "module",
                    "line_start": line_start,
                    "line_end": line_end,
                    "namespace": structure.get(
                        "namespace"
                    ),
                },
            )

            project.add_module(node)

            # --------------------------------------------------------
            # NESTED MODULE RELATIONSHIP
            # --------------------------------------------------------

            parent = structure.get("parent")

            if parent:

                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{parent}",
                        target=f"{path}:{name}",
                        kind="contains",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "ruby_kind": "nested_module",
                            "line": line_start,
                        },
                    )
                )

        # ------------------------------------------------------------
        # CLASSES
        # ------------------------------------------------------------

        for structure in structures:

            if structure["kind"] != "class":
                continue

            name = structure["name"]

            line_start = structure["line_start"]
            line_end = structure["line_end"]

            body = structure.get("body", "")

            bases = []

            superclass = structure.get("superclass")

            if superclass:
                bases.append(superclass)

            includes = self._extract_includes(body)
            extends = self._extract_extends(body)

            methods = self._extract_method_names(body)
            attributes = self._extract_attributes(body)

            documentation = self._extract_documentation_before(
                source,
                structure["offset"],
            )

            node = ClassNode(
                name=name,
                path=str(path),
                language=self.language,
                bases=bases,
                decorators=[],
                methods=methods,
                attributes=attributes,
                documentation=documentation,
                line_start=line_start,
                line_end=line_end,
                metadata={
                    "ruby_kind": "class",
                    "line_start": line_start,
                    "line_end": line_end,
                    "namespace": structure.get(
                        "namespace"
                    ),
                    "included_modules": includes,
                    "extended_modules": extends,
                },
            )

            project.add_class(node)

            # --------------------------------------------------------
            # INHERITANCE
            # --------------------------------------------------------

            for base in bases:

                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{name}",
                        target=base,
                        kind="inherits",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "ruby_kind": "class_inheritance",
                            "line": line_start,
                        },
                    )
                )

            # --------------------------------------------------------
            # INCLUDED MODULES
            # --------------------------------------------------------

            for included in includes:

                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{name}",
                        target=included,
                        kind="includes",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "ruby_kind": "include",
                            "line": line_start,
                        },
                    )
                )

            # --------------------------------------------------------
            # EXTENDED MODULES
            # --------------------------------------------------------

            for extended in extends:

                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{name}",
                        target=extended,
                        kind="extends",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "ruby_kind": "extend",
                            "line": line_start,
                        },
                    )
                )

            # --------------------------------------------------------
            # CLASS METHODS
            # --------------------------------------------------------

            method_structures = self._extract_methods(
                body,
                source,
                structure["body_start"],
                name,
                path,
            )

            for method in method_structures:

                method_node = MethodNode(
                    name=method["name"],
                    path=str(path),
                    language=self.language,
                    parameters=method["parameters"],
                    return_type=None,
                    decorators=[],
                    documentation=method["documentation"],
                    line_start=method["line_start"],
                    line_end=method["line_end"],
                    class_name=name,
                    metadata={
                        "ruby_kind": method["ruby_kind"],
                        "visibility": method["visibility"],
                        "singleton": method["singleton"],
                        "line_start": method["line_start"],
                        "line_end": method["line_end"],
                    },
                )

                project.add_method(method_node)

                project.add_relationship(
                    RelationshipNode(
                        source=f"{path}:{name}",
                        target=(
                            f"{path}:{method['name']}"
                        ),
                        kind="contains",
                        source_file=str(path),
                        metadata={
                            "language": self.language,
                            "ruby_kind": "class_method",
                            "line": method["line_start"],
                        },
                    )
                )

        # ------------------------------------------------------------
        # TOP-LEVEL METHODS
        # ------------------------------------------------------------

        top_level_methods = self._extract_top_level_methods(
            source,
            structures,
            path,
        )

        for method in top_level_methods:

            function_node = FunctionNode(
                name=method["name"],
                path=str(path),
                language=self.language,
                parameters=method["parameters"],
                return_type=None,
                decorators=[],
                documentation=method["documentation"],
                line_start=method["line_start"],
                line_end=method["line_end"],
                async_function=False,
                metadata={
                    "ruby_kind": "top_level_method",
                    "singleton": method["singleton"],
                    "visibility": method["visibility"],
                },
            )

            project.add_function(function_node)

        # ------------------------------------------------------------
        # CONSTANTS
        # ------------------------------------------------------------

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
                    type=None,
                    value=(
                        value.strip()
                        if value
                        else None
                    ),
                    constant=True,
                    line=line,
                    metadata={
                        "ruby_kind": "constant",
                        "declaration": "constant",
                    },
                )
            )

        # ------------------------------------------------------------
        # INSTANCE VARIABLES
        # ------------------------------------------------------------

        for match in self._INSTANCE_VARIABLE_RE.finditer(
            source
        ):

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
                    value=(
                        value.strip()
                        if value
                        else None
                    ),
                    constant=False,
                    line=line,
                    metadata={
                        "ruby_kind": "instance_variable",
                        "scope": "instance",
                    },
                )
            )

        # ------------------------------------------------------------
        # CLASS VARIABLES
        # ------------------------------------------------------------

        for match in self._CLASS_VARIABLE_RE.finditer(
            source
        ):

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
                    value=(
                        value.strip()
                        if value
                        else None
                    ),
                    constant=False,
                    line=line,
                    metadata={
                        "ruby_kind": "class_variable",
                        "scope": "class",
                    },
                )
            )

        # ------------------------------------------------------------
        # LOCAL VARIABLES
        # ------------------------------------------------------------

        for match in self._LOCAL_VARIABLE_RE.finditer(
            source
        ):

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
                    value=(
                        value.strip()
                        if value
                        else None
                    ),
                    constant=False,
                    line=line,
                    metadata={
                        "ruby_kind": "local_variable",
                        "scope": "local",
                    },
                )
            )

        # ------------------------------------------------------------
        # DOCUMENTATION
        # ------------------------------------------------------------

        for match in self._RUBYDOC_RE.finditer(source):

            documentation = self._clean_rubydoc(
                match.group("doc")
            )

            if not documentation:
                continue

            line = self._line_number(
                source,
                match.start(),
            )

            project.add_documentation(
                DocumentationNode(
                    title=self._documentation_title(
                        documentation
                    ),
                    path=str(path),
                    kind="rubydoc",
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
                "parser": "static-structural-scanner",
                "static_analysis": True,
                "ruby_version": "unknown",
            },
        )

    # ================================================================
    # REGEX PATTERNS
    # ================================================================

    # ------------------------------------------------------------
    # require "foo"
    # ------------------------------------------------------------

    _REQUIRE_RE = re.compile(
        r"""(?m)
        ^\s*
        require
        \s*
        ["'](?P<target>[^"']+)["']
        \s*
        $
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # require_relative "./foo"
    # ------------------------------------------------------------

    _REQUIRE_RELATIVE_RE = re.compile(
        r"""(?m)
        ^\s*
        require_relative
        \s*
        ["'](?P<target>[^"']+)["']
        \s*
        $
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # class Foo
    # class Foo < Bar
    # ------------------------------------------------------------

    _CLASS_RE = re.compile(
        r"""^\s*
        class
        \s+
        (?P<name>
            [A-Za-z_][A-Za-z0-9_:]*
        )
        (?:
            \s*
            <
            \s*
            (?P<superclass>
                [A-Za-z_][A-Za-z0-9_:]*
            )
        )?
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # module Foo
    # ------------------------------------------------------------

    _MODULE_RE = re.compile(
        r"""^\s*
        module
        \s+
        (?P<name>
            [A-Za-z_][A-Za-z0-9_:]*
        )
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # def foo
    # def foo(...)
    # def self.foo
    # def ClassName.foo
    # ------------------------------------------------------------

    _METHOD_RE = re.compile(
        r"""^\s*
        def
        \s+
        (?P<receiver>
            self
            |
            [A-Za-z_][A-Za-z0-9_:]*
        )?
        (?:\.)?
        (?P<name>
            [A-Za-z_][A-Za-z0-9_!?=]*
        )
        (?:
            \s*
            \(
                (?P<parameters>[^)]*)
            \)
        )?
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # include Foo
    # ------------------------------------------------------------

    _INCLUDE_RE = re.compile(
        r"""(?m)
        ^\s*
        include
        \s+
        (?P<modules>.+?)
        \s*$
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # extend Foo
    # ------------------------------------------------------------

    _EXTEND_RE = re.compile(
        r"""(?m)
        ^\s*
        extend
        \s+
        (?P<modules>.+?)
        \s*$
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # attr_reader / attr_writer / attr_accessor
    # ------------------------------------------------------------

    _ATTRIBUTE_RE = re.compile(
        r"""(?m)
        ^\s*
        (?P<kind>
            attr_reader
            |
            attr_writer
            |
            attr_accessor
        )
        \s+
        (?P<attributes>.+?)
        \s*$
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # CONSTANT = value
    # ------------------------------------------------------------

    _CONSTANT_RE = re.compile(
        r"""(?m)
        ^\s*
        (?P<name>
            [A-Z][A-Za-z0-9_]*
        )
        \s*=\s*
        (?P<value>[^\n]+)
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # @variable = value
    # ------------------------------------------------------------

    _INSTANCE_VARIABLE_RE = re.compile(
        r"""(?m)
        (?P<name>
            @[A-Za-z_][A-Za-z0-9_]*
        )
        \s*
        =
        \s*
        (?P<value>[^\n;]+)
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # @@variable = value
    # ------------------------------------------------------------

    _CLASS_VARIABLE_RE = re.compile(
        r"""(?m)
        (?P<name>
            @@[A-Za-z_][A-Za-z0-9_]*
        )
        \s*
        =
        \s*
        (?P<value>[^\n;]+)
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # local_variable = value
    #
    # This intentionally requires a lowercase/underscore identifier
    # and an assignment so method calls and keywords are less likely
    # to be interpreted as variables.
    # ------------------------------------------------------------

    _LOCAL_VARIABLE_RE = re.compile(
        r"""(?m)
        ^\s*
        (?P<name>
            [a-z_][A-Za-z0-9_]*
        )
        \s*
        =
        \s*
        (?P<value>[^\n;]+)
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------
    # Ruby documentation comments
    #
    # Examples:
    #
    # # Project documentation
    #
    # ##
    # # Project documentation
    # ##
    # ------------------------------------------------------------

    _RUBYDOC_RE = re.compile(
        r"""(?m)
        (?P<doc>
            (?:
                ^\s*#.*(?:\n|$)
            )+
        )
        """,
        re.VERBOSE,
    )

    # ================================================================
    # STRUCTURAL SCANNER
    # ================================================================

    @classmethod
    def _scan_structures(
        cls,
        source: str,
    ) -> list[dict]:

        lines = source.splitlines(
            keepends=True
        )

        structures: list[dict] = []

        stack: list[dict] = []

        offsets: list[int] = []

        current_offset = 0

        for line in lines:

            offsets.append(current_offset)

            current_offset += len(line)

        for index, line in enumerate(lines):

            stripped = cls._strip_ruby_comment(
                line
            ).strip()

            if not stripped:
                continue

            # --------------------------------------------------------
            # CLASS
            # --------------------------------------------------------

            class_match = cls._CLASS_RE.match(
                stripped
            )

            if class_match:

                name = class_match.group(
                    "name"
                )

                superclass = class_match.group(
                    "superclass"
                )

                structure = {
                    "kind": "class",
                    "name": name,
                    "superclass": superclass,
                    "line_start": index + 1,
                    "line_end": index + 1,
                    "offset": offsets[index],
                    "body_start": offsets[index]
                    + len(line),
                    "body": "",
                    "parent": (
                        stack[-1]["name"]
                        if stack
                        else None
                    ),
                }

                stack.append(
                    structure
                )

                structures.append(
                    structure
                )

                continue

            # --------------------------------------------------------
            # MODULE
            # --------------------------------------------------------

            module_match = cls._MODULE_RE.match(
                stripped
            )

            if module_match:

                name = module_match.group(
                    "name"
                )

                structure = {
                    "kind": "module",
                    "name": name,
                    "line_start": index + 1,
                    "line_end": index + 1,
                    "offset": offsets[index],
                    "body_start": offsets[index]
                    + len(line),
                    "body": "",
                    "parent": (
                        stack[-1]["name"]
                        if stack
                        else None
                    ),
                }

                stack.append(
                    structure
                )

                structures.append(
                    structure
                )

                continue

            # --------------------------------------------------------
            # END
            # --------------------------------------------------------

            if cls._is_end_line(stripped):

                if stack:

                    structure = stack.pop()

                    structure[
                        "line_end"
                    ] = index + 1

                    body_start = structure[
                        "body_start"
                    ]

                    body_end = offsets[index]

                    structure["body"] = (
                        source[
                            body_start:body_end
                        ]
                    )

                continue

        # ------------------------------------------------------------
        # UNFINISHED STRUCTURES
        #
        # A malformed/incomplete file should not crash the reader.
        # We simply use the end of the source as the current boundary.
        # ------------------------------------------------------------

        total_lines = len(lines)

        for structure in stack:

            structure["line_end"] = (
                total_lines
            )

            structure["body"] = source[
                structure["body_start"] :
            ]

        return structures

    # ================================================================
    # METHOD EXTRACTION
    # ================================================================

    @classmethod
    def _extract_methods(
        cls,
        body: str,
        source: str,
        body_offset: int,
        class_name: str,
        path: Path,
    ) -> list[dict]:

        lines = body.splitlines(
            keepends=True
        )

        methods: list[dict] = []

        stack: list[dict] = []

        current_offset = body_offset

        visibility = "public"

        for line in lines:

            stripped = cls._strip_ruby_comment(
                line
            ).strip()

            line_start = cls._line_number(
                source,
                current_offset,
            )

            # --------------------------------------------------------
            # VISIBILITY
            # --------------------------------------------------------

            if stripped in (
                "public",
                "private",
                "protected",
            ):

                visibility = stripped

                current_offset += len(line)

                continue

            # --------------------------------------------------------
            # METHOD
            # --------------------------------------------------------

            match = cls._METHOD_RE.match(
                stripped
            )

            if match:

                receiver = match.group(
                    "receiver"
                )

                name = match.group(
                    "name"
                )

                parameters = (
                    match.group("parameters")
                    or ""
                )

                singleton = (
                    receiver is not None
                )

                method_kind = (
                    "singleton_method"
                    if singleton
                    else "instance_method"
                )

                method = {
                    "name": name,
                    "parameters": cls._parse_parameters(
                        parameters
                    ),
                    "line_start": line_start,
                    "line_end": line_start,
                    "documentation": (
                        cls._extract_documentation_before(
                            source,
                            current_offset,
                        )
                    ),
                    "visibility": visibility,
                    "singleton": singleton,
                    "ruby_kind": method_kind,
                    "offset": current_offset,
                    "body_start": (
                        current_offset
                        + len(line)
                    ),
                    "body": "",
                }

                stack.append(method)

                methods.append(method)

                current_offset += len(line)

                continue

            # --------------------------------------------------------
            # END
            # --------------------------------------------------------

            if cls._is_end_line(stripped):

                if stack:

                    method = stack.pop()

                    method[
                        "line_end"
                    ] = line_start

                    body_end = current_offset

                    method["body"] = source[
                        method["body_start"] :
                        body_end
                    ]

                current_offset += len(line)

                continue

            current_offset += len(line)

        # ------------------------------------------------------------
        # INCOMPLETE METHODS
        # ------------------------------------------------------------

        for method in stack:

            method["line_end"] = (
                cls._line_number(
                    source,
                    len(source),
                )
            )

            method["body"] = source[
                method["body_start"] :
            ]

        return methods

    # ================================================================
    # TOP-LEVEL METHODS
    # ================================================================

    @classmethod
    def _extract_top_level_methods(
        cls,
        source: str,
        structures: list[dict],
        path: Path,
    ) -> list[dict]:

        results: list[dict] = []

        lines = source.splitlines(
            keepends=True
        )

        nesting = 0

        current_offset = 0

        stack: list[dict] = []

        visibility = "public"

        for index, line in enumerate(lines):

            stripped = cls._strip_ruby_comment(
                line
            ).strip()

            line_start = index + 1

            # --------------------------------------------------------
            # TRACK STRUCTURAL NESTING
            # --------------------------------------------------------

            class_match = cls._CLASS_RE.match(
                stripped
            )

            module_match = cls._MODULE_RE.match(
                stripped
            )

            if class_match or module_match:

                nesting += 1

                current_offset += len(line)

                continue

            # --------------------------------------------------------
            # VISIBILITY
            # --------------------------------------------------------

            if stripped in (
                "public",
                "private",
                "protected",
            ):

                visibility = stripped

                current_offset += len(line)

                continue

            # --------------------------------------------------------
            # TOP-LEVEL METHOD
            # --------------------------------------------------------

            if nesting == 0:

                match = cls._METHOD_RE.match(
                    stripped
                )

                if match:

                    receiver = match.group(
                        "receiver"
                    )

                    name = match.group(
                        "name"
                    )

                    parameters = (
                        match.group(
                            "parameters"
                        )
                        or ""
                    )

                    method = {
                        "name": name,
                        "parameters": cls._parse_parameters(
                            parameters
                        ),
                        "line_start": line_start,
                        "line_end": line_start,
                        "documentation": (
                            cls._extract_documentation_before(
                                source,
                                current_offset,
                            )
                        ),
                        "visibility": visibility,
                        "singleton": (
                            receiver
                            is not None
                        ),
                        "body_start": (
                            current_offset
                            + len(line)
                        ),
                    }

                    stack.append(method)

                    results.append(method)

            # --------------------------------------------------------
            # END
            # --------------------------------------------------------

            if cls._is_end_line(stripped):

                if stack:

                    method = stack.pop()

                    method[
                        "line_end"
                    ] = line_start

                else:

                    nesting = max(
                        0,
                        nesting - 1,
                    )

            current_offset += len(line)

        return results

    # ================================================================
    # INCLUDES
    # ================================================================

    @classmethod
    def _extract_includes(
        cls,
        body: str,
    ) -> list[str]:

        result: list[str] = []

        for match in cls._INCLUDE_RE.finditer(
            body
        ):

            modules = match.group(
                "modules"
            )

            result.extend(
                cls._split_constant_list(
                    modules
                )
            )

        return result

    # ================================================================
    # EXTENDS
    # ================================================================

    @classmethod
    def _extract_extends(
        cls,
        body: str,
    ) -> list[str]:

        result: list[str] = []

        for match in cls._EXTEND_RE.finditer(
            body
        ):

            modules = match.group(
                "modules"
            )

            result.extend(
                cls._split_constant_list(
                    modules
                )
            )

        return result

    # ================================================================
    # ATTRIBUTES
    # ================================================================

    @classmethod
    def _extract_attributes(
        cls,
        body: str,
    ) -> list[str]:

        attributes: list[str] = []

        for match in cls._ATTRIBUTE_RE.finditer(
            body
        ):

            kind = match.group(
                "kind"
            )

            values = cls._split_symbol_list(
                match.group("attributes")
            )

            for value in values:

                attributes.append(
                    value
                )

        return attributes

    # ================================================================
    # METHOD NAMES
    # ================================================================

    @classmethod
    def _extract_method_names(
        cls,
        body: str,
    ) -> list[str]:

        methods: list[str] = []

        for match in cls._METHOD_RE.finditer(
            body
        ):

            name = match.group(
                "name"
            )

            if name not in methods:

                methods.append(name)

        return methods

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _module_name(
        path: Path,
    ) -> str:

        return path.stem

    # ------------------------------------------------------------
    # LINE NUMBER
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # PARAMETERS
    # ------------------------------------------------------------

    @staticmethod
    def _parse_parameters(
        parameters: str,
    ) -> list[str]:

        if not parameters.strip():

            return []

        parts: list[str] = []

        current: list[str] = []

        depth = 0

        quote: str | None = None

        escape = False

        for character in parameters:

            # --------------------------------------------------------
            # STRING TRACKING
            # --------------------------------------------------------

            if quote:

                if escape:

                    escape = False

                elif character == "\\":
                    escape = True

                elif character == quote:
                    quote = None

            else:

                if character in (
                    "'",
                    '"',
                    "`",
                ):

                    quote = character

                elif character in "([{":

                    depth += 1

                elif character in ")]}":

                    depth = max(
                        0,
                        depth - 1,
                    )

            # --------------------------------------------------------
            # PARAMETER SEPARATOR
            # --------------------------------------------------------

            if (
                character == ","
                and depth == 0
                and quote is None
            ):

                value = "".join(
                    current
                ).strip()

                if value:

                    parts.append(value)

                current = []

                continue

            current.append(character)

        value = "".join(
            current
        ).strip()

        if value:

            parts.append(value)

        return parts

    # ------------------------------------------------------------
    # SYMBOL LIST
    # ------------------------------------------------------------

    @staticmethod
    def _split_symbol_list(
        value: str,
    ) -> list[str]:

        result: list[str] = []

        for item in value.split(","):

            item = item.strip()

            if not item:

                continue

            item = item.rstrip(";")

            item = item.strip()

            if item.startswith(":"):

                item = item[1:]

            item = item.strip(
                "'\""
            )

            if item:

                result.append(item)

        return result

    # ------------------------------------------------------------
    # CONSTANT LIST
    # ------------------------------------------------------------

    @staticmethod
    def _split_constant_list(
        value: str,
    ) -> list[str]:

        result: list[str] = []

        for item in value.split(","):

            item = item.strip()

            if not item:

                continue

            # Remove trailing inline comments.
            item = item.split(
                "#",
                1,
            )[0].strip()

            if item:

                result.append(item)

        return result

    # ------------------------------------------------------------
    # STRIP RUBY COMMENTS
    # ------------------------------------------------------------

    @staticmethod
    def _strip_ruby_comment(
        line: str,
    ) -> str:

        result: list[str] = []

        quote: str | None = None

        escape = False

        for character in line:

            if quote:

                result.append(
                    character
                )

                if escape:

                    escape = False

                elif character == "\\":
                    escape = True

                elif character == quote:
                    quote = None

                continue

            if character in (
                "'",
                '"',
                "`",
            ):

                quote = character

                result.append(
                    character
                )

                continue

            if character == "#":

                break

            result.append(
                character
            )

        return "".join(result)

    # ------------------------------------------------------------
    # END LINE
    # ------------------------------------------------------------

    @staticmethod
    def _is_end_line(
        stripped: str,
    ) -> bool:

        if stripped == "end":
            return True

        if stripped.startswith(
            "end "
        ):

            return True

        if stripped.startswith(
            "end;"
        ):

            return True

        return False

    # ------------------------------------------------------------
    # DOCUMENTATION
    # ------------------------------------------------------------

    @classmethod
    def _extract_documentation(
        cls,
        source: str,
    ) -> str | None:

        lines: list[str] = []

        for line in source.splitlines():

            stripped = line.strip()

            if not stripped.startswith(
                "#"
            ):

                continue

            content = stripped[
                1:
            ].strip()

            if content:

                lines.append(
                    content
                )

        if not lines:

            return None

        return "\n".join(lines)

    # ------------------------------------------------------------
    # DOCUMENTATION BEFORE SYMBOL
    # ------------------------------------------------------------

    @classmethod
    def _extract_documentation_before(
        cls,
        source: str,
        offset: int,
    ) -> str | None:

        before = source[:offset]

        lines = before.splitlines()

        documentation: list[str] = []

        for line in reversed(lines):

            stripped = line.strip()

            if not stripped:

                if documentation:

                    break

                continue

            if stripped.startswith(
                "#"
            ):

                content = stripped[
                    1:
                ].strip()

                documentation.insert(
                    0,
                    content,
                )

                continue

            break

        if not documentation:

            return None

        return "\n".join(
            documentation
        ).strip()

    # ------------------------------------------------------------
    # CLEAN RUBYDOC
    # ------------------------------------------------------------

    @staticmethod
    def _clean_rubydoc(
        documentation: str,
    ) -> str:

        lines: list[str] = []

        for line in documentation.splitlines():

            line = line.strip()

            if line.startswith(
                "#"
            ):

                line = line[1:].strip()

            if line:

                lines.append(
                    line
                )

        return "\n".join(
            lines
        ).strip()

    # ------------------------------------------------------------
    # DOCUMENTATION TITLE
    # ------------------------------------------------------------

    @staticmethod
    def _documentation_title(
        documentation: str,
    ) -> str:

        for line in documentation.splitlines():

            line = line.strip()

            if not line:

                continue

            if line.startswith(
                "@"
            ):

                continue

            return line[:120]

        return "Ruby Documentation"