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
- Structurizr DSL generation for a project-level C4 container view
- optional Structurizr Lite rendering through Docker Compose
- no function-level graph is used for the project architecture overview

## Supported CLI

The main command now runs the full local workflow:

1. analyze the selected project
2. generate the Barkly Docs HTML site and Structurizr workspace
3. start Structurizr Lite with Docker Compose
4. start the local documentation preview server
5. open the documentation index page in your default browser

```powershell
python __main__.py .
```

Choose a different project name or output folder when needed:

```powershell
python __main__.py . --name BarklyDocs --output docs-site
```

The generated documentation is served by nginx in Docker at `http://127.0.0.1:8000/`. The project-level Structurizr graph is served by Structurizr Lite at `http://127.0.0.1:8080/`. The two services use separate host/container ports.

### Requirements

- Docker Desktop for Windows installed and running (Docker Compose is included).
- A supported Python version for Barkly Docs.
- Ports `8000` (Barkly Docs site) and `8080` (Structurizr Lite) available locally by default; change the documentation port with `--port` (do not use `8080`, which is reserved for the graph).

To generate files without launching Docker or opening a browser:

```powershell
python __main__.py . --generate-only
```

Use `--output docs-site` to choose the output directory. If omitted, generated files go to `.barkly-docs-site` inside the project being analyzed. The `--host` and `--port` flags configure the browser URL and host port for the Docker-served documentation site. The generated `Dockerfile` uses nginx to serve the static site; the generated `architecture/docker-compose.yml` starts both nginx and Structurizr Lite. Stop both containers with `docker compose down` from the generated `architecture` directory.

The older `--serve` flag remains accepted for compatibility, but launching is now the default unless `--generate-only` is supplied.

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
PROJECT SUMMARY / STRUCTURIZR ARCHITECTURE / HTML RENDERERS
```

## Project-level architecture graph (Structurizr)

The generated HTML site includes a **Project Architecture** page backed by a Structurizr DSL workspace. The workspace intentionally contains only top-level project components and aggregated component-to-component dependencies; individual files, classes, functions, a
nd methods are not graph nodes. Detailed code entities and relationships remain available on their separate documentation pages.

The normal CLI workflow generates and builds the Docker services automatically. To start them manually after generating the site:

```powershell
cd docs-site/architecture
# Docker Desktop must be running.
docker compose up -d --build
```

Then open <http://localhost:8000> for the Barkly Docs site and <http://localhost:8080> for Structurizr Lite. The generated files are:

- `docs-site/Dockerfile` — nginx image definition for serving the static documentation.
- `docs-site/architecture/workspace.dsl` — the project-level C4 container view.
- `docs-site/architecture/docker-compose.yml` — starts the documentation website and Structurizr Lite on separate ports.

The workspace uses Barkly's dark, pink, and green visual styling. Component grouping is inferred from source paths and detected relationships, so review the result as an architecture aid rather than a definitive statement of intended design.

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