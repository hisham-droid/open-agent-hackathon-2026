"""Stress test on randomly generated incidents (synthetic, seeded, reproducible).
Each incident has a random number of commits, a random culprit position, decoy commits (including near-misses that
add a different required setting), noisy WARN logs, and a random outcome: real cause, cause already fixed in
production, outage no commit explains, or an error that names nothing any commit touched.
The agent must confirm the right commit on real causes and refuse on the rest.
Usage: python3 scripts/benchmark.py [N] [--write]"""
import json
import pathlib
import random
import statistics
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.main import run  # noqa: E402

SETTINGS = ["CACHE_TTL_SECONDS", "QUEUE_BATCH_SIZE", "SMTP_PASSWORD_FILE", "FEATURE_FLAGS_URL", "WORKER_CONCURRENCY",
            "S3_BUCKET_NAME", "REDIS_URL_PRIMARY", "AUTH_JWT_ISSUER", "RATE_LIMIT_PER_MIN", "TRACING_SAMPLE_RATE"]
PACKAGES = [("pydantic", "1.10.13", "2.5.0"), ("sqlalchemy", "1.4.50", "2.0.23"), ("celery", "4.4.7", "5.3.4"), ("numpy", "1.24.4", "2.0.0")]
DECOY_MSGS = ["Update README", "Fix typo in docs", "Refactor payment client", "Bump lodash", "Add retry to email sender",
              "Tidy logging format", "Rename helper function", "Update changelog"]
SERVICES = ["mailer", "payments", "search", "metrics"]
OUTCOMES = ["real"] * 12 + ["fixed_in_prod"] * 3 + ["outage"] * 3 + ["unrelated_error"] * 2


def hexid(rng):
    return "".join(rng.choice("0123456789abcdef") for _ in range(7))


def make(seed, out):
    rng = random.Random(seed)
    outcome = rng.choice(OUTCOMES)
    kind = rng.choice(["setting", "package"])
    n = rng.randint(3, 8)
    shas = [hexid(rng) for _ in range(n + 1)]
    base_ts = 1_700_000_000
    ts = lambda i: __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime(base_ts + i * 3600))
    culprit_i = rng.randint(1, n)
    token = rng.choice(SETTINGS)
    pkg, old, new = rng.choice(PACKAGES)
    commits, ci = [], []
    for i, sha in enumerate(shas):
        msg, diff = rng.choice(DECOY_MSGS), "+# tidy"
        env_keys = ["CI"]
        pk = {}
        if i == culprit_i:
            if kind == "setting":
                msg, diff = f"Require {token} in config", f"-x = os.environ.get('{token[:5]}', 1)\n+x = os.environ['{token}']"
                env_keys.append(token)
            else:
                msg, diff = f"Upgrade {pkg} to {new}", f"-{pkg}=={old}\n+{pkg}=={new}"
                pk = {pkg: new}
        elif i > 0 and rng.random() < 0.3:  # near-miss decoy: requires some other setting that is NOT in the error
            other = rng.choice([s for s in SETTINGS if s != token])
            msg, diff = f"Read {other} from env", f"+y = os.environ['{other}']"
            env_keys.append(other)
        commits.append({"sha": sha, "ts": ts(i), "author": "dev", "message": msg, "files": ["app.py"], "diff": diff})
        run_ = {"run_id": f"ci-{sha}", "sha": sha, "ts": ts(i), "status": "passed", "env_keys": env_keys}
        if pk:
            run_["packages"] = pk
        ci.append(run_)
    deploys = [{"id": "d-1", "sha": shas[0], "ts": ts(0), "env": "production", "status": "success"},
               {"id": "d-2", "sha": shas[-1], "ts": ts(n + 1), "env": "production", "status": "failed"}]
    keys = {"DATABASE_URL": "x", "PORT": "8080"}
    packages = {}
    if outcome == "fixed_in_prod":
        keys[token] = "1"
        packages = {pkg: new}
    elif kind == "package":
        packages = {pkg: old}
    prod = {"deploy_id": "d-2", "keys": keys, **({"packages": packages} if packages else {})}
    if outcome in ("real", "fixed_in_prod"):
        err = f"KeyError: '{token}' required environment variable not set" if kind == "setting" else \
            f"ImportError: cannot import name 'thing' from '{pkg}' (/app/{pkg}/__init__.py)"
    elif outcome == "outage":
        err = "ConnectionError: database host unreachable after 3 attempts"
    else:
        err = "KeyError: 'TOTALLY_UNRELATED_SETTING' required environment variable not set"
    logs = [{"ts": ts(n + 1), "deploy_id": "d-2", "level": "INFO", "service": "boot", "msg": f"starting shipit {shas[-1]}"}]
    for s in rng.sample(SERVICES, rng.randint(0, 2)):
        logs.append({"ts": ts(n + 1), "deploy_id": "d-2", "level": "WARN", "service": s, "msg": f"{s} call slow, retrying"})
    logs += [{"ts": ts(n + 1), "deploy_id": "d-2", "level": "ERROR", "service": "config", "msg": err},
             {"ts": ts(n + 1), "deploy_id": "d-2", "level": "FATAL", "service": "app", "msg": "startup aborted"}]
    out.mkdir(parents=True, exist_ok=True)
    (out / "commits.json").write_text(json.dumps(commits))
    (out / "deploys.json").write_text(json.dumps(deploys))
    (out / "ci_runs.json").write_text(json.dumps(ci))
    (out / "prod_env.json").write_text(json.dumps(prod))
    (out / "logs.jsonl").write_text("\n".join(json.dumps(l) for l in logs))
    return outcome, kind, shas[culprit_i]


