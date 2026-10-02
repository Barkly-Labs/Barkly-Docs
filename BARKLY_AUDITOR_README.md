# Barkly Docs Output Auditor

Paste these files into the **root of your Barkly Docs project**.

## Install

```powershell
python -m pip install -r requirements-barkly-audit.txt
```

## Run

```powershell
python -m tools.barkly_audit .\path\to\generated\output
```

or:

```powershell
.\run-barkly-audit.ps1 .\path\to\generated\output
```

The tool creates:

- `barkly-audit.html` — human-readable Barkly-style report
- `barkly-audit.json` — machine-readable findings

The command exits with code `1` when a FAIL exists, making it usable in CI.

## Current checks

- HTML title and primary heading
- unresolved `undefined`, `null`, or `none` values
- image alt attributes
- accessible labels on search controls
- visible Barkly evidence-state separation
- JSON/source-entity leakage regression
- Classes / Functions / Methods / Modules routing regression
- search/progressive-disclosure proxy for large generated sections

## Evidence and limits

The auditor is intentionally conservative. It reports `UNKNOWN` when the generated output does not provide enough evidence for a check.

It does **not** claim that automated checks can prove a page is Human First or aesthetically good. It checks measurable proxies such as structure, accessibility, data separation, evidence labels, search, and progressive disclosure.
