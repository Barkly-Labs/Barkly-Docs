"""Static README/documentation reader for Barkly Docs.

The reader preserves source text and extracts lightweight structure without
executing repository content. Rendering remains the responsibility of the
existing HTML layer.
"""
from __future__ import annotations

import re
from pathlib import Path

from model.project import DocumentationNode, FileNode, Project
from readers.base import LanguageReader, ReaderResult, decode_document_bytes


_README_RE = re.compile(
    r"^readme(?:[._-][^.]+)*(?:\.(?:md|markdown|mdown|mdx|rst|txt))?$",
    re.IGNORECASE,
)


class MarkdownReader(LanguageReader):
    language = "Documentation"
    extensions = (".md", ".markdown", ".mdown", ".mdx", ".rst", ".txt")
    version = "0.2.0"

    def can_read(self, path: Path) -> bool:
        # Deliberately narrow: Barkly should not classify every .md/.txt file as
        # the project README. This reader owns README variants only.
        return bool(_README_RE.match(path.name))

    def read(self, path: Path, project: Project) -> ReaderResult:
        try:
            text, source_encoding = _read_document_text(path)
        except OSError as exc:
            return ReaderResult(success=False, errors=[f"{path}: {exc}"])

        try:
            relative = path.resolve().relative_to(Path(project.root).resolve()).as_posix()
        except (OSError, ValueError):
            relative = path.as_posix()

        fmt = _format_for(path)
        headings = _headings(text, fmt)
        title = headings[0] if headings else path.name
        links = _links(text, fmt)
        structure = _document_structure(text, fmt)
        sections = _semantic_sections(text, fmt, structure)
        overview = _overview_text(text, fmt, structure)
        metadata = {
            "readme": True,
            "format": fmt,
            "relative_path": relative,
            "root_level": "/" not in relative,
            "sections": sections,
            "structure": structure,
            "overview": overview,
            "empty": not bool(text.strip()),
            "source_encoding": source_encoding,
        }

        project.add_file(
            FileNode(
                path=str(path),
                language="Documentation",
                size=len(text.encode("utf-8")),
                metadata={"documentation_format": fmt, "readme": True},
            )
        )
        project.add_documentation(
            DocumentationNode(
                title=title,
                path=str(path),
                kind=fmt,
                headings=headings,
                links=links,
                documentation=text,
                metadata=metadata,
            )
        )
        return ReaderResult(
            success=True,
            project=project,
            metadata={"documentation": 1, "format": fmt, "headings": len(headings)},
        )


def _read_document_text(path: Path) -> tuple[str, str]:
    """Read documentation without executing it and without silent replacement.

    Unicode BOMs are authoritative (UTF-8, UTF-16 LE/BE, UTF-32 LE/BE), then
    strict UTF-8 is attempted. For legacy README files that are not valid UTF-8,
    Latin-1 is a deterministic byte-preserving fallback: every input byte maps
    to one Unicode code point instead of becoming U+FFFD. The selected encoding
    is recorded in DocumentationNode metadata.
    """
    return decode_document_bytes(path.read_bytes())


def _format_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".rst":
        return "rst"
    if suffix == ".txt":
        return "text"
    # Extensionless README files conventionally contain Markdown. Treat them
    # as Markdown so format detection does not bypass structured rendering.
    if not suffix:
        return "markdown"
    if suffix == ".mdx":
        return "mdx"
    return "markdown"


def _headings(text: str, fmt: str) -> list[str]:
    lines = text.splitlines()
    found: list[str] = []
    if fmt in {"markdown", "mdx"}:
        front_matter_end = _front_matter_end(lines)
        for index, line in enumerate(lines):
            if front_matter_end is not None and index <= front_matter_end:
                continue
            atx = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
            if atx:
                found.append(atx.group(1).strip())
                continue
            if index + 1 < len(lines) and line.strip() and re.match(r"^\s*(?:=+|-+)\s*$", lines[index + 1]):
                found.append(line.strip())
    elif fmt == "rst":
        for index, line in enumerate(lines[:-1]):
            if line.strip() and re.match(r"^\s*([=\-~^\"`:+*#])\1{2,}\s*$", lines[index + 1]):
                found.append(line.strip())
    return _dedupe(found)