def benchmark(n=60):
    rows = []
    for seed in range(1, n + 1):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, kind, sha = make(seed, pathlib.Path(tmp) / "d")
            r, _ = run("why", pathlib.Path(tmp) / "d", pathlib.Path(tmp) / "o", pathlib.Path(tmp) / "m")
        want = "confirmed" if outcome == "real" else "inconclusive"
        ok = r["status"] == want and (outcome != "real" or r["culprit"]["sha"] == sha)
        rows.append({"seed": seed, "outcome": outcome, "kind": kind, "got": r["status"], "ok": ok, "rounds": r["rounds"],
                     "false_confirm": outcome != "real" and r["status"] == "confirmed",
                     "wrong_culprit": outcome == "real" and r["status"] == "confirmed" and r["culprit"]["sha"] != sha})
    return rows


def summary(rows):
    real = [r for r in rows if r["outcome"] == "real"]
    L = [f"Synthetic incidents (seeded, reproducible): {len(rows)}",
         f"Correct verdict: {sum(r['ok'] for r in rows)}/{len(rows)}",
         f"Real causes found and named correctly: {sum(r['ok'] for r in real)}/{len(real)} "
         f"({sum(r['kind'] == 'setting' for r in real)} missing-setting, {sum(r['kind'] == 'package' for r in real)} dependency-version)",
         f"Refused when it should have: {sum(r['ok'] for r in rows if r['outcome'] != 'real')}/{len(rows) - len(real)}",
         f"False confirmations (claimed a cause when there was none): {sum(r['false_confirm'] for r in rows)}",
         f"Wrong culprit named: {sum(r['wrong_culprit'] for r in rows)}",
         f"Median rounds on real causes: {statistics.median(r['rounds'] for r in real)}"]
    bad = [r for r in rows if not r["ok"]]
    if bad:
        L.append("Failures: " + ", ".join(f"seed {r['seed']} ({r['outcome']}/{r['kind']} -> {r['got']})" for r in bad))
    return "\n".join(L)


if __name__ == "__main__":
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    rows = benchmark(int(nums[0]) if nums else 60)
    s = summary(rows)
    print(s)
    if "--write" in sys.argv:
        (ROOT / "sample_outputs" / "benchmark.md").write_text(s + "\n")
