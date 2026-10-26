def render(question, r):
    L = [f"# Investigation report", "", f"**Question:** {question}", ""]
    if r["status"] == "no_failure_found":
        return "\n".join(L + ["No failed production deploy was found in the data."])
    L += [f"**Status:** {r['status']}  |  **Confidence:** {int(r['confidence'] * 100)}%  |  **Rounds:** {r['rounds']}", "",
          "## Likely cause", r["cause"], "", "## Evidence"]
    if r.get("scope"):
        s = r["scope"]
        L.insert(-1, f"_Worked through {s['commits_in_window']} commits since the last good deploy and {s['log_lines']} log lines "
                     f"from the failed deploy._")
        L.insert(-1, "")
    f, g = r["failed_deploy"], r["last_good"]
    L.append(f"- Deploy `{f['id']}` ({f['sha']}) failed; last good deploy was `{g['id']}` ({g['sha']}) [deploy:{f['id']}, deploy:{g['id']}]")
    if r["primary_log"]:
        L.append(f"- First error in the failed deploy: `{r['primary_log']['msg']}` [{r['primary_log_id']}]")
    c = r["culprit"]
    if c:
        L.append(f"- Commit {c['sha']} adds a requirement on {', '.join(c['introduced'])} [commit:{c['sha']}]")
    if r["env"]:
        L.append((f"- Production check: {'; '.join(r['env']['notes'])} [{r['env']['evidence'][0]}]" if r['env'].get("notes") else
                  f"- Production env missing: {', '.join(r['env']['missing']) or 'nothing'}; defined: {', '.join(r['env']['present']) or 'none'} [{r['env']['evidence'][0]}]"))
    if r["ci"]:
        L.append(f"- CI run `{r['ci']['run']}` green: {r['ci']['green']}; CI has what the commit needs: {r['ci']['defines_token']}"
                 " (this is why tests did not catch it)" if r['ci']['green'] and r['ci']['defines_token'] else
                 f"- CI run `{r['ci']['run']}` green: {r['ci']['green']}; CI has what the commit needs: {r['ci']['defines_token']}")
    ex = r.get("explanation")
    if ex:
        c = ex["content"]
        who = (f"written by `{ex['model']}` through Meterless Nightshift; every citation checked against collected evidence"
               if ex["mode"] == "model" else "template (no model output was used" + (f": {ex['rejected']}" if ex["rejected"] else "") + ")")
        L += ["", "## In plain English", f"_{who}_", "", c["summary"], ""]
        L += [f"- {p['text']} " + " ".join(f"[{x}]" for x in p["cites"]) for p in c["points"]]
        L += ["", f"**Suggested fix:** {c['fix']['text']} " + " ".join(f"[{x}]" for x in c["fix"]["cites"])]
    L += ["", "## Checks"] + [f"- {k}: {v}" for k, v in r["checks"].items()]
    L += ["", "## Ruled out"] + [f"- {x['sha']}: {x['reason']}" for x in r["ruled_out"]]
    mem = r.get("memory") or {}
    L += ["", "## Memory (H-MEM)"]
    if mem.get("retrieved"):
        top = mem["retrieved"][0]
        L.append(f"- Retrieved {len(mem['retrieved'])} memory (strategy: {mem['strategy']}); top match `{top['id']}` "
                 f"scored {top['score']} at confidence {top['confidence']}: {top['content']}")
        if mem["fast_path"]:
            L.append("- The planner used it to run the likely checks together. The evaluator still verified every check from evidence.")
        if mem.get("feedback"):
            L.append(f"- Outcome fed back as `{mem['feedback']['verdict']}`; memory confidence is now {mem['feedback']['confidence_after']}.")
    else:
        L.append("- Nothing relevant in memory yet (cold start).")
    if mem.get("lesson_id"):
        L.append(f"- Saved lesson `{mem['lesson_id']}` to long-term memory for future runs.")
    L += ["", "Full step-by-step trace: `trace.jsonl`."]
    return "\n".join(L)
