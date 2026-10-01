# Barkly Docs

Human-centered documentation and knowledge infrastructure for Barkly Labs.

Barkly Docs is a static analysis project for turning source code and project artifacts into a common, structured understanding of a software system. The repository currently contains a small, dependency-free core, a discovery layer, and static readers that translate source files into the shared Barkly Project Model.

## Current status

The implementation in this repository is a work in progress. It currently supports:

- project discovery over a directory tree
- file-type-based reader selection
- Python AST extraction into the shared project model
- JavaScript, Java, Ruby, and Rust static readers
- project summaries printed by the CLI
- optional HTML website generation from the shared project model
- no graph renderer, no explanation layer, and no full Markdown/JSON generation pipeline beyond the static HTML site

## Supported CLI

The current CLI supports two working modes:

1. analyze a project directory and print a project summary
2. generate a small static HTML documentation site in an output directory

```bash
python -m cli .
python -m cli . --name BarklyDocs
python -m cli . --name BarklyDocs --output docs-site
```

For compatibility with the repository root entry point, this also works:

```bash
python __main__.py .
python __main__.py . --name BarklyDocs
python __main__.py . --name BarklyDocs --output docs-site
```

The CLI accepts:

- positional `project`: path to the project to analyze
- optional `--name`: display name for the project in the output
- optional `-o` / `--output`: output directory for a static HTML website

There is no `barkly_docs` package entry point in this repository, and no `init` / `generate` subcommands are implemented beyond the optional HTML output path above.

## Architecture

```text
SOURCE FILES
  ├── Python
  ├── JavaScript
  ├── Java
  ├── Ruby
  └── Rust
        ↓
PROJECT DISCOVERY
        ↓
READERS / LANGUAGE ANALYZERS
        ↓
BARKLY PROJECT MODEL
        ↓
PROJECT SUMMARY / FUTURE GRAPH / RENDERERS
```

## Design principles

1. Human first.
2. Documentation is infrastructure.
3. Show the shape first; reveal details when needed.
4. Never present inferred information as confirmed fact.
5. Make generated output readable by humans and useful to machines.
6. Build the documentation system against real Barkly projects.
7. Keep the system open to modification.

## Development status

This repository retains an earlier prototype alongside the newer shared model and reader architecture. The prototype scripts are intentionally kept in place while the core project-discovery and model layers are being stabilized.