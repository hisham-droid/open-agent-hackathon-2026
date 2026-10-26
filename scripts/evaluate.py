"""Run the agent on several different incidents and check it reaches the right verdict on each, including when it
should refuse to name a cause. Usage: python3 scripts/evaluate.py [--write]"""
import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.main import run  # noqa: E402


def _load(d):
    return {n: (json.loads((d / n).read_text()) if n.endswith(".json") else
                [json.loads(l) for l in (d / n).read_text().splitlines() if l.strip()])
            for n in ("commits.json", "deploys.json", "ci_runs.json", "prod_env.json", "logs.jsonl")}


def _save(d, data):
    for n, v in data.items():
        (d / n).write_text("\n".join(json.dumps(x) for x in v) if n.endswith(".jsonl") else json.dumps(v, indent=1))


def _set_error(data, msg):
    for l in data["logs.jsonl"]:
        if l["deploy_id"] == "d-102" and l["service"] == "config":
            l["msg"] = msg


def planted(d):
    pass


def other_service_secret(d):
    """A different commit (the email change) adds a required API token that production lacks."""
    c = next(x for x in d["commits.json"] if x["sha"] == "77bb88c")
    c["message"] = "Add retry to email sender, read API token from env"
    c["diff"] += "\n+    token = os.environ['MAIL_API_TOKEN']"
    next(r for r in d["ci_runs.json"] if r["sha"] == "77bb88c")["env_keys"].append("MAIL_API_TOKEN")
    _set_error(d, "KeyError: 'MAIL_API_TOKEN' required environment variable not set")


def infrastructure_outage(d):
    """The error names no setting and no commit touches it: the agent must not blame a commit."""
    _set_error(d, "ConnectionError: database host unreachable after 3 attempts")


def already_fixed_in_prod(d):
    """Production already defines the variable, so the obvious suspect is contradicted by evidence."""
    d["prod_env.json"]["keys"]["DATABASE_POOL_SIZE"] = "20"


def dependency_skew(d):
    """A dependency upgrade lands; CI installs the new version, production still runs the old one."""
    c = next(x for x in d["commits.json"] if x["sha"] == "55aa66b")
    c.update(message="Upgrade pydantic to 2.5.0", files=["requirements.txt", "app/models.py"],
             diff="--- a/requirements.txt\n+++ b/requirements.txt\n-pydantic==1.10.13\n+pydantic==2.5.0\n"
                  "--- a/app/models.py\n+++ b/app/models.py\n+from pydantic import field_validator")
    ci = next(r for r in d["ci_runs.json"] if r["sha"] == "55aa66b")
    ci["packages"] = {"pydantic": "2.5.0"}
    d["prod_env.json"]["packages"] = {"pydantic": "1.10.13"}
    _set_error(d, "ImportError: cannot import name 'field_validator' from 'pydantic' (/app/venv/pydantic/__init__.py)")


def dependency_already_current(d):
    """Same error, but production already runs the required version, so the upgrade cannot explain it."""
    dependency_skew(d)
    d["prod_env.json"]["packages"] = {"pydantic": "2.5.0"}


SCENARIOS = [
    ("planted", planted, "confirmed", "9f8e7d6"),
    ("other-service-secret", other_service_secret, "confirmed", "77bb88c"),
    ("dependency-version-skew", dependency_skew, "confirmed", "55aa66b"),
    ("infrastructure-outage", infrastructure_outage, "inconclusive", None),
    ("contradicted-by-prod", already_fixed_in_prod, "inconclusive", None),
    ("dependency-already-current", dependency_already_current, "inconclusive", None),
]


def build(name, mutate, base, dest):
    dest = pathlib.Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(base, dest)
    data = _load(dest)
    mutate(data)
    _save(dest, data)
    return dest


def evaluate(write=False, generator=None):
    rows = []
    for name, mutate, want_status, want_sha in SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp:
            data = build(name, mutate, ROOT / "sample_data", pathlib.Path(tmp) / "data")
            out = ROOT / "sample_outputs" / f"scenario-{name}" if write else pathlib.Path(tmp) / "out"
            if write:
                shutil.rmtree(out, ignore_errors=True)
                shutil.rmtree(ROOT / "scenarios" / name, ignore_errors=True)
                shutil.copytree(data, ROOT / "scenarios" / name)
            r, _ = run("Why did the latest production deploy fail?", data, out, pathlib.Path(tmp) / "mem", generator=generator)
        sha = r["culprit"]["sha"] if r["status"] == "confirmed" else None
        ok = r["status"] == want_status and sha == want_sha
        rows.append({"scenario": name, "expected": want_status + (f" {want_sha}" if want_sha else ""),
                     "got": r["status"] + (f" {sha}" if sha else ""), "confidence": r["confidence"],
                     "rounds": r["rounds"], "ok": ok})
    return rows


def table(rows):
    L = ["| Scenario | Expected | Agent said | Confidence | Rounds | Pass |", "|---|---|---|---|---|---|"]
    L += [f"| {r['scenario']} | {r['expected']} | {r['got']} | {r['confidence']} | {r['rounds']} | {'yes' if r['ok'] else 'NO'} |" for r in rows]
    return "\n".join(L)


if __name__ == "__main__":
    rows = evaluate(write="--write" in sys.argv)
    print(table(rows))
    if "--write" in sys.argv:
        (ROOT / "sample_outputs" / "evaluation.md").write_text(table(rows) + "\n")
    sys.exit(0 if all(r["ok"] for r in rows) else 1)
