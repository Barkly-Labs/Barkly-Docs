# Barkly Docs

### Understand the codebase before you have to understand all the code.

**Barkly Docs is a source-code documentation and exploration tool designed to make unfamiliar software projects easier for humans to understand.**

It analyzes a project's structure, identifies code elements and their relationships, and turns that information into browsable documentation. Instead of forcing developers to navigate thousands of files before they understand a project, Barkly Docs aims to bring the important information to the surface first.

Built by **Barkly Labs**, a Detroit-rooted, human-centered technology initiative.

> **Our guiding question:** Can we make computers front-load the hard stuff for humans?

---

## Table of contents

* [Why Barkly Docs?](#why-barkly-docs)
* [What it does](#what-it-does)
* [Design principles](#design-principles)
* [How it works](#how-it-works)
* [Language support](#language-support)
* [Generated documentation](#generated-documentation)
* [Getting started](#getting-started)
* [Development and testing](#development-and-testing)
* [Current limitations](#current-limitations)
* [Roadmap](#roadmap)
* [Who is it for?](#who-is-it-for)
* [Project philosophy](#project-philosophy)
* [Contributing](#contributing)
* [About Barkly Labs](#about-barkly-labs)

---

## Why Barkly Docs?

Understanding an unfamiliar codebase can be one of the most expensive parts of software development.

A developer joining an existing project may need to figure out:

* Where the important functionality lives.
* Which classes, functions, and methods are available.
* How different parts of the application connect.
* Which files are responsible for particular behaviors.
* Where to begin when the project has hundreds or thousands of files.
* What changed since the last time they examined the code.

Traditional documentation can help, but it may be incomplete, outdated, or written for someone who already understands the project.

Barkly Docs approaches this problem from a different direction: **let the software's structure help explain the software.**

By extracting information directly from source code, Barkly Docs aims to give developers an initial map of a project before they need to explore every file themselves.

## What it does

Barkly Docs is being developed around a few core capabilities.

### 1. Source-code analysis

Read source files and extract structural information, including:

* Modules and files.
* Classes.
* Functions and methods.
* Imports and dependencies.
* Documentation metadata.
* Relationships between discovered code elements.

The goal is to make a codebase's shape visible without requiring a developer to manually inspect every file.

### 2. Relationship discovery

Code elements rarely exist in isolation. Functions belong to modules, classes contain methods, and source files depend on other parts of the project.

Barkly Docs models discovered relationships so that documentation can explain not only what exists, but also how parts of a project connect.

Relationship information is based on what the analyzer can establish from the source. It should not automatically be interpreted as proof of runtime behavior.

### 3. Browser-based documentation

Barkly Docs is designed to turn analysis results into an HTML documentation site.

The intended experience is to move from a high-level project overview to individual files, classes, functions, methods, and their associated relationships.

### 4. Project orientation

The first thing a developer needs is not necessarily every available symbol. It is a useful answer to the question:

**“What am I looking at, and where should I start?”**

Barkly Docs aims to surface project-level information before presenting deeper technical detail.

### 5. Static analysis without executing the target project

Barkly Docs' Python analysis approach uses AST-based inspection rather than importing and executing the target Python code.

This helps avoid running arbitrary project code just to discover its structure. It does not, by itself, guarantee that every input file is safe to process or that every language reader has identical safety properties.

---

## Design principles

Barkly Docs is guided by the human-first engineering philosophy of Barkly Labs.

| Principle                   | What it means                                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Understand before exploring | Show the overall shape of a project before overwhelming people with details.                               |
| Structure before volume     | Organize findings into useful documentation rather than dumping raw scan output.                           |
| Evidence over assumptions   | Distinguish what the source establishes from what an analyzer infers or cannot determine.                  |
| Human-readable by default   | Present information in a format people can navigate and understand.                                        |
| Useful across projects      | Build toward support for different languages and repository structures.                                    |
| Transparent limitations     | Make missing information and unsupported features visible rather than silently inventing answers.          |
| Local-first workflow        | Aim to make project analysis useful without requiring source code to be uploaded to a third-party service. |

These principles describe the project's direction. Individual features should be evaluated against what is actually implemented in the current release.

---

## How it works

Barkly Docs is organized around a pipeline that separates source reading, analysis, and presentation.

```text
        Source repository
                |
                v
        File discovery
                |
                v
        Language readers
                |
                v
      Structured project model
                |
                v
      Code and relationship analysis
                |
                v
       Documentation rendering
                |
                v
       Browsable HTML output
```

### 1. File discovery

The scanner identifies files in the target repository and determines which files it can process.

Unsupported files, excluded files, and files that cannot be parsed may be skipped or reported, depending on the reader and configuration.

### 2. Language readers

Language-specific readers extract structural information from source files.

Keeping readers separate makes it possible to add support for additional languages without redesigning the entire documentation pipeline.

### 3. Project model

Extracted information is represented in a shared model. The model provides a common foundation for representing modules, classes, functions, methods, imports, and relationships across different languages.

### 4. Analysis

The analysis layer works with the structured model to identify relationships and organize the information needed for documentation.

The distinction between directly observed information and inferred relationships is an important area of development.

### 5. Rendering

The rendering layer transforms the analyzed project into HTML documentation.

Separating rendering from source analysis makes it possible to improve the documentation experience without rewriting every language reader.

---

## Language support

Barkly Docs is being developed with a multi-language architecture.

The project has reader implementations for Python, JavaScript, Ruby, Java, and Rust. The completeness and reliability of individual readers may differ, so the presence of a reader does not mean that every language feature is fully supported.

| Language   | Reader status                                                        |
| ---------- | -------------------------------------------------------------------- |
| Python     | Reader implemented                                                   |
| JavaScript | Reader implemented                                                   |
| Ruby       | Reader implemented; continuing integration and end-to-end validation |
| Java       | Reader implemented                                                   |
| Rust       | Reader implemented                                                   |
| TypeScript | Support remains to be verified against the current implementation    |
| C++        | Planned or incomplete                                                |
| Astro      | Planned or incomplete                                                |
| CSS        | Planned or incomplete                                                |
| HTML       | Planned or incomplete                                                |
| Markdown   | Planned or incomplete                                                |

This table describes known development status, not a guarantee of complete syntax coverage. Consult the current source and tests before relying on a reader for a particular language feature.

The long-term objective is to make the documentation pipeline useful across mixed-language repositories, including projects that combine application code, configuration, templates, and supporting files.

---

## Generated documentation

Barkly Docs is intended to generate a browsable HTML site containing project structure and discovered code information.

The documentation experience is being developed around:

* A project overview.
* An inventory of discovered files and modules.
* Class, function, and method information.
* Import and relationship information.
* Entity exploration.
* Navigation between related code elements.
* Useful summaries that help developers orient themselves.

The exact pages and fields available depend on the current renderer and analysis implementation.

Generated documentation should be treated as an aid to understanding source code, not a substitute for reading the code, running appropriate tests, or consulting authoritative project documentation.

---

## Getting started

### Requirements

* Python 3.14 is the development environment currently being used.
* A local checkout of Barkly Docs.
* A source-code repository to analyze.

Additional dependencies or version requirements may apply as the project evolves. Check the repository's dependency and configuration files for the authoritative setup instructions.

### Get the source

Clone the repository or download a copy of the source code, then open a terminal in the project root.

```powershell
cd "C:\Users\<your-username>\Documents\Barkly Docs"
```

Replace the example path with the actual location of your checkout.

### Inspect the available commands

The project currently has a Python entry point at `__main__.py`.

From the repository root, inspect the entry point and its argument handling before selecting a target project or output directory. Do not assume that a packaged command such as `python -m barkly_docs` is available unless the project has been packaged to support it.

Once the supported CLI arguments and dependency setup are established, they should be documented here as a verified, copy-and-pasteable command.

### Output

Generated documentation is intended to be written to a local output directory. For example, a development run against a Rails checkout has used:

```text
rails/
└── .barkly-docs-site/
```

The actual output location depends on the CLI configuration.

---

## Development and testing

Barkly Docs is an actively developed project. Tests are important because a reader can appear to work in isolation while the complete pipeline still fails during analysis or rendering.

### Run the tests

From the repository root, use the project's configured test runner.

For a pytest-based checkout, the following commands can be used once the test import configuration is working:

```powershell
python -m pytest .\tests\test_entity_explorer.py -q
```

Run the relevant language-reader tests as well as the focused renderer tests.

For a broader check:

```powershell
python -m pytest
```

The complete suite may expose unrelated existing failures. Record those separately from regressions introduced by a change.

### Validate the renderer

The entity explorer must handle projects with large numbers of code elements and relationships.

Important regression checks include:

* Building the relationship index once per render.
* Looking up relationships without rescanning the entire relationship collection for every entity.
* Preserving stable relationship ordering.
* Displaying a bounded number of related items without losing the accurate total count.
* Rendering entities with no relationships.
* Preserving links, escaping, and existing HTML behavior.

### Test real repositories

Small synthetic fixtures are useful for precise regression tests, but real projects are also necessary to validate end-to-end behavior.

Useful test targets include:

* A small project with known expected output.
* A Ruby project with representative classes and methods.
* A large repository with many files and relationships.
* A mixed-language repository, once the relevant readers are supported.

Record processing counts, skipped files, warnings, errors, rendering completion, and test results. A successful source scan does not necessarily mean that documentation generation completed successfully.

---

## Current limitations

Barkly Docs is under active development. Its current implementation should not be confused with the complete long-term vision.

Known areas requiring continued verification include:

* **Reader completeness:** Language readers may not cover every syntax construct, framework convention, or metaprogramming pattern.
* **Runtime behavior:** Static analysis cannot reliably determine every dynamic relationship or runtime execution path.
* **Relationship accuracy:** A discovered relationship must be interpreted according to the evidence available to the analyzer.
* **Large-project performance:** Rendering and relationship exploration need to remain efficient as repository size grows.
* **Error handling:** Malformed files and unsupported constructs should produce useful warnings rather than obscure failures.
* **End-to-end reliability:** Successful parsing and model construction must be followed by successful rendering.
* **Test and packaging configuration:** Test imports, entry points, and setup instructions must work consistently for contributors.

These are areas for ongoing engineering, not reasons to treat the project as unusable. The goal is to make the tool's capabilities and limitations understandable.

---

## Roadmap

The following is a development direction, not a promise that every item is already implemented or scheduled.

### Foundation

* [x] Establish a shared project model.
* [x] Develop a multi-language reader architecture.
* [x] Implement initial readers for multiple programming languages.
* [ ] Stabilize test discovery and project setup.
* [ ] Establish reliable end-to-end tests.

### Documentation experience

* [x] Develop the HTML rendering pipeline.
* [ ] Complete the end-to-end entity explorer.
* [ ] Improve project-level orientation and summaries.
* [ ] Make relationships easy to navigate.
* [ ] Improve explanations when documentation is missing or incomplete.

### Analysis quality

* [ ] Clearly distinguish declared, detected, inferred, and unknown information.
* [ ] Improve relationship accuracy and traceability.
* [ ] Expand reader coverage and language-specific regression tests.
* [ ] Report unsupported syntax and analysis limitations clearly.

### Scale and reliability

* [ ] Validate rendering against large real-world repositories.
* [ ] Reduce unnecessary repeated relationship scans.
* [ ] Improve error reporting and recovery.
* [ ] Establish repeatable performance benchmarks.
* [ ] Document verified installation, CLI, and release procedures.

### Community

* [ ] Publish contributor documentation.
* [ ] Establish a clear process for reporting bugs and requesting features.
* [ ] Document how to add and test a language reader.
* [ ] Build toward reproducible releases and a sustainable open-source workflow.

---

## Who is it for?

Barkly Docs is being built for people who need to understand software without spending unnecessary time reconstructing its structure by hand.

Potential users include:

* Developers joining an unfamiliar project.
* Maintainers working with legacy code.
* Students learning how real repositories are organized.
* Open-source contributors exploring a project before making a change.
* Small teams that need a useful starting point for internal documentation.
* Developers maintaining projects that span multiple languages.

It is especially relevant when the first challenge is not writing code, but figuring out where to begin.

---

## Contributing

Contributions are welcome as the project and its contribution process mature.

Useful areas of contribution include:

* Fixing reader bugs.
* Adding syntax coverage.
* Improving relationship analysis.
* Improving generated HTML and navigation.
* Adding regression tests.
* Testing against real-world repositories.
* Improving accessibility and usability.
* Writing examples and documentation.

Before submitting a change:

1. Check the existing implementation and tests.
2. Keep changes focused on a clearly defined behavior.
3. Add regression coverage where practical.
4. Run the relevant tests.
5. Document limitations or unsupported cases introduced by the change.

For new language readers, prefer the existing reader architecture and shared project model rather than introducing a separate, incompatible representation of source code.

If the repository does not yet contain a contribution guide or issue templates, those can be added as the project establishes its public contribution workflow.

---

## Project philosophy

Barkly Docs is part of a broader effort to make technology work better for the people using and maintaining it.

Documentation is not just a record of what a developer already knows. It can be a tool that reduces the effort required to learn, maintain, and contribute to software.

A project should not require someone to understand thousands of lines of code before it can begin explaining itself.

**Show the shape first. Make the details navigable. Be honest about what is known.**

That is the direction Barkly Docs is working toward.

---

## About Barkly Labs

Barkly Docs is developed as part of **Barkly Labs**, a Detroit-rooted, human-centered technology initiative focused on building software, hardware, interfaces, and documentation that make technology more understandable and accessible.

Barkly Labs is guided by one question:

> Can we make computers front-load the hard stuff for humans?

The goal is not merely to make computers more capable. It is to make the effort required to use and understand them less burdensome for people.

Barkly Docs applies that philosophy to software development itself.

**Project:** Barkly Docs
**Organization:** Barkly Labs
**Website:** https://barklylabs.space
**Focus:** Source-code understanding, generated documentation, and human-centered developer tools
**Status:** Active development

---

*Barkly Docs is a developing project. Verify current feature coverage, supported syntax, and CLI behavior against the source code and tests before relying on a particular capability.*
