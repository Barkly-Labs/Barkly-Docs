from ..models import Finding, AuditState


def check_accessibility(page):
    findings = []

    images = page.soup.find_all("img")
    missing_alt = [img.get("src", "<unknown>") for img in images if img.get("alt") is None]
    findings.append(Finding(
        "BARKLY-A11Y-001",
        AuditState.FAIL if missing_alt else AuditState.PASS,
        f"{len(missing_alt)} image(s) are missing alt attributes." if missing_alt
        else "Images provide alt attributes.",
        page.relative_path,
        evidence=", ".join(missing_alt[:10]) if missing_alt else None,
    ))

    searches = page.soup.select('input[type="search"]')
    unlabeled = [
        item.get("id", "<search>")
        for item in searches
        if not item.get("aria-label") and not item.get("aria-labelledby")
    ]
    findings.append(Finding(
        "BARKLY-A11Y-002",
        AuditState.FAIL if unlabeled else AuditState.PASS,
        f"{len(unlabeled)} search input(s) lack accessible labels." if unlabeled
        else "Search controls have accessible labels.",
        page.relative_path,
    ))

    return findings
