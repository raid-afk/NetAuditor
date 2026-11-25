"""Standalone UTF-8 reports. No external fonts, scripts or assets."""
import csv
import json
import os
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile

CSS = """
*{box-sizing:border-box}body{margin:0;background:#0c141c;color:#e5eef4;
font:16px/1.55 system-ui,sans-serif}main{max-width:1000px;margin:auto;padding:6vh 5vw}
header{border-top:4px solid #56ddbb;padding-top:18px}small,dt{color:#97aeba}
h1{font-size:clamp(2rem,6vw,4rem);margin:.15em 0;letter-spacing:-.045em}
h2{font-size:1.25rem}dl{display:flex;gap:22px;flex-wrap:wrap;background:#142431;
border:1px solid #28404b;padding:18px;border-radius:10px}dd{margin:4px 0;font-weight:650}
section{overflow-x:auto}table{width:100%;border-collapse:collapse}th,td{text-align:left;
padding:12px;border-bottom:1px solid #29404b}th,p{color:#adc1cb}code{overflow-wrap:anywhere}
b{font-size:.85em;border-radius:6px;padding:3px 8px}.High{background:#613337}
.Review{background:#544729}.Info{background:#1a4a43}footer{margin-top:2rem;color:#99b2bd}
"""


def html_report(report):
    def safe(value):
        return escape(str(value), quote=True)

    metadata = [("Address", report["ip"]), ("Started (UTC)", report["started_utc"]),
                ("Duration", f'{report["duration_s"]:.3f} s'), ("Ports checked", report["tested"]),
                ("Engine", report["engine"])]
    cards = "".join(f"<div><dt>{k}</dt><dd>{safe(v)}</dd></div>" for k, v in metadata)
    rows = []
    for item in report["ports"]:
        priority = safe(item["priority"])
        rows.append(f'<tr><td>{item["port"]}/tcp</td><td>{safe(item["service"])}</td>'
                    f'<td><b class="{priority}">{priority}</b></td>'
                    f'<td><code>{safe(item["banner"]) or "—"}</code></td></tr>')
    states = " · ".join(f"{safe(k)} {v}" for k, v in report["states"].items() if v)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>NetAudit-CLI report</title>
<style>{CSS}</style><main><header><small>NetAudit-CLI / TCP inventory</small>
<h1>{safe(report["target"])}</h1></header><dl>{cards}</dl><p>{states}</p>
<h2>Open ports ({len(rows)})</h2><section><table><thead><tr><th>Port</th><th>Expected service</th>
<th>Review priority</th><th>Observed greeting</th></tr></thead><tbody>
{''.join(rows) or '<tr><td colspan="4">No open TCP ports observed.</td></tr>'}</tbody></table></section>
<footer>Priority reflects the usual purpose of the port. Confirm the service and intended exposure.
A dash means no printable greeting was collected.</footer></main></html>"""


def write_report(path, report):
    # Replace atomically so an interrupted export preserves a previous report.
    path = Path(path)
    tmp = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                                delete=False) as stream:
            tmp = Path(stream.name)
            if path.suffix.lower() == ".html":
                stream.write(html_report(report))
            elif path.suffix.lower() == ".json":
                json.dump(report, stream, indent=2, ensure_ascii=False)
            else:
                writer = csv.writer(stream)
                writer.writerow(["target", "ip", "started_utc", "duration_s",
                                 "port", "service", "priority", "banner"])
                for row in report["ports"]:
                    values = [report[k] for k in ("target", "ip", "started_utc", "duration_s")]
                    values.extend(row[k] for k in ("port", "service", "priority", "banner"))
                    # Keep imported strings from becoming spreadsheet formulas.
                    writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(
                        ("=", "+", "-", "@")) else v for v in values])
        os.replace(tmp, path)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
