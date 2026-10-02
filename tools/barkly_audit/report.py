from collections import Counter
from html import escape
import json


def write_json_report(path, findings):
    payload = {
        "summary": dict(Counter(f.state.value for f in findings)),
        "findings": [f.as_dict() for f in findings],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_html_report(path, findings):
    counts = Counter(f.state.value for f in findings)
    cards = []
    for f in findings:
        evidence = f"<div class='evidence'>{escape(f.evidence)}</div>" if f.evidence else ""
        cards.append(
            f"<article class='finding {f.state.value.lower()}'>"
            f"<div><span class='tag'>{escape(f.state.value)}</span>"
            f"<code>{escape(f.rule)}</code></div>"
            f"<h3>{escape(f.message)}</h3>"
            f"<div class='source'>{escape(f.source)}</div>{evidence}</article>"
        )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Barkly Docs Output Audit</title>
<style>
:root{{--bg:#09090a;--panel:#111113;--text:#f6f6f7;--muted:#a8a8b0;--line:#29292e;--accent:#ff6b9d}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:36px 20px 70px}} h1{{margin:0 0 8px}} .sub{{color:var(--muted);margin-bottom:24px}}
.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}} .summary span,.tag{{border-radius:999px;padding:5px 9px;background:rgba(255,107,157,.12);color:var(--accent);font:700 11px monospace}}
.finding{{padding:16px;margin:8px 0;border:1px solid var(--line);border-radius:10px;background:var(--panel)}}
.finding h3{{font-size:14px;margin:10px 0 5px}} code,.source,.evidence{{color:var(--muted);font:12px monospace}} code{{margin-left:10px}}
.fail{{border-color:rgba(255,107,157,.35)}} .unknown{{opacity:.82}}
</style></head><body><main>
<h1>Barkly Docs Output Audit</h1>
<p class="sub">Deterministic checks of generated documentation. Human-First qualities that cannot be proven mechanically remain limited to measurable proxies.</p>
<div class="summary">{''.join(f"<span>{escape(k)} {v}</span>" for k,v in sorted(counts.items()))}</div>
{''.join(cards)}
</main></body></html>"""
    path.write_text(html, encoding="utf-8")
