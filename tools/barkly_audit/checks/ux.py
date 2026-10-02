from ..models import Finding, AuditState


def check_human_first_proxies(page):
    findings = []
    for section in page.soup.select("details.index-section-card, details.searchable-section"):
        heading = section.find(["h2", "h3"])
        name = heading.get_text(" ", strip=True) if heading else "Unnamed section"
        items = section.select(".entity-list > .entity-item")
        search = section.select_one('input[type="search"]')

        if len(items) > 12 and not search:
            findings.append(Finding(
                "BARKLY-UX-001",
                AuditState.WARN,
                f'"{name}" contains {len(items)} items but no search control.',
                page.relative_path,
            ))

    if not findings:
        findings.append(Finding(
            "BARKLY-UX-001",
            AuditState.PASS,
            "Large detected data sections provide progressive disclosure/search where measurable.",
            page.relative_path,
        ))
    return findings
