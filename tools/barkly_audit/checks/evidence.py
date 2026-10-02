from ..models import Finding, AuditState

EVIDENCE_STATES = {"DECLARED", "DETECTED", "INFERRED", "UNKNOWN"}


def check_evidence(page):
    page_text = " ".join(page.soup.stripped_strings).upper()
    present = {state for state in EVIDENCE_STATES if state in page_text}

    # Only require the full legend on pages that appear to expose evidence semantics.
    evidence_page = bool(present)
    if not evidence_page:
        return [Finding(
            "BARKLY-EVIDENCE-001",
            AuditState.UNKNOWN,
            "This page does not expose evidence labels; evidence-state compliance is not established here.",
            page.relative_path,
        )]

    missing = EVIDENCE_STATES - present
    return [Finding(
        "BARKLY-EVIDENCE-001",
        AuditState.WARN if missing else AuditState.PASS,
        "Missing evidence labels: " + ", ".join(sorted(missing)) if missing
        else "DECLARED, DETECTED, INFERRED, and UNKNOWN remain visibly distinguishable.",
        page.relative_path,
    )]
