# AGENTS.md — Barkly Docs

## 1. Project purpose

Barkly Docs is a human-centered, static code-documentation generator developed as part of Barkly Labs.

Its guiding question is:

> Can we make computers front-load the hard stuff for humans?

Barkly Docs aims to help people understand unfamiliar codebases by identifying project structure, code entities, dependencies, and relationships, then presenting evidence-based results in useful generated documentation.

Prioritize correctness, clarity, accessibility, maintainability, and user control over flashy output or unsupported claims.

## 2. Instructions for coding agents

Before making changes:

1. Read this file and any more-specific `AGENTS.md` files that apply to the files being edited.
2. Inspect the relevant implementation, tests, and generated output.
3. Check the current Git status and preserve all existing user changes.
4. Identify the root cause before changing code.
5. State the intended scope briefly when the task is substantial.

Do not assume that a feature works because a class, function, HTML element, or event handler exists. Trace the behavior through the relevant pipeline and verify the actual result.

When instructions conflict, follow the more specific applicable project instructions unless they conflict with a higher-priority instruction or the user's explicit request.

## 3. Work in small, bounded stages

Large tasks should be divided into manageable stages:

1. **Inspect:** Find the relevant code path and reproduce or confirm the issue.
2. **Plan:** Identify the smallest appropriate fix and the tests needed.
3. **Implement:** Make focused changes without unrelated refactoring.
4. **Verify:** Run focused tests, then the relevant broader suite.
5. **Report:** Summarize changes, evidence, test results, and remaining limitations.

For a large task, do not silently expand the scope. Finish a useful, verifiable slice before moving to unrelated work.

Do not repeatedly re-audit the entire repository when the task is confined to one component, unless evidence shows that a broader investigation is necessary.

## 4. Preserve user work and repository state

- Never run destructive Git commands such as `git reset --hard`, `git clean -fd`, or force-checkout commands unless the user explicitly requests the operation and its consequences are clear.
- Do not discard, overwrite, or revert unrelated user changes.
- Inspect `git status` before potentially disruptive edits.
- Do not restore files from an old ZIP, backup, or commit merely because it is easier than fixing the current implementation.
- Do not create a commit unless the user requests one or the active workflow explicitly authorizes it.
- Keep changes focused and explain any unavoidable broader changes.

## 5. Architecture and data flow

Barkly Docs processes source repositories and generates documentation. Depending on the feature, the pipeline may include:

`Source files and manifests → language reader → shared project model → analysis and resolution → relationship graph → HTML rendering → browser interactions`

When investigating a bug, trace the relevant data through every applicable stage.

For example, extracting an import in a reader does not prove that the dependency is correctly represented in the shared model, resolved to the correct target, included in the graph, or displayed in generated HTML.

Fix the stage where the information is actually lost. Prefer a shared fix when multiple languages genuinely share the same underlying bug, and a reader-specific fix when behavior is language-specific.

Avoid unnecessary changes to unrelated readers, the shared model, or rendering code.

## 6. Static analysis and source safety

- Treat scanned repositories as untrusted input.
- Do not execute, import, evaluate, or run the target project's source code merely to document it.
- Prefer deterministic parsing and static analysis.
- Do not fabricate dependencies, calls, inheritance links, endpoints, or other relationships.
- Preserve evidence and provenance where supported by the model.
- Distinguish detected facts from inferred relationships and unknown information.
- Handle dynamic language features conservatively. If a relationship cannot be established reliably, report the limitation rather than inventing a target.
- Escape source-derived content appropriately before placing it in HTML.
- Avoid unsafe HTML or JavaScript construction from scanned source text.

## 7. Language readers and dependency detection

Barkly Docs aims to document projects written in multiple languages, including Python, JavaScript/TypeScript where supported, Java, Ruby, Rust, and C++ where supported.

Do not claim a language or feature is supported solely because a reader file exists. Confirm that the reader is registered, invoked, and integrated with the relevant analysis and rendering paths.

When fixing dependency detection, distinguish where applicable:

- External packages and dependencies declared in manifests or lockfiles
- Imports and requires found in source code
- Standard-library modules
- Internal modules or project files
- Version constraints, locked versions, dependency kinds, and source evidence
- Unresolved or dynamic imports

Do not collapse distinct dependency types into one generic category. Avoid duplicate or dangling graph edges. Do not treat a manifest declaration and a source import as identical evidence.

Use small deterministic fixtures to test expected behavior, negative cases, and the generated output.

## 8. Generated HTML and UI behavior

Generated documentation is a product interface, not merely a collection of HTML files.

