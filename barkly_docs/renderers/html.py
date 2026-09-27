from __future__ import annotations

import html
from pathlib import Path

from ..models.document import Document


def _block(block) -> str:
    if block.kind == "heading":
        level = max(1, min(block.level or 2, 6))
        anchor = "".join(ch.lower() if ch.isalnum() else "-" for ch in block.text).strip("-")
        return f'<h{level} id="{html.escape(anchor)}">{html.escape(block.text)}</h{level}>'
    if block.kind == "list":
        return f'<li>{html.escape(block.text)}</li>'
    if block.kind == "table":
        rows = []
        for row in block.rows:
            cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
            rows.append(f"<tr>{cells}</tr>")
        return "<table><tbody>" + "".join(rows) + "</tbody></table>"
    return f"<p>{html.escape(block.text)}</p>"


def render_document(document: Document, output: str | Path) -> Path:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    body = "\n".join(_block(block) for block in document.blocks)
    version = f"<span>VERSION {html.escape(document.version)}</span>" if document.version else ""
    source = html.escape(document.source or "")
    doc_type = html.escape(document.document_type.replace("-", " ").upper())
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="barkly-doc-type" content="{html.escape(document.document_type)}">
<meta name="barkly-doc-title" content="{html.escape(document.title)}">
<title>{html.escape(document.title)} / Barkly Docs</title>
<style>
body{{margin:0;background:#090909;color:#eee;font-family:Arial,sans-serif;line-height:1.7}}
main{{max-width:960px;margin:auto;padding:48px 24px 100px}}
header{{border-bottom:1px solid #333;padding-bottom:28px;margin-bottom:40px}}
.kicker{{font-size:.75rem;letter-spacing:.18em;color:#aaa}}
h1{{font-size:clamp(2rem,6vw,4.5rem);line-height:1.05;margin:.5rem 0}}
h2,h3{{margin-top:2.5rem}}
p,li{{max-width:78ch}}
pre,code{{background:#151515;padding:.15rem .35rem}}
table{{border-collapse:collapse;width:100%;margin:1.5rem 0}}td{{border:1px solid #333;padding:10px;text-align:left}}
a{{color:#fff}}
.meta{{display:flex;gap:20px;flex-wrap:wrap;color:#999;font-size:.8rem;letter-spacing:.08em}}
</style>
</head>
<body><main>
<header><div class="kicker">BARKLY / DOCS / {doc_type}</div><h1>{html.escape(document.title)}</h1><div class="meta">{version}<span>{source}</span></div></header>
{body}
</main></body></html>"""
    target = output / "index.html"
    target.write_text(page, encoding="utf-8")
    return target
