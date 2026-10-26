"""Evidence-grounded explanation. A model (Nemotron through Nightshift) writes the plain-English story, but the
evaluator's verdict is not its to change: every point must cite evidence ids the agent actually collected, and any
text that invents a commit, deploy, log line or setting name is rejected and replaced by a deterministic template."""
import json
import re

from .specialists import TOKEN_RE

SHA_RE = re.compile(r"\b[0-9a-f]{7}\b")
CITE_RE = re.compile(r"\[((?:deploy|commit|log|env|ci):[^\]\s]+)\]")


def catalog(r):
    """Every fact the agent verified, keyed by evidence id."""
    facts = {}
    f, g = r.get("failed_deploy"), r.get("last_good")
    if f:
        facts[f"deploy:{f['id']}"] = f"Production deploy {f['id']} (commit {f['sha']}) failed."
    if g:
        facts[f"deploy:{g['id']}"] = f"Deploy {g['id']} (commit {g['sha']}) was the last good production deploy."
    if r.get("primary_log"):
        facts[r["primary_log_id"]] = f"First error in the failed deploy: {r['primary_log']['msg']}"
    c = r.get("culprit")
    if c:
        facts[f"commit:{c['sha']}"] = (f"Commit {c['sha']} ('{c['message']}') adds a requirement on "
                                       f"{', '.join(c['introduced'])}" + (f" ({', '.join(f'{k} {v}' for k, v in c['required'].items())})" if c.get("required") else "") + ".")
    env = r.get("env")
    if env:
        facts[env["evidence"][0]] = (("Production check: " + "; ".join(env["notes"]) + ".") if env.get("notes") else
                                     f"Production env is missing {', '.join(env['missing']) or 'nothing'} and defines "
                                     f"{', '.join(env['present']) or 'none of the suspect settings'}.")
    ci = r.get("ci")
    if ci and ci.get("evidence"):
        facts[ci["evidence"][0]] = (f"CI run {ci['run']} green={ci['green']}; CI defines the setting={ci['defines_token']}.")
    for x in r.get("ruled_out", []):
        facts.setdefault(f"commit:{x['sha']}", f"Commit {x['sha']} was ruled out: {x['reason']}.")
    return facts


def fallback(r, facts):
    points = [{"text": t, "cites": [k]} for k, t in facts.items() if not k.startswith("commit:") or
              (r.get("culprit") and k == f"commit:{r['culprit']['sha']}")]
    c, env = r.get("culprit"), r.get("env")
    if r["status"] == "confirmed" and c and env and env["missing"]:
        fix = {"text": (f"Rebuild and redeploy production so {', '.join(env['missing'])} matches the commit, and make CI install exactly what production runs."
                        if env.get("kind") == "package" else
                        f"Add {', '.join(env['missing'])} to the production environment, or give it a safe default, "
                        "and make CI run with a production-like environment so this is caught before deploy."),
               "cites": [f"commit:{c['sha']}", env["evidence"][0]]}
    else:
        fix = {"text": "Do not act on a single suspect yet: gather the missing evidence listed in the checks first.",
               "cites": [k for k in list(facts)[:1]]}
    return {"summary": r["cause"], "points": points, "fix": fix}


def prompt(r, facts):
    lines = "\n".join(f"- [{k}] {v}" for k, v in facts.items())
    return (
        "You are explaining a build-failure investigation to an engineer. Use ONLY the verified facts below.\n"
        f"Verdict from the evaluator: {r['status']} at confidence {r['confidence']}. Do not change it.\n"
        f"Verified facts:\n{lines}\n\n"
        'Reply with ONLY a JSON object: {"summary": string, "points": [{"text": string, "cites": [evidence ids]}], '
        '"fix": {"text": string, "cites": [evidence ids]}}. Give 3 to 5 points. Every cite must be an id from the list. '
        "Do not mention any commit, deploy, setting name or number that is not in the facts. If the verdict is "
        "inconclusive, say so and do not name a root cause."
    )


def parse(text):
    text = text.strip()
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        raise ValueError("no JSON object")
    return json.loads(text[a:b + 1])


def validate(obj, r, facts):
    if not isinstance(obj, dict) or not isinstance(obj.get("points"), list) or not 2 <= len(obj["points"]) <= 6:
        raise ValueError("bad shape")
    pieces = [obj.get("summary", "")] + [p.get("text", "") for p in obj["points"]] + [obj.get("fix", {}).get("text", "")]
    if not all(isinstance(t, str) and t and len(t) < 400 for t in pieces):
        raise ValueError("bad text")
    for p in obj["points"] + [obj.get("fix", {})]:
        cites = p.get("cites")
        if not cites or any(c not in facts for c in cites):
            raise ValueError(f"uncited or unknown evidence id: {cites}")
    allowed = " ".join(facts.values()) + " " + " ".join(facts)
    for t in " ".join(pieces).split():
        for m in SHA_RE.findall(t) + TOKEN_RE.findall(t):
            if m not in allowed:
                raise ValueError(f"invented identifier: {m}")
    if r["status"] != "confirmed" and re.search(r"\b(root cause is|caused by|confirmed)\b", " ".join(pieces), re.I):
        raise ValueError("overclaims on an inconclusive verdict")
    return obj


def explain(r, generator=None, attempts=2):
    facts = catalog(r)
    base = {"evidence_count": len(facts)}
    if generator is None:
        return {"mode": "template", "model": None, "provider": None, "content": fallback(r, facts), "rejected": None, **base}
    ask, err, raw = prompt(r, facts), None, ""
    for n in range(attempts):
        try:
            raw = generator(ask)
            obj = validate(parse(raw), r, facts)
            return {"mode": "model", "model": getattr(generator, "last_model", None), "provider": "meterless-nightshift",
                    "content": obj, "rejected": None, "attempts": n + 1, **base}
        except Exception as e:
            err = e
            ask = (prompt(r, facts) + f"\n\nYour previous reply was rejected ({e}). Reply again with ONLY one short, "
                   "valid JSON object: double quotes, commas between items, no comments, no text before or after.")
    return {"mode": "template", "model": None, "provider": None, "content": fallback(r, facts),
            "rejected": f"model output not accepted after {attempts} tries: {err}; started with: {raw[:160]!r}", **base}
