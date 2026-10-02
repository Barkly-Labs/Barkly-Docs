import argparse
from pathlib import Path

from .crawler import BarklyCrawler
from .report import write_html_report, write_json_report
from .checks.structure import check_document_structure, check_undefined_values
from .checks.accessibility import check_accessibility
from .checks.evidence import check_evidence
from .checks.routing import check_data_routing
from .checks.ux import check_human_first_proxies


def audit(output_dir: Path):
    findings = []
    crawler = BarklyCrawler(output_dir)
    pages = list(crawler.pages())

    for page in pages:
        findings += check_document_structure(page)
        findings += check_undefined_values(page)
        findings += check_accessibility(page)
        findings += check_evidence(page)
        findings += check_data_routing(page)
        findings += check_human_first_proxies(page)

    return pages, findings


def main():
    parser = argparse.ArgumentParser(description="Audit generated Barkly Docs output.")
    parser.add_argument("output", type=Path, help="Generated Barkly Docs output directory")
    parser.add_argument("--report-dir", type=Path, default=None)
    args = parser.parse_args()

    output = args.output.resolve()
    if not output.exists() or not output.is_dir():
        parser.error(f"Output directory does not exist: {output}")

    pages, findings = audit(output)
    report_dir = (args.report_dir or output).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    html_report = report_dir / "barkly-audit.html"
    json_report = report_dir / "barkly-audit.json"
    write_html_report(html_report, findings)
    write_json_report(json_report, findings)

    counts = {}
    for finding in findings:
        counts[finding.state.value] = counts.get(finding.state.value, 0) + 1

    print(f"Audited {len(pages)} HTML page(s)")
    for state in ("PASS", "WARN", "FAIL", "UNKNOWN"):
        print(f"{state}: {counts.get(state, 0)}")
    print(f"HTML report: {html_report}")
    print(f"JSON report: {json_report}")

    raise SystemExit(1 if counts.get("FAIL", 0) else 0)


if __name__ == "__main__":
    main()
