"""Builds docs/demo.html from the saved live proof runs (real traces, real reports)."""
import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent

def section(md, name):
    m = re.search(rf"## {name}\n(.*?)(?=\n## |\nFull step)", md, re.S)
    return m.group(1).strip() if m else ""

runs = []
for key, title in (("live-run-1", "Run 1 · cold start"), ("live-run-2", "Run 2 · with memory")):
    d = ROOT / "sample_outputs" / key
    steps = []
    for l in (d / "trace.jsonl").read_text().splitlines():
        s = json.loads(l); s.pop("sql", None); s.pop("ts", None); s.pop("evidence", None)
        steps.append(s)
    md = (d / "report.md").read_text()
    runs.append({"key": key, "title": title, "steps": steps, "cause": section(md, "Likely cause"),
                 "evidence": [x[2:] for x in section(md, "Evidence").splitlines() if x.startswith("- ")],
                 "ruled_out": [x[2:] for x in section(md, "Ruled out").splitlines() if x.startswith("- ")]})
commits = json.loads((ROOT / "sample_data" / "commits.json").read_text())
commits = [{"sha": c["sha"], "author": c["author"], "message": c["message"], "files": c["files"]} for c in commits]
tpl = (ROOT / "scripts" / "demo_template.html").read_text()
out = ROOT / "docs" / "demo.html"
out.write_text(tpl.replace("__DATA__", json.dumps({"runs": runs, "commits": commits})))
print(out, out.stat().st_size)
