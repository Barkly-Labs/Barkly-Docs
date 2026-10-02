from ..models import Finding, AuditState


def check_document_structure(page):
    findings = []
    title = page.soup.find("title")
    h1 = page.soup.find("h1")

    findings.append(Finding(
        "BARKLY-STRUCTURE-001",
        AuditState.PASS if title and title.get_text(strip=True) else AuditState.FAIL,
        "Page has a document title." if title and title.get_text(strip=True) else "Page is missing a document title.",
        page.relative_path,
    ))
    findings.append(Finding(
        "BARKLY-STRUCTURE-002",
        AuditState.PASS if h1 else AuditState.WARN,
        "Page has a primary heading." if h1 else "Page has no H1 primary heading.",
        page.relative_path,
    ))
    return findings


def check_undefined_values(page):
    bad = []
    for text in page.soup.stripped_strings:
        value = text.strip().lower()
        if value in {"undefined", "null", "none"}:
            bad.append(text.strip())

    return [Finding(
        "BARKLY-CONTENT-001",
        AuditState.FAIL if bad else AuditState.PASS,
        f"Found unresolved values: {', '.join(sorted(set(bad)))}" if bad
        else "No unresolved undefined/null values were rendered.",
        page.relative_path,
        evidence=", ".join(sorted(set(bad))) if bad else None,
    )]
