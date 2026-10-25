def render(question, r):
    L = [f"# Investigation report", "", f"**Question:** {question}", ""]
    if r["status"] == "no_failure_found":
        return "\n".join(L + ["No failed production deploy was found in the data."])
    L += [f"**Status:** {r['status']}  |  **Confidence:** {int(r['confidence'] * 100)}%  |  **Rounds:** {r['rounds']}", "",
          "## Likely cause", r["cause"], "", "## Evidence"]
    f, g = r["failed_deploy"], r["last_good"]
    L.append(f"- Deploy `{f['id']}` ({f['sha']}) failed; last good deploy was `{g['id']}` ({g['sha']}) [deploy:{f['id']}, deploy:{g['id']}]")
    if r["primary_log"]:
        L.append(f"- First error in the failed deploy: `{r['primary_log']['msg']}` [{r['primary_log_id']}]")
    c = r["culprit"]
    if c:
        L.append(f"- Commit {c['sha']} adds a requirement on {', '.join(c['introduced'])} [commit:{c['sha']}]")
    if r["env"]:
        L.append(f"- Production env missing: {', '.join(r['env']['missing']) or 'nothing'}; defined: {', '.join(r['env']['present']) or 'none'} [{r['env']['evidence'][0]}]")
    if r["ci"]:
        L.append(f"- CI run `{r['ci']['run']}` green: {r['ci']['green']}; CI defines the variable: {r['ci']['defines_token']}"
                 " (this is why tests did not catch it)" if r['ci']['green'] and r['ci']['defines_token'] else
                 f"- CI run `{r['ci']['run']}` green: {r['ci']['green']}; CI defines the variable: {r['ci']['defines_token']}")
    L += ["", "## Checks"] + [f"- {k}: {v}" for k, v in r["checks"].items()]
    L += ["", "## Ruled out"] + [f"- {x['sha']}: {x['reason']}" for x in r["ruled_out"]]
    if r["memory_hits"]:
        L += ["", "## Seen before", *[f"- {h['sha']} ('{h['message']}') on {h['deploy']}" for h in r["memory_hits"]]]
    L += ["", "Full step-by-step trace: `trace.jsonl`."]
    return "\n".join(L)
