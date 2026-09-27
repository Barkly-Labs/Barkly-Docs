from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from ..models.document import Document, DocumentBlock

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(W + "t")).strip()


def _style(paragraph: ET.Element) -> str:
    ppr = paragraph.find(W + "pPr")
    if ppr is None:
        return ""
    pstyle = ppr.find(W + "pStyle")
    return pstyle.attrib.get(W + "val", "") if pstyle is not None else ""


def _heading_level(style: str) -> int | None:
    match = re.search(r"heading\s*([1-9])", style, re.I)
    return int(match.group(1)) if match else None


def parse_docx(path: str | Path, document_type: str = "functional-requirements") -> Document:
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    blocks: list[DocumentBlock] = []
    tables = root.findall(".//" + W + "tbl")
    table_ids = {id(table) for table in tables}

    for child in root.find(W + "body") or []:
        if child.tag == W + "p":
            value = _text(child)
            if not value:
                continue
            style = _style(child)
            level = _heading_level(style)
            if level:
                blocks.append(DocumentBlock(kind="heading", text=value, level=level))
            else:
                num = child.find(W + "pPr/" + W + "numPr")
                kind = "list" if num is not None else "paragraph"
                blocks.append(DocumentBlock(kind=kind, text=value))
        elif child.tag == W + "tbl" and id(child) in table_ids:
            rows: list[list[str]] = []
            for row in child.findall(W + "tr"):
                rows.append([_text(cell) for cell in row.findall(W + "tc")])
            blocks.append(DocumentBlock(kind="table", rows=rows))

    title = path.stem
    version = None
    for block in blocks[:12]:
        if "functional requirements" in block.text.lower() and "—" in block.text:
            title = block.text.split("—", 1)[0].strip()
        match = re.search(r"\bv(?:ersion\s*)?(\d+(?:\.\d+)*)\b", block.text, re.I)
        if match:
            version = match.group(1)
            break

    return Document(
        title=title,
        document_type=document_type,
        version=version,
        source=str(path),
        blocks=blocks,
        metadata={"format": "docx"},
    )