Unless the user explicitly requests a redesign:

- Preserve the existing Barkly Docs visual identity, page structure, section order, colors, typography, spacing, and card design.
- Fix the source renderer or template when the HTML is generated; do not rely on manual edits to output that will be overwritten.
- Preserve existing content, links, and working behavior.
- Avoid adding a new framework or runtime dependency for simple interactions.

For search, filters, cards, lists, and expand/collapse controls:

- Make controls perform their advertised action.
- Scope each interaction to the correct card or section.
- Ensure searching uses the real generated records, not placeholder results.
- Clearing a query should restore the appropriate results and preserve unrelated filters.
- Search should be able to find records beyond a compact list's initial visible limit.
- Long lists may be compact by default, but the remaining data must remain accessible.
- Expand/collapse controls must operate independently and reflect their state accurately.
- Avoid duplicate IDs, duplicate event listeners, broad selectors that affect unrelated sections, and nested controls that interfere with each other.
- Use semantic HTML, keyboard-accessible controls, visible focus indicators, and appropriate ARIA state.
- Provide useful empty states when a search returns no matches.
- Handle empty data and missing optional fields gracefully.

Do not add decorative controls that do nothing. Do not make informational cards clickable unless there is a meaningful action.

## 9. Human-centered documentation

Generated documentation should help people understand a project even when its README or comments are incomplete, while remaining honest about what static analysis can establish.

- Show useful project structure and entry points when detectable.
- Make entities and relationships searchable and navigable where those views are implemented.
- Use clear labels and explanations.
- Preserve source locations and links where possible.
- Distinguish evidence from inference.
- Disclose unsupported syntax, unresolved dependencies, and known limitations.
- Never claim comprehensive understanding when the tool only detects a subset of the code.

A useful result is accurate, understandable, and navigable—not simply large or visually impressive.

## 10. Testing standards

Tests must verify behavior, not merely implementation details.

Prefer small deterministic unit tests for parsing, model construction, analysis, graph construction, rendering, and UI behavior. Keep tests fast enough for routine development.

Separate slow integration tests or large-repository scans from the fast suite when appropriate, but **do not delete, weaken, or silently skip meaningful tests just to make the suite pass faster**.

When categorizing tests as slow:

- Keep them discoverable and runnable through an explicit command.
- Explain why they are slow.
- Preserve their assertions.
- Run relevant integration tests explicitly when practical.

For a change, run the most relevant focused tests first, then the fast suite. Run relevant slower integration tests when the change affects those paths.

When possible, test generated HTML and browser interactions using the project's existing automation tools. If interactive behavior cannot be tested in a browser, say so clearly and use the strongest available alternative.

Do not report tests as passing unless they actually completed successfully. Distinguish passed, failed, skipped, deselected, and not-run tests.

## 11. Definition of done

A task is complete only when:

- The requested behavior is implemented in the appropriate source files.
- The implementation fits the existing architecture.
- Relevant regression tests cover the bug or feature.
- Focused tests have been run.
- Relevant broader tests have been run, or the reason they were not run is stated.
- Generated output has been inspected when applicable.
- No unrelated user changes have been discarded.
- Remaining limitations and unverified behavior are documented.

A test passing is evidence for the behavior it exercises, not proof that every language, repository, or edge case works.

## 12. Reporting requirements

At the end of each task, provide a concise report with:

1. **Summary:** What changed and why.
2. **Files changed:** The relevant paths.
3. **Verification:** Exact test commands and results, including counts and runtime when available.
4. **Generated-output checks:** What was inspected or tested in the actual output.
5. **Limitations:** What remains unsupported, unverified, or failing.
6. **Next step:** Only the most useful next step, if one is needed.

Clearly distinguish:
- Implemented
- Tested and passed
- Tested and failed
- Not tested or unverified

Do not claim that a fix is complete based only on code inspection or the presence of an implementation.

## 13. Scope and communication

- Follow the user's stated goal; do not substitute a redesign or broad refactor.
- Ask a concise clarifying question only when a missing detail materially blocks safe implementation.
- Otherwise, inspect the project and make a reasonable, reversible choice.
- Prefer precise, plain-language explanations.
- Do not overwhelm the user with repeated progress narration or huge lists of speculative future improvements.
- For substantial work, report meaningful checkpoints and finish with concrete evidence.
- Be candid about uncertainty and errors.

## 14. Project principle

Barkly Docs should embody the principle behind Barkly Labs:

> Front-load the hard work for humans, without hiding uncertainty or taking control away from them.

Make the software do the tedious work, make the results understandable, and make the limits visible.