def _links(text: str, fmt: str) -> list[str]:
    found: list[str] = []
    if fmt in {"markdown", "mdx"}:
        found.extend(m.group(1).strip() for m in re.finditer(r"!?\[[^\]]*\]\(([^)\s]+)", text))
        definitions = {
            m.group(1).casefold(): m.group(2).strip()
            for m in re.finditer(r"^\s*\[([^\]]+)\]:\s*(\S+)", text, re.MULTILINE)
        }
        found.extend(definitions.values())
    elif fmt == "rst":
        found.extend(m.group(1) for m in re.finditer(r"<([^>]+)>`_", text))
    return _dedupe(found)


def _document_structure(text: str, fmt: str) -> list[dict[str, object]]:
    """Preserve headed document structure without assigning semantic meaning.

    Every recognized heading is retained even when Barkly does not understand its
    subject.  This keeps parsing independent from project/framework conventions.
    """
    headings = _headings_with_levels(text, fmt)
    if not headings:
        return []
    lines = text.splitlines()
    result: list[dict[str, object]] = []
    for pos, (line_no, level, title, consumed) in enumerate(headings):
        end = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines)
        body = "\n".join(lines[line_no + consumed:end]).strip()
        result.append({
            "title": title,
            "level": level,
            "line_start": line_no + 1,
            "body": body,
        })
    return result


def _semantic_sections(
    text: str, fmt: str, structure: list[dict[str, object]] | None = None
) -> dict[str, str]:
    """Extract optional semantic fields while preserving unfamiliar sections.

    Matching is deliberately synonym-based and order-independent.  A heading that
    cannot be classified simply remains in ``structure`` and in the original
    documentation instead of being discarded or guessed into a category.
    """
    structure = structure if structure is not None else _document_structure(text, fmt)
    aliases = {
        "installation": {"installation", "install", "setup", "getting started", "quick start", "quickstart", "bootstrap"},
        "usage": {"usage", "examples", "example", "how to use", "using", "tutorial"},
        "configuration": {"configuration", "config", "settings", "options"},
        "requirements": {"requirements", "dependencies", "prerequisites", "prerequisites and dependencies"},
        "architecture": {"architecture", "design", "internals", "how it works", "project structure"},
        "features": {"features", "capabilities", "highlights", "what it does"},
        "testing": {"testing", "tests", "test", "verification"},
        "development": {"development", "developer guide", "developing", "local development"},
        "contributing": {"contributing", "contribution", "contributions", "how to contribute"},
        "license": {"license", "licence", "licensing"},
        "support": {"support", "contact", "help", "getting help"},
    }
    lookup = {alias: key for key, values in aliases.items() for alias in values}
    result: dict[str, str] = {}
    for section in structure:
        normalized = _normalize_heading(str(section.get("title", "")))
        key = lookup.get(normalized)
        body = str(section.get("body", "")).strip()
        if key and body and key not in result:
            result[key] = body
    return result


