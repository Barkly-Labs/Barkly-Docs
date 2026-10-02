from ..models import Finding, AuditState

FORBIDDEN_IN_JSON = {"CLASSNODE", "FUNCTIONNODE", "METHODNODE", "MODULENODE"}


def _section_for_heading(page, title):
    for heading in page.soup.find_all(["h1", "h2", "h3"]):
        if heading.get_text(" ", strip=True).casefold() == title.casefold():
            node = heading
            while node and getattr(node, "name", None) not in {"details", "section", "article"}:
                node = node.parent
            return node or heading.parent
    return None


def check_data_routing(page):
    findings = []
    json_section = _section_for_heading(page, "JSON")
    if json_section:
        text = " ".join(json_section.stripped_strings).upper()
        leaked = sorted(kind for kind in FORBIDDEN_IN_JSON if kind in text)
        findings.append(Finding(
            "BARKLY-ROUTING-JSON-001",
            AuditState.FAIL if leaked else AuditState.PASS,
            f"JSON contains source entity types: {', '.join(leaked)}" if leaked
            else "JSON section does not contain class/function/method/module entity tags.",
            page.relative_path,
            evidence=", ".join(leaked) if leaked else None,
        ))

    expected = {
        "Classes": "CLASSNODE",
        "Functions": "FUNCTIONNODE",
        "Methods": "METHODNODE",
        "Modules": "MODULENODE",
    }
    all_kinds = set(expected.values())
    for title, allowed in expected.items():
        section = _section_for_heading(page, title)
        if not section:
            continue
        text = " ".join(section.stripped_strings).upper()
        wrong = sorted(kind for kind in all_kinds - {allowed} if kind in text)
        findings.append(Finding(
            f"BARKLY-ROUTING-{title.upper()}-001",
            AuditState.FAIL if wrong else AuditState.PASS,
            f"{title} contains entity types from another section: {', '.join(wrong)}" if wrong
            else f"{title} does not contain other source entity types.",
            page.relative_path,
            evidence=", ".join(wrong) if wrong else None,
        ))
    return findings
