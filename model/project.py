"""
BARKLY DOCS
Project Model

The common language shared by every Barkly Docs reader.

Language readers should translate source code into these structures
instead of inventing their own representations.

Design principle:

    Source Code
        ↓
    Language Reader
        ↓
    Barkly Project Model
        ↓
    Documentation / Graph / Website
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .relationships import RelationshipEngine


EVIDENCE_STATUS = {
    "DECLARED",
    "DETECTED",
    "INFERRED",
    "UNKNOWN",
}


# ============================================================
# CORE PROJECT
# ============================================================


@dataclass
class Project:
    """
    Represents an entire software project.
    """

    name: str
    root: str

    files: list["FileNode"] = field(default_factory=list)
    modules: list["ModuleNode"] = field(default_factory=list)
    components: list["ComponentNode"] = field(default_factory=list)

    functions: list["FunctionNode"] = field(default_factory=list)
    methods: list["MethodNode"] = field(default_factory=list)
    classes: list["ClassNode"] = field(default_factory=list)
    interfaces: list["InterfaceNode"] = field(default_factory=list)
    variables: list["VariableNode"] = field(default_factory=list)
    data: list["DataNode"] = field(default_factory=list)

    routes: list["RouteNode"] = field(default_factory=list)
    endpoints: list["EndpointNode"] = field(default_factory=list)

    imports: list["ImportNode"] = field(default_factory=list)
    exports: list["ExportNode"] = field(default_factory=list)
    dependencies: list["DependencyNode"] = field(default_factory=list)

    configurations: list["ConfigurationNode"] = field(default_factory=list)
    tests: list["TestNode"] = field(default_factory=list)
    documentation: list["DocumentationNode"] = field(default_factory=list)

    relationships: list["RelationshipNode"] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
    relationship_engine: "RelationshipEngine | None" = field(
        default=None,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        from .relationships import RelationshipEngine

        self.relationship_engine = RelationshipEngine(self)

    def add_file(self, node: "FileNode") -> None:
        if any(existing.path == node.path for existing in self.files):
            return
        self.files.append(node)

    def add_module(self, node: "ModuleNode") -> None:
        if any(
            existing.name == node.name and existing.path == node.path
            for existing in self.modules
        ):
            return
        self.modules.append(node)

    def add_function(self, node: "FunctionNode") -> None:
        if any(
            existing.name == node.name
            and existing.path == node.path
            and getattr(existing, "line_start", None)
            == getattr(node, "line_start", None)
            for existing in self.functions
        ):
            return
        self.functions.append(node)

    def add_method(self, node: "MethodNode") -> None:
        if any(
            existing.name == node.name
            and existing.path == node.path
            and getattr(existing, "class_name", None)
            == getattr(node, "class_name", None)
            and getattr(existing, "line_start", None)
            == getattr(node, "line_start", None)
            for existing in self.methods
        ):
            return
        self.methods.append(node)

    def add_class(self, node: "ClassNode") -> None:
        if any(
            existing.name == node.name and existing.path == node.path
            for existing in self.classes
        ):
            return
        self.classes.append(node)

    def add_variable(self, node: "VariableNode") -> None:
        if any(
            existing.name == node.name
            and existing.path == node.path
            and existing.line == node.line
            for existing in self.variables
        ):
            return
        self.variables.append(node)

    def add_data(self, node: "DataNode") -> None:
        if any(
            existing.name == node.name
            and existing.path == node.path
            and existing.kind == node.kind
            and getattr(existing, "value_type", None)
            == getattr(node, "value_type", None)
            for existing in self.data
        ):
            return
        self.data.append(node)

    def add_import(self, node: "ImportNode") -> None:
        if any(
            existing.source_file == node.source_file
            and existing.target == node.target
            and existing.alias == node.alias
            for existing in self.imports
        ):
            return
        self.imports.append(node)

    def add_relationship(self, node: "RelationshipNode") -> None:
        if self.relationship_engine is None:
            self.__post_init__()

        self.relationship_engine.store(node)

    def evidence_summary(self) -> dict[str, int]:
        """Return relationship totals by evidence label."""

        counts = {label: 0 for label in EVIDENCE_STATUS}
        for relationship in self.relationships:
            key = (
                relationship.evidence
                if relationship.evidence in EVIDENCE_STATUS
                else "UNKNOWN"
            )
            counts[key] = counts.get(key, 0) + 1
        return counts

    def add_component(self, node: "ComponentNode") -> None:
        self.components.append(node)

    def add_interface(self, node: "InterfaceNode") -> None:
        self.interfaces.append(node)

    def add_route(self, node: "RouteNode") -> None:
        self.routes.append(node)

    def add_endpoint(self, node: "EndpointNode") -> None:
        identity = (node.metadata or {}).get("id")
        for existing in self.endpoints:
            existing_identity = (existing.metadata or {}).get("id")
            if identity and existing_identity == identity:
                return
            if (
                not identity
                and existing.method == node.method
                and existing.path == node.path
                and existing.source_file == node.source_file
                and (existing.metadata or {}).get("line") == (node.metadata or {}).get("line")
            ):
                return
        self.endpoints.append(node)

    def add_export(self, node: "ExportNode") -> None:
        self.exports.append(node)

    def add_dependency(self, node: "DependencyNode") -> None:
        self.dependencies.append(node)

    def add_configuration(self, node: "ConfigurationNode") -> None:
        self.configurations.append(node)

    def add_test(self, node: "TestNode") -> None:
        self.tests.append(node)

    def add_documentation(self, node: "DocumentationNode") -> None:
        self.documentation.append(node)

    def summary(self) -> dict[str, int]:
        """
        Return a simple structural summary.

        This is deliberately deterministic.
        """
        return {
            "files": len(self.files),
            "modules": len(self.modules),
            "components": len(self.components),
            "functions": len(self.functions),
            "methods": len(self.methods),
            "classes": len(self.classes),
            "interfaces": len(self.interfaces),
            "variables": len(self.variables),
            "routes": len(self.routes),
            "endpoints": len(self.endpoints),
            "imports": len(self.imports),
            "exports": len(self.exports),
            "dependencies": len(self.dependencies),
            "configurations": len(self.configurations),
            "tests": len(self.tests),
            "documentation": len(self.documentation),
            "relationships": len(self.relationships),
        }


# ============================================================
# FILES
# ============================================================


@dataclass
class FileNode:
    """
    Represents a source or project file.
    """

    path: str
    language: str | None = None
    size: int = 0

    generated: bool = False
    ignored: bool = False

    modules: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return Path(self.path).name


# ============================================================
# MODULES
# ============================================================


@dataclass
class ModuleNode:
    """
    Represents a logical source module.
    """

    name: str
    path: str

    language: str | None = None

    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)

    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)

    documentation: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# COMPONENTS
# ============================================================


@dataclass
class ComponentNode:
    """
    Represents a reusable project component.

    This is intentionally language-neutral.

    Examples:
        Astro component
        UI component
        service
        subsystem
        hardware abstraction
    """

    name: str
    path: str | None = None

    kind: str = "component"

    props: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    documentation: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# FUNCTIONS
# ============================================================


@dataclass
class FunctionNode:
    """
    Represents a standalone function.
    """

    name: str
    path: str

    language: str | None = None

    parameters: list[str] = field(default_factory=list)

    return_type: str | None = None

    decorators: list[str] = field(default_factory=list)

    documentation: str | None = None

    line_start: int | None = None
    line_end: int | None = None

    async_function: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# METHODS
# ============================================================


@dataclass
class MethodNode(FunctionNode):
    """
    Represents a function belonging to a class or component.
    """

    class_name: str | None = None


# ============================================================
# CLASSES
# ============================================================


@dataclass
class ClassNode:
    """
    Represents a class.
    """

    name: str
    path: str

    language: str | None = None

    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)

    methods: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)

    documentation: str | None = None

    line_start: int | None = None
    line_end: int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# INTERFACES
# ============================================================


@dataclass
class InterfaceNode:
    """
    Represents a language-level interface/type contract.

    Particularly useful for TypeScript.
    """

    name: str
    path: str

    language: str | None = None

    properties: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)

    documentation: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# VARIABLES
# ============================================================


@dataclass
class VariableNode:
    """
    Represents a meaningful variable or constant declaration.
    """

    name: str
    path: str

    language: str | None = None

    type: str | None = None
    value: str | None = None

    constant: bool = False

    line: int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# DATA (STRUCTURED FILE CONTENT)
# ============================================================


@dataclass
class DataNode:
    """
    Represents a structured JSON-like value discovered in a data file.

    `kind` records the JSON container or primitive category; `value_type`
    preserves the exact type, while `keys` captures object member names or
    array indexes in a stable, readable form.
    """

    name: str
    path: str

    language: str | None = None

    kind: str = "object"
    value_type: str | None = None
    keys: list[str] = field(default_factory=list)
    value: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# ROUTES
# ============================================================


@dataclass
class RouteNode:
    """
    Represents a navigable application/site route.
    """

    path: str
    source_file: str | None = None

    framework: str | None = None

    component: str | None = None

    methods: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# API ENDPOINTS
# ============================================================


@dataclass
class EndpointNode:
    """
    Represents an API endpoint.
    """

    path: str
    method: str

    source_file: str | None = None

    handler: str | None = None

    parameters: list[str] = field(default_factory=list)

    documentation: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# IMPORTS
# ============================================================


@dataclass
class ImportNode:
    """
    Represents an import/dependency relationship discovered
    directly from source code.
    """

    source_file: str
    target: str

    language: str | None = None

    names: list[str] = field(default_factory=list)

    alias: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# EXPORTS
# ============================================================


@dataclass
class ExportNode:
    """
    Represents an exported symbol.
    """

    source_file: str
    name: str

    language: str | None = None

    kind: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# DEPENDENCIES
# ============================================================


@dataclass
class DependencyNode:
    """
    Represents an external or project dependency.
    """

    name: str

    source: str | None = None
    version: str | None = None

    kind: str = "runtime"

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# CONFIGURATION
# ============================================================


@dataclass
class ConfigurationNode:
    """
    Represents project configuration.
    """

    name: str
    path: str

    kind: str | None = None

    values: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# TESTS
# ============================================================


@dataclass
class TestNode:
    """
    Represents a discovered test.
    """

    name: str
    path: str

    framework: str | None = None

    target: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# DOCUMENTATION
# ============================================================


@dataclass
class DocumentationNode:
    """
    Represents project knowledge discovered from documentation.
    """

    title: str
    path: str

    kind: str = "markdown"

    headings: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# RELATIONSHIPS
# ============================================================


@dataclass
class RelationshipNode:
    """
    Represents a relationship between two project objects.

    Examples:

        module imports module
        class inherits class
        component uses component
        route renders component
        function calls function
        documentation describes component
    """

    source: str
    target: str

    kind: str

    source_file: str | None = None
    evidence: str = "DETECTED"
    source_location: dict[str, Any] | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.evidence not in EVIDENCE_STATUS:
            self.evidence = "UNKNOWN"

        if self.source_location is not None and not isinstance(
            self.source_location,
            dict,
        ):
            raise TypeError("source_location must be a dict or None")
