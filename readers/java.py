"""
BARKLY DOCS

Java Reader

Static structural reader for Java source files.

This reader does NOT execute Java code.

It translates Java source into the common Barkly Project Model:

    Java Source

        ↓

    JavaReader

        ↓

    Barkly Project Model

        ↓

    Documentation / Graph / Website

Supported file types:

    .java
"""

from __future__ import annotations

import re

from pathlib import Path
from typing import Any

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


class JavaReader(LanguageReader):
    """
    Static structural reader for Java source files.

    The reader analyzes Java source as text only.

    It never:
        - compiles Java
        - imports Java
        - executes Java
        - loads project dependencies
        - invokes the JVM
    """

    language = "Java"

    extensions = (".java",)

    version = "0.1.0"

    # ========================================================
    # REGEX
    # ========================================================

    _PACKAGE_RE = re.compile(
        r"""
        ^\s*
        package
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_.]*)
        \s*
        ;
        """,
        re.VERBOSE,
    )

    _IMPORT_RE = re.compile(
        r"""
        ^\s*
        import
        \s+
        (?P<static>static\s+)?
        (?P<name>[A-Za-z_][A-Za-z0-9_.$]*(?:\.\*)?)
        \s*
        ;
        """,
        re.VERBOSE,
    )

    _CLASS_RE = re.compile(
        r"""
        ^\s*
        (?P<annotations>(?:@\w+(?:\([^)]*\))?\s*)*)
        (?P<modifiers>
            (?:
                public
                |protected
                |private
                |abstract
                |final
                |static
                |sealed
                |non-sealed
                |strictfp
            )
            \s+
        )*
        class
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)
        (?P<generic>\s*<[^{};]*>)?
        (?:
            \s+
            extends
            \s+
            (?P<superclass>[A-Za-z_][A-Za-z0-9_.$]*(?:\s*<[^{};]*>)?)
        )?
        (?:
            \s+
            implements
            \s+
            (?P<interfaces>[^{]+)
        )?
        \s*
        \{
        """,
        re.VERBOSE,
    )

    _INTERFACE_RE = re.compile(
        r"""
        ^\s*
        (?P<annotations>(?:@\w+(?:\([^)]*\))?\s*)*)
        (?P<modifiers>
            (?:
                public
                |protected
                |private
                |abstract
                |static
                |sealed
                |non-sealed
            )
            \s+
        )*
        interface
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)
        (?P<generic>\s*<[^{};]*>)?
        (?:
            \s+
            extends
            \s+
            (?P<interfaces>[^{]+)
        )?
        \s*
        \{
        """,
        re.VERBOSE,
    )

    _ENUM_RE = re.compile(
        r"""
        ^\s*
        (?P<annotations>(?:@\w+(?:\([^)]*\))?\s*)*)
        (?P<modifiers>
            (?:
                public
                |protected
                |private
                |static
                |final
                |strictfp
            )
            \s+
        )*
        enum
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)
        (?:
            \s+
            implements
            \s+
            (?P<interfaces>[^{]+)
        )?
        \s*
        \{
        """,
        re.VERBOSE,
    )

    _RECORD_RE = re.compile(
        r"""
        ^\s*
        (?P<annotations>(?:@\w+(?:\([^)]*\))?\s*)*)
        (?P<modifiers>
            (?:
                public
                |protected
                |private
                |static
                |final
                |strictfp
            )
            \s+
        )*
        record
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)
        \s*
        \(
            (?P<components>[^)]*)
        \)
        (?:
            \s+
            implements
            \s+
            (?P<interfaces>[^{]+)
        )?
        \s*
        \{
        """,
        re.VERBOSE,
    )

    _METHOD_RE = re.compile(
        r"""
        ^\s*
        (?P<annotations>(?:@\w+(?:\([^)]*\))?\s*)*)
        (?P<modifiers>
            (?:
                public
                |protected
                |private
                |static
                |final
                |abstract
                |synchronized
                |native
                |strictfp
                |default
                |sealed
                |non-sealed
            )
            \s+
        )*
        (?P<type>
            (?:[\w.$<>\[\], ?]+)
        )
        \s+
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)
        \s*
        \(
            (?P<params>[^()]*(?:\([^()]*\)[^()]*)*)
        \)
        \s*
        (?:
            throws
            \s+
            (?P<throws>[^{;]+)
        )?
        \s*
        (?P<terminator>\{|;)
        """,
        re.VERBOSE,
    )

    _CONSTRUCTOR_RE = re.compile(
        r"""
        ^\s*
        (?P<annotations>(?:@\w+(?:\([^)]*\))?\s*)*)
        (?P<modifiers>
            (?:
                public
                |protected
                |private
                |synchronized
            )
            \s+
        )*
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)
        \s*
        \(
            (?P<params>[^()]*(?:\([^()]*\)[^()]*)*)
        \)
        \s*
        (?:
            throws
            \s+
            (?P<throws>[^{]+)
        )?
        \s*
        \{
        """,
        re.VERBOSE,
    )

    _FIELD_RE = re.compile(
        r"""
        ^\s*
        (?P<annotations>(?:@\w+(?:\([^)]*\))?\s*)*)
        (?P<modifiers>
            (?:
                public
                |protected
                |private
                |static
                |final
                |transient
                |volatile
                |synchronized
            )
            \s+
        )*
        (?P<type>
            [A-Za-z_$][A-Za-z0-9_$.$<>, ?\[\]]*
        )
        \s+
        (?P<declarations>
            [A-Za-z_$][A-Za-z0-9_$]*
            (?:\s*=\s*[^;]+)?
            (?:
                \s*,\s*
                [A-Za-z_$][A-Za-z0-9_$]*
                (?:\s*=\s*[^;]+)?
            )*
        )
        \s*
        ;
        """,
        re.VERBOSE,
    )

    _LOCAL_VARIABLE_RE = re.compile(
        r"""
        \b
        (?P<type>
            byte|short|int|long|float|double|boolean|char
            |String
            |[A-Z_$][A-Za-z0-9_$.$<>, ?\[\]]*
        )
        \s+
        (?P<name>[a-zA-Z_$][A-Za-z0-9_$]*)
        \s*
        =
        """,
        re.VERBOSE,
    )

    _JAVADOC_RE = re.compile(
        r"""
        ^\s*
        (?:
            /\*\*
            |
            \*
            |
            \*/
        )
        (?P<text>.*)
        """,
        re.VERBOSE,
    )

    _LINE_COMMENT_RE = re.compile(r"^\s*//\s?(?P<text>.*)$")

    _ANNOTATION_RE = re.compile(r"^\s*@(?P<name>[A-Za-z_][A-Za-z0-9_.]*)")

    # ========================================================
    # PUBLIC API
    # ========================================================

    def read(
        self,
        path: Path,
        project: Project,
    ) -> ReaderResult:
        """
        Analyze one Java source file.

        Java source is treated as data only.

        Java code is never imported, compiled, or executed.
        """

        warnings: list[str] = []
        errors: list[str] = []

        try:
            source = self.read_text(path)
        except Exception as exc:
            return ReaderResult(
                success=False,
                project=project,
                warnings=warnings,
                errors=[f"{path}: unable to read Java source: {exc}"],
                metadata={
                    "language": self.language,
                    "version": self.version,
                },
            )

        try:
            # ------------------------------------------------
            # FILE
            # ------------------------------------------------

            file_node = FileNode(
                path=str(path),
                language=self.language,
                size=len(
                    source.encode(
                        "utf-8",
                        errors="replace",
                    )
                ),
                metadata={
                    "reader": self.__class__.__name__,
                    "reader_version": self.version,
                },
            )

            project.add_file(file_node)

            # ------------------------------------------------
            # PACKAGE / FILE MODULE
            # ------------------------------------------------

            package_name = self._extract_package(source)

            module_name = package_name if package_name else self._module_name(path)

            file_module = ModuleNode(
                name=module_name,
                path=str(path),
                language=self.language,
                metadata={
                    "kind": "java_file",
                    "package": package_name,
                },
            )

            project.add_module(file_module)

            file_node.modules.append(module_name)

            # ------------------------------------------------
            # IMPORTS
            # ------------------------------------------------

            imports = self._extract_imports(
                source,
                path,
                project,
                file_module,
            )

            # ------------------------------------------------
            # STRUCTURES
            # ------------------------------------------------

            structures = self._scan_structures(source)

            classes = [
                item
                for item in structures
                if item["kind"]
                in {
                    "class",
                    "record",
                    "enum",
                    "interface",
                }
            ]

            # ------------------------------------------------
            # STRUCTURE NODES
            # ------------------------------------------------

            for structure in classes:
                name = structure["name"]
                kind = structure["kind"]

                # Use a package-qualified name for classes when possible.
                fq_name = f"{package_name}.{name}" if package_name else name

                bases = []

                if structure.get("superclass"):
                    bases.append(structure["superclass"])

                bases.extend(
                    structure.get(
                        "interfaces",
                        [],
                    )
                )

                methods = self._extract_methods(
                    structure["body"],
                    structure["body_start"],
                    name,
                )

                method_names = [method["name"] for method in methods]

                attributes = self._extract_fields(structure["body"])

                documentation = structure.get("documentation")

                class_node = ClassNode(
                    name=fq_name,
                    path=str(path),
                    language=self.language,
                    bases=bases,
                    methods=method_names,
                    attributes=attributes,
                    documentation=documentation,
                    line_start=structure["line_start"],
                    line_end=structure["line_end"],
                    metadata={
                        "java_kind": kind,
                        "package": package_name,
                        "simple_name": name,
                        "superclass": structure.get("superclass"),
                        "interfaces": structure.get(
                            "interfaces",
                            [],
                        ),
                        "annotations": structure.get(
                            "annotations",
                            [],
                        ),
                        "parent": structure.get("parent"),
                    },
                )

                project.add_class(class_node)

                # Record class membership using the qualified name.
                file_node.classes.append(fq_name)
                file_module.classes.append(fq_name)

                # --------------------------------------------
                # INHERITANCE / IMPLEMENTATION
                # --------------------------------------------

                if structure.get("superclass"):
                    project.add_relationship(
                        RelationshipNode(
                            source=fq_name,
                            target=structure["superclass"],
                            kind="inherits",
                            source_file=str(path),
                            evidence="DECLARED",
                        )
                    )

                for interface in structure.get(
                    "interfaces",
                    [],
                ):
                    project.add_relationship(
                        RelationshipNode(
                            source=fq_name,
                            target=interface,
                            kind=("implements" if kind != "interface" else "extends"),
                            source_file=str(path),
                            evidence="DECLARED",
                        )
                    )

                # --------------------------------------------
                # METHODS
                # --------------------------------------------

                for method in methods:
                    method_node = MethodNode(
                        name=method["name"],
                        path=str(path),
                        language=self.language,
                        parameters=self._parse_parameters(
                            method.get(
                                "params",
                                "",
                            )
                        ),
                        return_type=method.get("return_type"),
                        decorators=method.get(
                            "annotations",
                            [],
                        ),
                        documentation=method.get("documentation"),
                        line_start=method["line_start"],
                        line_end=method["line_end"],
                        class_name=fq_name,
                        metadata={
                            "java_kind": method.get(
                                "java_kind",
                                "method",
                            ),
                            "modifiers": method.get(
                                "modifiers",
                                [],
                            ),
                            "throws": method.get("throws"),
                            "constructor": method.get(
                                "constructor",
                                False,
                            ),
                        },
                    )

                    project.add_method(method_node)

                    project.add_relationship(
                        RelationshipNode(
                            source=fq_name,
                            target=method["name"],
                            kind="contains",
                            source_file=str(path),
                            evidence="DECLARED",
                        )
                    )

                # --------------------------------------------
                # RECORD COMPONENTS
                # --------------------------------------------

                for component in structure.get(
                    "components",
                    [],
                ):
                    project.add_variable(
                        VariableNode(
                            name=component,
                            path=str(path),
                            language=self.language,
                            type=None,
                            constant=False,
                            line=structure["line_start"],
                            metadata={
                                "java_kind": ("record_component"),
                                "class": fq_name,
                            },
                        )
                    )

            # ------------------------------------------------
            # TOP-LEVEL JAVA FUNCTIONS
            # ------------------------------------------------
            #
            # Java normally has no top-level functions.
            #
            # We intentionally do not turn methods into
            # FunctionNode objects here.
            #
            # They belong to their containing ClassNode and
            # are represented as MethodNode objects above.

            # ------------------------------------------------
            # VARIABLES / FIELDS
            # ------------------------------------------------

            self._extract_variables(
                source,
                path,
                project,
            )

            # ------------------------------------------------
            # DOCUMENTATION
            # ------------------------------------------------

            self._extract_documentation(
                source,
                path,
                project,
            )

            # ------------------------------------------------
            # FILE METADATA
            # ------------------------------------------------

            file_node.metadata.update(
                {
                    "java_version": "unknown",
                    "package": package_name,
                    "classes": [
                        (
                            f"{package_name}.{structure['name']}"
                            if package_name
                            else structure["name"]
                        )
                        for structure in classes
                    ],
                    "imports": [item["name"] for item in imports],
                    "parser": ("static-java-structural-scanner"),
                }
            )

            return ReaderResult(
                success=True,
                project=project,
                warnings=warnings,
                errors=errors,
                metadata={
                    "language": self.language,
                    "version": self.version,
                    "parser": ("static-java-structural-scanner"),
                    "static_analysis": True,
                    "java_version": "unknown",
                    "classes": len(classes),
                    "methods": sum(
                        len(
                            self._extract_methods(
                                item["body"],
                                item["body_start"],
                                item["name"],
                            )
                        )
                        for item in classes
                    ),
                },
            )

        except Exception as exc:
            errors.append(f"{path}: Java structural analysis failed: {exc}")

            return ReaderResult(
                success=False,
                project=project,
                warnings=warnings,
                errors=errors,
                metadata={
                    "language": self.language,
                    "version": self.version,
                },
            )

    # ========================================================
    # PACKAGE
    # ========================================================

    def _extract_package(
        self,
        source: str,
    ) -> str | None:
        """
        Extract the Java package declaration.
        """

        for raw_line in source.splitlines():
            line = self._strip_java_comment(raw_line).strip()

            match = self._PACKAGE_RE.match(line)

            if match:
                return match.group("name")

        return None

    # ========================================================
    # STRUCTURE SCANNER
    # ========================================================

    def _scan_structures(
        self,
        source: str,
    ) -> list[dict[str, Any]]:
        """
        Scan Java classes, interfaces, enums, and records.

        This is intentionally structural rather than a full
        Java parser.

        Braces are tracked so nested methods and blocks do not
        prematurely terminate a class.
        """

        lines = source.splitlines(keepends=True)

        structures: list[dict[str, Any]] = []

        offsets: list[int] = []

        offset = 0

        for line in lines:
            offsets.append(offset)
            offset += len(line)

        stack: list[dict[str, Any]] = []

        brace_depth = 0

        for index, raw_line in enumerate(lines):
            clean_line = self._strip_java_comments(raw_line).strip()

            if not clean_line:
                continue

            line_start_offset = offsets[index]

            # ------------------------------------------------
            # STRUCTURE DECLARATIONS
            # ------------------------------------------------

            match = self._match_structure(clean_line)

            if match:
                kind = match["kind"]

                structure = {
                    "kind": kind,
                    "name": match["name"],
                    "superclass": match.get("superclass"),
                    "interfaces": match.get(
                        "interfaces",
                        [],
                    ),
                    "components": match.get(
                        "components",
                        [],
                    ),
                    "annotations": match.get(
                        "annotations",
                        [],
                    ),
                    "line_start": index + 1,
                    "line_end": None,
                    "offset": line_start_offset,
                    "body_start": (line_start_offset + raw_line.find("{") + 1),
                    "body": "",
                    "parent": self._nearest_parent(stack),
                    "documentation": (
                        self._documentation_before(
                            lines,
                            index,
                        )
                    ),
                    "brace_depth": (brace_depth + 1),
                }

                stack.append(
                    {
                        "kind": kind,
                        "structure": structure,
                        "depth": (brace_depth + 1),
                    }
                )

            # ------------------------------------------------
            # BRACES
            # ------------------------------------------------

            opens = clean_line.count("{")
            closes = clean_line.count("}")

            brace_depth += opens - closes

            # ------------------------------------------------
            # CLOSE STRUCTURES
            # ------------------------------------------------

            while stack:
                entry = stack[-1]

                if brace_depth >= entry["depth"]:
                    break

                stack.pop()

                structure = entry["structure"]

                structure["line_end"] = index + 1

                closing_offset = offsets[index] + len(raw_line)

                structure["body"] = source[structure["body_start"] : closing_offset]

                structures.append(structure)

        # ----------------------------------------------------
        # CONSERVATIVE CLOSE
        # ----------------------------------------------------

        while stack:
            entry = stack.pop()

            structure = entry["structure"]

            structure["line_end"] = len(lines)

            structure["body"] = source[structure["body_start"] :]

            structures.append(structure)

        structures.sort(
            key=lambda item: (
                item["line_start"],
                item["line_end"] or item["line_start"],
            )
        )

        return structures

    # ========================================================
    # STRUCTURE MATCHING
    # ========================================================

    def _match_structure(
        self,
        line: str,
    ) -> dict[str, Any] | None:
        """
        Match one Java structure declaration.
        """

        match = self._CLASS_RE.match(line)

        if match:
            return {
                "kind": "class",
                "name": match.group("name"),
                "superclass": match.group("superclass"),
                "interfaces": (self._split_type_list(match.group("interfaces"))),
                "annotations": self._parse_annotations(match.group("annotations")),
            }

        match = self._INTERFACE_RE.match(line)

        if match:
            return {
                "kind": "interface",
                "name": match.group("name"),
                "superclass": None,
                "interfaces": (self._split_type_list(match.group("interfaces"))),
                "annotations": self._parse_annotations(match.group("annotations")),
            }

        match = self._ENUM_RE.match(line)

        if match:
            return {
                "kind": "enum",
                "name": match.group("name"),
                "superclass": None,
                "interfaces": (self._split_type_list(match.group("interfaces"))),
                "annotations": self._parse_annotations(match.group("annotations")),
            }

        match = self._RECORD_RE.match(line)

        if match:
            return {
                "kind": "record",
                "name": match.group("name"),
                "superclass": None,
                "interfaces": (self._split_type_list(match.group("interfaces"))),
                "components": (self._parse_parameters(match.group("components"))),
                "annotations": self._parse_annotations(match.group("annotations")),
            }

        return None

    # ========================================================
    # METHODS
    # ========================================================

    def _extract_methods(
        self,
        body: str,
        body_start_offset: int,
        class_name: str,
    ) -> list[dict[str, Any]]:
        """
        Extract Java methods and constructors.

        This is intentionally conservative.

        A declaration must look like a Java method or
        constructor before it becomes a MethodNode.
        """

        lines = body.splitlines(keepends=True)

        methods: list[dict[str, Any]] = []

        offsets: list[int] = []

        offset = body_start_offset

        for line in lines:
            offsets.append(offset)
            offset += len(line)

        brace_depth = 0

        for index, raw_line in enumerate(lines):
            clean_line = self._strip_java_comments(raw_line).strip()

            if not clean_line:
                continue

            # ------------------------------------------------
            # CONSTRUCTOR
            # ------------------------------------------------

            constructor = self._CONSTRUCTOR_RE.match(clean_line)

            if constructor:
                if constructor.group("name") == class_name:
                    method = {
                        "name": class_name,
                        "params": (constructor.group("params") or ""),
                        "return_type": None,
                        "throws": (constructor.group("throws")),
                        "annotations": self._parse_annotations(
                            constructor.group("annotations")
                        ),
                        "modifiers": self._parse_modifiers(
                            constructor.group("modifiers")
                        ),
                        "line_start": (
                            self._line_number_from_offset(
                                body,
                                offsets[index],
                            )
                        ),
                        "line_end": (
                            self._find_block_end(
                                lines,
                                index,
                            )
                        ),
                        "documentation": (
                            self._documentation_before(
                                lines,
                                index,
                            )
                        ),
                        "constructor": True,
                        "java_kind": "constructor",
                    }

                    methods.append(method)

                    continue

            # ------------------------------------------------
            # METHOD
            # ------------------------------------------------

            match = self._METHOD_RE.match(clean_line)

            if match:
                terminator = match.group("terminator")

                method = {
                    "name": match.group("name"),
                    "params": (match.group("params") or ""),
                    "return_type": (match.group("type")),
                    "throws": (match.group("throws")),
                    "annotations": self._parse_annotations(match.group("annotations")),
                    "modifiers": self._parse_modifiers(match.group("modifiers")),
                    "line_start": (
                        self._line_number_from_offset(
                            body,
                            offsets[index],
                        )
                    ),
                    "line_end": None,
                    "documentation": (
                        self._documentation_before(
                            lines,
                            index,
                        )
                    ),
                    "constructor": False,
                    "java_kind": "method",
                }

                if terminator == ";":
                    method["line_end"] = method["line_start"]

                else:
                    method["line_end"] = self._find_block_end(
                        lines,
                        index,
                    )

                methods.append(method)

                continue

            brace_depth += clean_line.count("{") - clean_line.count("}")

        methods.sort(
            key=lambda item: (
                item["line_start"],
                item["line_end"] or item["line_start"],
            )
        )

        return methods

    # ========================================================
    # FIELDS
    # ========================================================

    def _extract_fields(
        self,
        body: str,
    ) -> list[str]:
        """
        Extract obvious class fields.

        Local variables inside method bodies are intentionally
        not treated as class attributes here.
        """

        fields: list[str] = []

        for raw_line in body.splitlines():
            line = self._strip_java_comments(raw_line).strip()

            if not line:
                continue

            if "(" in line:
                continue

            match = self._FIELD_RE.match(line)

            if not match:
                continue

            declarations = match.group("declarations")

            for declaration in declarations.split(","):
                name = declaration.split(
                    "=",
                    1,
                )[0].strip()

                if re.match(
                    r"^[A-Za-z_$][A-Za-z0-9_$]*$",
                    name,
                ):
                    fields.append(name)

        return fields

    # ========================================================
    # VARIABLES
    # ========================================================

    def _extract_variables(
        self,
        source: str,
        path: Path,
        project: Project,
    ) -> None:
        """
        Extract obvious Java fields and local declarations.

        This remains intentionally conservative.
        """

        seen: set[tuple[str, str]] = set()

        for line_number, raw_line in enumerate(
            source.splitlines(),
            start=1,
        ):
            line = self._strip_java_comments(raw_line).strip()

            if not line:
                continue

            # ------------------------------------------------
            # FIELD / DECLARATION
            # ------------------------------------------------

            field_match = self._FIELD_RE.match(line)

            if field_match:
                variable_type = field_match.group("type")

                declarations = field_match.group("declarations")

                for declaration in declarations.split(","):
                    parts = declaration.split(
                        "=",
                        1,
                    )

                    name = parts[0].strip()

                    value = parts[1].strip() if len(parts) > 1 else None

                    if not re.match(
                        r"^[A-Za-z_$][A-Za-z0-9_$]*$",
                        name,
                    ):
                        continue

                    key = (
                        "java_variable",
                        name,
                    )

                    if key in seen:
                        continue

                    seen.add(key)

                    modifiers = self._parse_modifiers(field_match.group("modifiers"))

                    project.add_variable(
                        VariableNode(
                            name=name,
                            path=str(path),
                            language=self.language,
                            type=variable_type,
                            value=value,
                            constant=("final" in modifiers),
                            line=line_number,
                            metadata={
                                "java_kind": "field",
                                "modifiers": modifiers,
                            },
                        )
                    )

            # ------------------------------------------------
            # LOCAL VARIABLE
            # ------------------------------------------------

            local_match = self._LOCAL_VARIABLE_RE.search(line)

            if local_match:
                name = local_match.group("name")

                variable_type = local_match.group("type")

                key = (
                    "java_local_variable",
                    name,
                )

                if key not in seen:
                    seen.add(key)

                    project.add_variable(
                        VariableNode(
                            name=name,
                            path=str(path),
                            language=self.language,
                            type=variable_type,
                            constant=False,
                            line=line_number,
                            metadata={
                                "java_kind": ("local_variable"),
                            },
                        )
                    )

    # ========================================================
    # IMPORTS
    # ========================================================

    def _extract_imports(
        self,
        source: str,
        path: Path,
        project: Project,
        file_module: ModuleNode,
    ) -> list[dict[str, str]]:
        """
        Extract Java import declarations.
        """

        imports: list[dict[str, str]] = []

        for line in source.splitlines():
            stripped = line.strip()

            match = self._IMPORT_RE.match(stripped)

            if not match:
                continue

            name = match.group("name")

            is_static = bool(match.group("static"))

            kind = "static_import" if is_static else "import"

            imports.append(
                {
                    "name": name,
                    "kind": kind,
                }
            )

            project.add_import(
                ImportNode(
                    source_file=str(path),
                    target=name,
                    language=self.language,
                    metadata={
                        "java_kind": kind,
                        "static": is_static,
                    },
                )
            )

            project.add_relationship(
                RelationshipNode(
                    source=str(path),
                    target=name,
                    kind="imports",
                    source_file=str(path),
                    evidence="DECLARED",
                )
            )

            file_module.imports.append(name)

        return imports

    # ========================================================
    # DOCUMENTATION
    # ========================================================

    def _extract_documentation(
        self,
        source: str,
        path: Path,
        project: Project,
    ) -> None:
        """
        Extract JavaDoc and documentation comments.
        """

        lines = source.splitlines()

        current: list[str] = []
        start_line: int | None = None
        in_javadoc = False

        for index, raw_line in enumerate(
            lines,
            start=1,
        ):
            line = raw_line.strip()

            # ------------------------------------------------
            # JAVADOC START
            # ------------------------------------------------

            if line.startswith("/**"):
                in_javadoc = True

                start_line = index

                text = line[3:]

                if text.endswith("*/"):
                    text = text[:-2]
                    in_javadoc = False

                text = self._clean_javadoc_line(text)

                if text:
                    current.append(text)

                if not in_javadoc:
                    self._finish_documentation(
                        current,
                        start_line,
                        index,
                        path,
                        project,
                    )

                    current = []
                    start_line = None

                continue

            # ------------------------------------------------
            # JAVADOC BODY
            # ------------------------------------------------

            if in_javadoc:
                text = line

                if text.endswith("*/"):
                    text = text[:-2]
                    in_javadoc = False

                text = self._clean_javadoc_line(text)

                if text:
                    current.append(text)

                if not in_javadoc:
                    self._finish_documentation(
                        current,
                        start_line,
                        index,
                        path,
                        project,
                    )

                    current = []
                    start_line = None

                continue

        if current and start_line is not None:
            self._finish_documentation(
                current,
                start_line,
                len(lines),
                path,
                project,
            )

    def _finish_documentation(
        self,
        lines: list[str],
        start_line: int | None,
        end_line: int,
        path: Path,
        project: Project,
    ) -> None:
        """
        Add one JavaDoc block to the Project Model.
        """

        text = "\n".join(lines).strip()

        if not text:
            return

        title = self._documentation_title(text)

        project.add_documentation(
            DocumentationNode(
                title=title,
                path=str(path),
                kind="javadoc",
                headings=[title],
                metadata={
                    "line_start": start_line,
                    "line_end": end_line,
                    "language": self.language,
                },
            )
        )

    # ========================================================
    # HELPERS
    # ========================================================

    def _module_name(
        self,
        path: Path,
    ) -> str:
        """
        Convert a Java filename into a logical file module name.
        """

        return path.stem

    def _nearest_parent(
        self,
        stack: list[dict[str, Any]],
    ) -> str | None:
        """
        Return the nearest containing Java structure.
        """

        for entry in reversed(stack):
            structure = entry.get("structure")

            if structure:
                return structure.get("name")

        return None

    def _split_type_list(
        self,
        value: str | None,
    ) -> list[str]:
        """
        Split Java extends / implements declarations.
        """

        if not value:
            return []

        result: list[str] = []

        for item in value.split(","):
            item = item.strip()

            if not item:
                continue

            # Remove generic type parameters from the
            # relationship name only when necessary.
            item = re.sub(
                r"<.*>",
                "",
                item,
            ).strip()

            result.append(item)

        return result

    def _parse_parameters(
        self,
        params: str,
    ) -> list[str]:
        """
        Parse a Java parameter list conservatively.

        The original parameter text is preserved as individual
        parameter strings where possible.
        """

        if not params:
            return []

        result: list[str] = []

        current: list[str] = []

        depth = 0

        quote: str | None = None

        escaped = False

        for char in params:
            if escaped:
                current.append(char)
                escaped = False
                continue

            if char == "\\":
                current.append(char)
                escaped = True
                continue

            if quote:
                current.append(char)

                if char == quote:
                    quote = None

                continue

            if char in {
                "'",
                '"',
            }:
                quote = char
                current.append(char)
                continue

            if char in "([{<":
                depth += 1
                current.append(char)
                continue

            if char in ")]}>":
                depth = max(
                    0,
                    depth - 1,
                )
                current.append(char)
                continue

            if char == "," and depth == 0:
                item = "".join(current).strip()

                if item:
                    result.append(item)

                current = []

                continue

            current.append(char)

        item = "".join(current).strip()

        if item:
            result.append(item)

        return result

    def _parse_annotations(
        self,
        value: str | None,
    ) -> list[str]:
        """
        Extract annotation names from a declaration prefix.
        """

        if not value:
            return []

        return [match.group("name") for match in self._ANNOTATION_RE.finditer(value)]

    def _parse_modifiers(
        self,
        value: str | None,
    ) -> list[str]:
        """
        Extract Java modifiers.
        """

        if not value:
            return []

        allowed = {
            "public",
            "protected",
            "private",
            "abstract",
            "final",
            "static",
            "sealed",
            "non-sealed",
            "strictfp",
            "synchronized",
            "native",
            "default",
            "transient",
            "volatile",
        }

        return [token for token in value.split() if token in allowed]

    def _find_block_end(
        self,
        lines: list[str],
        start_index: int,
    ) -> int:
        """
        Find the approximate ending line of a Java brace block.

        Returns a 1-based line number.
        """

        depth = 0

        started = False

        for index in range(
            start_index,
            len(lines),
        ):
            line = self._strip_java_comments(lines[index])

            for char in line:
                if char == "{":
                    depth += 1
                    started = True

                elif char == "}":
                    depth -= 1

            if started and depth <= 0:
                return index + 1

        return len(lines)

    def _documentation_before(
        self,
        lines: list[str],
        index: int,
    ) -> str | None:
        """
        Return contiguous documentation comments immediately
        preceding a declaration.

        Supports simple // documentation and JavaDoc blocks.
        """

        docs: list[str] = []

        cursor = index - 1

        while cursor >= 0:
            line = lines[cursor].strip()

            if not line:
                if docs:
                    break

                cursor -= 1
                continue

            if line.startswith("*/"):
                cursor -= 1

                while cursor >= 0:
                    current = lines[cursor].strip()

                    if current.startswith("/**"):
                        text = current[3:]

                        if text:
                            docs.append(self._clean_javadoc_line(text))

                        cursor -= 1
                        break

                    if current.startswith("*"):
                        docs.append(self._clean_javadoc_line(current))

                    cursor -= 1

                continue

            if line.startswith("/**"):
                text = line[3:]

                if text.endswith("*/"):
                    text = text[:-2]

                text = self._clean_javadoc_line(text)

                if text:
                    docs.append(text)

                cursor -= 1
                continue

            if line.startswith("//"):
                text = line[2:].strip()

                if text:
                    docs.append(text)

                cursor -= 1
                continue

            if line.startswith("*"):
                docs.append(self._clean_javadoc_line(line))

                cursor -= 1
                continue

            break

        if not docs:
            return None

        docs.reverse()

        return "\n".join(item for item in docs if item).strip()

    def _clean_javadoc_line(
        self,
        text: str,
    ) -> str:
        """
        Clean one JavaDoc line.
        """

        text = text.strip()

        if text.startswith("*"):
            text = text[1:].strip()

        return text.strip()

    def _documentation_title(
        self,
        text: str,
    ) -> str:
        """
        Generate a deterministic documentation title.
        """

        first_line = text.splitlines()[0].strip()

        if not first_line:
            return "Java Documentation"

        return first_line[:120]

    def _line_number_from_offset(
        self,
        text: str,
        offset: int,
    ) -> int:
        """
        Convert a character offset into a 1-based line number.
        """

        offset = max(
            0,
            min(
                offset,
                len(text),
            ),
        )

        return (
            text.count(
                "\n",
                0,
                offset,
            )
            + 1
        )

    def _strip_java_comment(
        self,
        line: str,
    ) -> str:
        """
        Strip Java // comments while attempting to preserve
        comment-like characters inside quoted strings.

        Block comments are handled conservatively elsewhere.
        """

        result: list[str] = []

        quote: str | None = None

        escaped = False

        index = 0

        while index < len(line):
            char = line[index]

            if escaped:
                result.append(char)
                escaped = False
                index += 1
                continue

            if char == "\\":
                result.append(char)
                escaped = True
                index += 1
                continue

            if quote:
                result.append(char)

                if char == quote:
                    quote = None

                index += 1
                continue

            if char in {
                '"',
                "'",
            }:
                quote = char
                result.append(char)
                index += 1
                continue

            if char == "/" and index + 1 < len(line) and line[index + 1] == "/":
                break

            result.append(char)

            index += 1

        return "".join(result)

    def _strip_java_comments(self, source: str) -> str:
        """
        Remove Java comments while preserving strings, character literals,
        and line structure.

        Static analysis only:
        - does not compile Java
        - does not execute Java
        - preserves newlines so line numbers remain stable
        """

        result = []
        i = 0
        n = len(source)

        in_string = False
        in_char = False
        in_line_comment = False
        in_block_comment = False
        escaped = False

        while i < n:
            ch = source[i]
            nxt = source[i + 1] if i + 1 < n else ""

            if in_line_comment:
                if ch == "\n":
                    in_line_comment = False
                    result.append("\n")
                else:
                    result.append(" ")
                i += 1
                continue

            if in_block_comment:
                if ch == "*" and nxt == "/":
                    result.append(" ")
                    result.append(" ")
                    i += 2
                    in_block_comment = False
                    continue

                if ch == "\n":
                    result.append("\n")
                else:
                    result.append(" ")

                i += 1
                continue

            if in_string:
                result.append(ch)

                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False

                i += 1
                continue

            if in_char:
                result.append(ch)

                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == "'":
                    in_char = False

                i += 1
                continue

            # Start // comment
            if ch == "/" and nxt == "/":
                result.append(" ")
                result.append(" ")
                i += 2
                in_line_comment = True
                continue

            # Start /* ... */ comment
            if ch == "/" and nxt == "*":
                result.append(" ")
                result.append(" ")
                i += 2
                in_block_comment = True
                continue

            # Start string
            if ch == '"':
                result.append(ch)
                in_string = True
                escaped = False
                i += 1
                continue

            # Start character literal
            if ch == "'":
                result.append(ch)
                in_char = True
                escaped = False
                i += 1
                continue

            result.append(ch)
            i += 1

        return "".join(result)
