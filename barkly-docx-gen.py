#!/usr/bin/env python3
"""
BARKLY DOCX

Human-friendly DOCX → HTML documentation converter.

Reads a Word document and renders it as a Barkly Docs page.

Input:
    .docx

Output:
    index.html

Design principle:
    Preserve the structure of the document while making it
    easier to navigate, read, and understand.

This is intentionally separate from barkly_docs.py so the
document conversion system can evolve independently.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from docx import Document


# ============================================================
# HELPERS
# ============================================================

def esc(value: object) -> str:
    return html.escape(str(value or ""))


def heading_level(style_name: str) -> int:
    """
    Convert Word heading styles into numeric levels.
    """

    name = style_name.lower().strip()

    if name.startswith("heading"):
        try:
            return int(name.replace("heading", "").strip())
        except ValueError:
            pass

    return 0


def paragraph_html(paragraph) -> str:
    """
    Convert a DOCX paragraph into HTML.
    """

    text = paragraph.text.strip()

    if not text:
        return ""

    level = heading_level(
        paragraph.style.name
        if paragraph.style
        else ""
    )

    if level:
        level = max(1, min(level, 4))

        return f"""
        <h{level}>
            {esc(text)}
        </h{level}>
        """

    style = (
        paragraph.style.name.lower()
        if paragraph.style
        else ""
    )

    # --------------------------------------------------------
    # Lists
    # --------------------------------------------------------

    if "list bullet" in style:
        return f"""
        <li class="bullet-item">
            {esc(text)}
        </li>
        """

    if "list number" in style:
        return f"""
        <li class="number-item">
            {esc(text)}
        </li>
        """

    return f"""
    <p>
        {esc(text)}
    </p>
    """


def table_html(table) -> str:
    """
    Convert a DOCX table into a Barkly table.
    """

    rows = []

    for row_index, row in enumerate(table.rows):

        cells = []

        for cell in row.cells:

            text = " ".join(
                paragraph.text.strip()
                for paragraph in cell.paragraphs
                if paragraph.text.strip()
            )

            tag = "th" if row_index == 0 else "td"

            cells.append(
                f"<{tag}>{esc(text)}</{tag}>"
            )

        rows.append(
            "<tr>"
            + "".join(cells)
            + "</tr>"
        )

    return f"""
    <div class="document-table">
        <table>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>
    """


def document_title(document, fallback: str) -> str:
    """
    Try to determine a useful title from the document.
    """

    for paragraph in document.paragraphs:

        level = heading_level(
            paragraph.style.name
            if paragraph.style
            else ""
        )

        if level == 1 and paragraph.text.strip():
            return paragraph.text.strip()

    return fallback


# ============================================================
# DOCUMENT EXTRACTION
# ============================================================

def extract_document(document):
    """
    Convert the DOCX document into ordered HTML fragments.

    This intentionally keeps the original document order.
    """

    blocks = []

    for item in document.element.body.iterchildren():

        # ----------------------------------------------------
        # Paragraph
        # ----------------------------------------------------

        if item.tag.endswith("}p"):

            for paragraph in document.paragraphs:

                if paragraph._p is item:

                    rendered = paragraph_html(
                        paragraph
                    )

                    if rendered:
                        blocks.append(
                            rendered
                        )

                    break

        # ----------------------------------------------------
        # Table
        # ----------------------------------------------------

        elif item.tag.endswith("}tbl"):

            for table in document.tables:

                if table._tbl is item:

                    blocks.append(
                        table_html(table)
                    )

                    break

    return blocks


# ============================================================
# HTML DOCUMENT
# ============================================================

def build_html(
    document,
    source: Path,
) -> str:

    title = document_title(
        document,
        source.stem,
    )

    blocks = extract_document(
        document
    )

    return f"""<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8" />

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    />

    <title>
        {esc(title)} · BARKLY DOCS
    </title>

    <style>

        :root {{
            --bg: #080808;
            --panel: #101010;
            --panel-2: #151515;
            --line: #262626;
            --line-soft: #1d1d1d;
            --text: #f2f2f2;
            --muted: #9a9a9a;
            --dim: #666;
            --accent: #ff6b9d;
            --accent-soft: rgba(255, 107, 157, 0.12);
            --radius: 16px;
        }}

        * {{
            box-sizing: border-box;
        }}

        html {{
            scroll-behavior: smooth;
        }}

        body {{
            margin: 0;
            background: var(--bg);
            color: var(--text);

            font-family:
                Inter,
                ui-sans-serif,
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;

            line-height: 1.7;
        }}

        a {{
            color: inherit;
        }}

        code,
        pre,
        .eyebrow,
        .brand-meta {{
            font-family:
                "SFMono-Regular",
                Consolas,
                "Liberation Mono",
                monospace;
        }}

        /* --------------------------------------------------
           TOPBAR
        -------------------------------------------------- */

        .topbar {{
            position: sticky;
            top: 0;
            z-index: 20;

            display: flex;
            align-items: center;
            justify-content: space-between;

            min-height: 68px;
            padding: 0 28px;

            background: rgba(8, 8, 8, 0.92);
            border-bottom: 1px solid var(--line);

            backdrop-filter: blur(18px);
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;

            font-weight: 800;
            letter-spacing: -0.03em;
        }}

        .brand-mark {{
            color: var(--accent);
            font-size: 20px;
        }}

        .brand-meta {{
            display: block;
            margin-top: 1px;

            color: var(--muted);
            font-size: 9px;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }}

        .topbar-status {{
            color: var(--dim);

            font-family: monospace;
            font-size: 10px;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }}

        /* --------------------------------------------------
           PAGE
        -------------------------------------------------- */

        .page {{
            width: min(1000px, calc(100% - 36px));
            margin: 0 auto;
        }}

        .hero {{
            padding: 100px 0 70px;
        }}

        .eyebrow {{
            color: var(--accent);

            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
        }}

        .hero h1 {{
            max-width: 900px;

            margin: 14px 0 18px;

            font-size:
                clamp(48px, 8vw, 96px);

            line-height: 0.92;
            letter-spacing: -0.07em;
        }}

        .hero-description {{
            max-width: 760px;

            color: var(--muted);
            font-size: 18px;
        }}

        .meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;

            margin-top: 26px;
        }}

        .meta-pill {{
            padding: 7px 10px;

            border: 1px solid var(--line);
            border-radius: 999px;

            color: var(--muted);

            font-family: monospace;
            font-size: 10px;
        }}

        /* --------------------------------------------------
           DOCUMENT
        -------------------------------------------------- */

        .document {{
            padding: 40px;

            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
        }}

        .document > h1 {{
            margin-top: 0;
        }}

        .document h1,
        .document h2,
        .document h3,
        .document h4 {{
            scroll-margin-top: 100px;

            line-height: 1.05;
            letter-spacing: -0.04em;
        }}

        .document h1 {{
            margin-top: 54px;
            margin-bottom: 18px;

            font-size: clamp(34px, 5vw, 56px);
        }}

        .document h2 {{
            margin-top: 46px;
            margin-bottom: 14px;

            font-size: clamp(28px, 4vw, 42px);
        }}

        .document h3 {{
            margin-top: 34px;
            margin-bottom: 10px;

            color: var(--accent);

            font-size: 24px;
        }}

        .document h4 {{
            margin-top: 26px;
            margin-bottom: 8px;

            color: var(--muted);
            font-size: 18px;
        }}

        .document p {{
            max-width: 820px;

            margin: 0 0 18px;

            color: #c4c4c4;
            font-size: 15px;
        }}

        .document ul,
        .document ol {{
            max-width: 820px;

            margin: 12px 0 22px;
            padding-left: 26px;

            color: #c4c4c4;
        }}

        .document li {{
            margin: 6px 0;
        }}

        .document li::marker {{
            color: var(--accent);
        }}

        /* --------------------------------------------------
           TABLES
        -------------------------------------------------- */

        .document-table {{
            overflow-x: auto;

            margin: 26px 0;

            border: 1px solid var(--line);
            border-radius: 12px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;

            min-width: 500px;
        }}

        th,
        td {{
            padding: 12px 14px;

            border-bottom: 1px solid var(--line-soft);
            border-right: 1px solid var(--line-soft);

            text-align: left;
            vertical-align: top;
        }}

        th {{
            background: var(--panel-2);

            color: var(--text);

            font-family: monospace;
            font-size: 10px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        td {{
            color: var(--muted);
            font-size: 13px;
        }}

        tr:last-child td {{
            border-bottom: 0;
        }}

        /* --------------------------------------------------
           FOOTER
        -------------------------------------------------- */

        footer {{
            padding: 60px 0 80px;

            border-top: 1px solid var(--line);

            color: var(--dim);

            font-family: monospace;
            font-size: 10px;
        }}

        footer strong {{
            color: var(--text);
        }}

        /* --------------------------------------------------
           MOBILE
        -------------------------------------------------- */

        @media (max-width: 700px) {{

            .topbar {{
                padding: 0 16px;
            }}

            .topbar-status {{
                display: none;
            }}

            .page {{
                width: min(100% - 24px, 1000px);
            }}

            .hero {{
                padding-top: 70px;
            }}

            .document {{
                padding: 22px;
            }}

        }}

    </style>

</head>

<body>

    <header class="topbar">

        <a class="brand" href="/">

            <span class="brand-mark">
                ◆
            </span>

            <span>
                BARKLY DOCS

                <span class="brand-meta">
                    human-readable engineering reference
                </span>
            </span>

        </a>

        <span class="topbar-status">
            DOCUMENT IMPORT
        </span>

    </header>


    <main class="page">

        <section class="hero">

            <div class="eyebrow">
                BARKLY LABS · DOCUMENTATION
            </div>

            <h1>
                {esc(title)}
            </h1>

            <p class="hero-description">
                Imported from
                <code>{esc(source.name)}</code>
                and rendered through BARKLY DOCS.
            </p>

            <div class="meta">

                <span class="meta-pill">
                    DOCX
                </span>

                <span class="meta-pill">
                    STRUCTURED DOCUMENT
                </span>

                <span class="meta-pill">
                    HUMAN-READABLE
                </span>

            </div>

        </section>


        <article class="document">

            {"".join(blocks)}

        </article>


        <footer>

            <strong>BARKLY DOCS</strong>

            · Generated automatically.

            <br />

            Documentation is infrastructure.

        </footer>

    </main>

</body>

</html>
"""


# ============================================================
# CONVERSION
# ============================================================

def convert_docx(
    source: Path,
    output: Path,
) -> None:

    source = source.resolve()
    output = output.resolve()

    if not source.exists():
        raise FileNotFoundError(
            f"DOCX file not found: {source}"
        )

    if source.suffix.lower() != ".docx":
        raise ValueError(
            "Input file must be a .docx document."
        )

    document = Document(
        str(source)
    )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_text = build_html(
        document,
        source,
    )

    output_file = output / "index.html"

    output_file.write_text(
        html_text,
        encoding="utf-8",
    )

    print()
    print("BARKLY DOCS · DOCX")
    print("------------------")
    print(f"Source: {source}")
    print(f"Output: {output_file}")
    print()
    print("Document converted successfully.")


# ============================================================
# CLI
# ============================================================

def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "BARKLY DOCS — DOCX to HTML converter."
        )
    )

    parser.add_argument(
        "source",
        help="Input .docx file.",
    )

    parser.add_argument(
        "--output",
        default="docs",
        help="Output directory.",
    )

    return parser


def main():

    parser = build_parser()
    args = parser.parse_args()

    convert_docx(
        source=Path(args.source),
        output=Path(args.output),
    )


if __name__ == "__main__":
    main()