def _overview_text(
    text: str, fmt: str, structure: list[dict[str, object]] | None = None
) -> str:
    """Return concise introductory prose without consuming later README structure."""
    lines = text.splitlines()
    front_matter_end = _front_matter_end(lines) if fmt in {"markdown", "mdx"} else None
    heading_data = _headings_with_levels(text, fmt)
    heading_lines = {line_no for line_no, *_ in heading_data}
    underline_lines = {line_no + 1 for line_no, _level, _title, consumed in heading_data if consumed == 2}

    paragraph: list[str] = []
    in_fence = False
    started = False
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if front_matter_end is not None and index <= front_matter_end:
            continue
        if fmt in {"markdown", "mdx"} and re.match(r"^\s*(?:```|~~~)", raw):
            if started:
                break
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        # Once introductory prose starts, any document structure ends the card
        # summary. Before it starts, headings/media may be skipped while looking
        # for the first real prose paragraph.
        if index in heading_lines or index in underline_lines:
            if started:
                break
            continue
        if _is_readme_structural_boundary(stripped, fmt):
            if started:
                break
            continue
        if not stripped:
            if started:
                break
            continue
        if _is_non_prose_readme_line(stripped, fmt):
            if started:
                break
            continue

        plain = _plain_readme_prose(stripped, fmt)
        if not plain:
            if started:
                break
            continue
        paragraph.append(plain)
        started = True
        if len(" ".join(paragraph)) >= 360:
            break

    overview = " ".join(paragraph).strip()
    if len(overview) > 360:
        clipped = overview[:361].rsplit(" ", 1)[0].rstrip(" ,;:-")
        overview = clipped + "…"
    return overview


def _is_readme_structural_boundary(line: str, fmt: str) -> bool:
    if not line:
        return False
    if fmt in {"markdown", "mdx"}:
        if re.match(r"^\s*([-*_])(?:\s*\1){2,}\s*$", line):
            return True
        if re.match(r"^\s*#{1,6}\s+", line):
            return True
        if re.match(r"^\s*(?:```|~~~)", line):
            return True
        if re.match(r"^\s*\|?.+\|.+\|?\s*$", line):
            return True
    return False

def _is_non_prose_readme_line(line: str, fmt: str) -> bool:
    if line.startswith((">", "- ", "* ", "+ ", "|")) or re.match(r"^\d+[.)]\s+", line):
        return True
    if re.match(r"^!\[", line) or re.match(r"^\[?!\[", line):
        return True
    if fmt == "mdx" and (line.startswith(("import ", "export ")) or re.match(r"^</?[A-Z][A-Za-z0-9_.:-]*(?:\s|/?>)", line)):
        return True
    if re.match(r"^</?[A-Za-z][^>]*>$", line):
        return True
    if re.match(r"^\[[^]]+\]:\s*\S+", line):
        return True
    return False


def _plain_readme_prose(line: str, fmt: str) -> str:
    if fmt in {"markdown", "mdx"}:
        line = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\[([^]]+)\]\[[^]]+\]", r"\1", line)
        line = re.sub(r"[`*_~]", "", line)
    return re.sub(r"\s+", " ", line).strip()


def _normalize_heading(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def _headings_with_levels(text: str, fmt: str) -> list[tuple[int, int, str, int]]:
    lines = text.splitlines()
    result: list[tuple[int, int, str, int]] = []
    if fmt in {"markdown", "mdx"}:
        front_matter_end = _front_matter_end(lines)
        for index, line in enumerate(lines):
            if front_matter_end is not None and index <= front_matter_end:
                continue
            match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if match:
                result.append((index, len(match.group(1)), match.group(2).strip(), 1))
            elif index + 1 < len(lines) and line.strip():
                underline = re.match(r"^\s*(=+|-+)\s*$", lines[index + 1])
                if underline:
                    result.append((index, 1 if underline.group(1).startswith("=") else 2, line.strip(), 2))
    elif fmt == "rst":
        levels: dict[str, int] = {}
        for index, line in enumerate(lines[:-1]):
            underline = re.match(r"^\s*([=\-~^\"`:+*#])\1{2,}\s*$", lines[index + 1])
            if line.strip() and underline:
                char = underline.group(1)
                if char not in levels:
                    levels[char] = len(levels) + 1
                result.append((index, levels[char], line.strip(), 2))
    return result

def _headings_with_lines(text: str, fmt: str) -> list[tuple[int, str]]:
    return [(line_no, title) for line_no, _level, title, _consumed in _headings_with_levels(text, fmt)]



def _front_matter_end(lines: list[str]) -> int | None:
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            return index
    return None

def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
