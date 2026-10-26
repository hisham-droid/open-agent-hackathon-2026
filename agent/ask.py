"""Follow-up questions about a finished investigation, answered only from what the agent verified.
A model may phrase the answer, but it must cite evidence ids, and anything it invents is rejected."""
import json
import re

from .explain import SHA_RE, TOKEN_RE, catalog, parse


def facts_for(r):
    facts = catalog(r)
    facts["verdict"] = f"The verdict is {r['status']} at {int(r['confidence'] * 100)}% confidence after {r['rounds']} rounds."
    for k, v in (r.get("checks") or {}).items():
        facts[f"check:{k}"] = f"The check {k.replace('_', ' ')} came out as {v}."
    mem = r.get("memory") or {}
    facts["memory"] = ("Memory recalled a lesson from an earlier incident and the planner ran the likely checks together; "
                       "the evaluator still verified each one." if mem.get("fast_path") else
                       "Nothing relevant was in memory, so the checks ran one at a time.")
    return facts


def fallback(question, r, facts):
    q = question.lower()
    for x in r.get("ruled_out", []):
        if x["sha"] in q:
            return {"answer": f"Commit {x['sha']} was ruled out: {x['reason']}.", "cites": [f"commit:{x['sha']}"]}
    if any(w in q for w in ("memory", "learn", "remember")):
        return {"answer": facts["memory"], "cites": ["memory"]}
    if any(w in q for w in ("confiden", "sure", "certain", "check")):
        return {"answer": facts["verdict"] + " " + " ".join(v for k, v in facts.items() if k.startswith("check:")),
                "cites": ["verdict"] + [k for k in facts if k.startswith("check:")]}
    if any(w in q for w in ("fix", "do about", "next")):
        ex = (r.get("explanation") or {}).get("content", {}).get("fix")
        if ex:
            return {"answer": ex["text"], "cites": ex["cites"]}
    return {"answer": r["cause"], "cites": ["verdict"]}


def prompt(question, r, facts):
    lines = "\n".join(f"- [{k}] {v}" for k, v in facts.items())
    return ("You answer follow-up questions about a build-failure investigation. Use ONLY these verified facts. "
            "If they do not answer the question, say the agent did not check that.\n"
            f"Verified facts:\n{lines}\n\nQuestion: {question}\n\n"
            'Reply with ONLY one JSON object: {"answer": string (max 3 sentences), "cites": [evidence ids from the list]}. '
            "Never mention a commit, deploy, setting or number that is not in the facts.")


def ask(question, r, generator=None):
    facts = facts_for(r)
    if generator is not None:
        try:
            obj = parse(generator(prompt(question, r, facts)))
            ans, cites = obj["answer"], obj["cites"]
            allowed = " ".join(facts.values()) + " " + " ".join(facts) + " " + question
            if not isinstance(ans, str) or not ans or not cites or any(c not in facts for c in cites):
                raise ValueError("uncited or unknown id")
            for m in SHA_RE.findall(ans) + TOKEN_RE.findall(ans):
                if m not in allowed:
                    raise ValueError(f"invented identifier {m}")
            return {"mode": "model", "model": getattr(generator, "last_model", None), "answer": ans, "cites": cites}
        except Exception as e:
            fb = fallback(question, r, facts)
            return {"mode": "template", "model": None, "rejected": str(e), **fb}
    return {"mode": "template", "model": None, "rejected": None, **fallback(question, r, facts)}
