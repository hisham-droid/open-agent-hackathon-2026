"""Planner -> specialists -> evaluator loop. The evaluator can reject, which forces the planner to retry or branch."""
from .specialists import DeploySpecialist, LogSpecialist, CommitSpecialist, CISpecialist

WEIGHTS = {"log_signature": 0.30, "commit_introduces": 0.30, "prod_env_missing": 0.25, "ci_explains_green": 0.15}
ACCEPT_AT = 0.85


class Evaluator:
    """Scores the current hypothesis from evidence only. Each check is pass, fail or unchecked."""

    def review(self, state):
        checks = {}
        log = state.get("log")
        checks["log_signature"] = "unchecked" if log is None else ("pass" if log["primary"] else "fail")

        cands = state.get("commits")
        cand = self.candidate(state)
        if cands is None:
            checks["commit_introduces"] = "unchecked"
        else:
            checks["commit_introduces"] = "pass" if cand else "fail"

        env = state.get("env")
        checks["prod_env_missing"] = "unchecked" if env is None else ("pass" if env["missing"] else "fail")

        ci = state.get("ci")
        checks["ci_explains_green"] = "unchecked" if ci is None else ("pass" if ci["green"] and ci["defines_token"] else "fail")

        confidence = round(sum(w for k, w in WEIGHTS.items() if checks[k] == "pass"), 2)
        unchecked = [k for k, v in checks.items() if v == "unchecked"]
        failed = [k for k, v in checks.items() if v == "fail"]
        verdict = "accept" if (not unchecked and confidence >= ACCEPT_AT) else "reject"
        critique = []
        if unchecked:
            critique.append("not yet verified: " + ", ".join(unchecked))
        if failed:
            critique.append("contradicted or unsupported: " + ", ".join(failed))
        return {"verdict": verdict, "confidence": confidence, "checks": checks, "critique": "; ".join(critique) or "all checks pass"}

    @staticmethod
    def candidate(state):
        cands = state.get("commits") or []
        i = state.get("cand_idx", 0)
        return cands[i] if i < len(cands) and cands[i]["introduced"] else None


class Planner:
    def next_actions(self, state, review):
        checks = review["checks"]
        if checks["commit_introduces"] == "unchecked":
            return ["commits.analyze"]
        if checks["commit_introduces"] == "fail":
            return []
        if checks["prod_env_missing"] == "unchecked":
            return ["env.check"]
        if checks["ci_explains_green"] == "unchecked":
            return ["ci.analyze"]
        if checks["prod_env_missing"] == "fail":
            nxt = state["cand_idx"] + 1
            cands = state["commits"]
            if nxt < len(cands) and cands[nxt]["introduced"]:
                state["rejected"].append({"sha": state["commits"][state["cand_idx"]]["sha"],
                                          "reason": "production already defines " + ", ".join(state["env"]["present"]) + ", so a missing variable cannot explain the failure"})
                state["cand_idx"] = nxt
                state["env"] = None
                state["ci"] = None
                return ["env.check", "ci.analyze"]
        return []


def investigate(ds, trace, memory, question):
    deploy_sp, log_sp, commit_sp, ci_sp = DeploySpecialist(), LogSpecialist(), CommitSpecialist(), CISpecialist()
    planner, evaluator = Planner(), Evaluator()
    state = {"cand_idx": 0, "rejected": [], "commits": None, "env": None, "ci": None, "log": None}
    trace.log("planner", "start", question=question, data_source=ds.source, memory_backend=memory.backend)

    def run(action):
        if action == "deploy.locate":
            r = deploy_sp.locate_failure(ds)
            state["deploy"] = r
            trace.log("deploy", action, failed=r and r["failed"]["id"], last_good=r and r["last_good"] and r["last_good"]["id"],
                      window=r and r["window"], evidence=r and r["evidence"])
        elif action == "log.analyze":
            r = log_sp.analyze(ds, state["deploy"]["failed"]["id"])
            state["log"] = r
            hits = memory.recall(r["tokens"])
            state["memory_hits"] = hits
            trace.log("logs", action, primary=r["primary"] and r["primary"]["msg"], tokens=r["tokens"], evidence=r["evidence"])
            trace.log("memory", "recall", tokens=r["tokens"], prior_cases=len(hits))
        elif action == "commits.analyze":
            r = commit_sp.analyze(ds, state["deploy"]["window"], state["log"]["tokens"])
            state["commits"] = r
            trace.log("commits", action, ranked=[{"sha": c["sha"], "score": c["score"], "introduced": c["introduced"]} for c in r])
        elif action == "env.check":
            cand = evaluator.candidate(state)
            r = deploy_sp.check_env(ds, cand["introduced"])
            state["env"] = r
            trace.log("deploy", action, candidate=cand["sha"], missing=r["missing"], present=r["present"], evidence=r["evidence"])
        elif action == "ci.analyze":
            cand = evaluator.candidate(state)
            r = ci_sp.analyze(ds, cand["sha"], cand["introduced"])
            state["ci"] = r
            trace.log("ci", action, candidate=cand["sha"], green=r["green"], ci_defines_token=r["defines_token"], evidence=r["evidence"])

    actions = ["deploy.locate", "log.analyze"]
    rounds, review = 0, None
    while rounds < 8:
        rounds += 1
        if not state.get("deploy") and actions[0] != "deploy.locate":
            break
        for a in actions:
            run(a)
            if a == "deploy.locate" and state["deploy"] is None:
                trace.log("planner", "abort", reason="no failed production deploy found")
                return {"status": "no_failure_found", "confidence": 0.0, "rounds": rounds}
        review = evaluator.review(state)
        trace.log("evaluator", "review", round=rounds, verdict=review["verdict"], confidence=review["confidence"],
                  checks=review["checks"], critique=review["critique"])
        if review["verdict"] == "accept":
            break
        actions = planner.next_actions(state, review)
        trace.log("planner", "replan", next_actions=actions, reason=review["critique"])
        if not actions:
            break

    cand = evaluator.candidate(state)
    status = "confirmed" if review and review["verdict"] == "accept" else "inconclusive"
    warn_services = state["log"]["warn_services"] if state.get("log") else []
    ruled_out = list(state["rejected"])
    for c in state.get("commits") or []:
        if cand and c["sha"] == cand["sha"]:
            continue
        if any(r["sha"] == c["sha"] for r in ruled_out):
            continue
        svc = next((s for s in warn_services if any(s in f for f in c["files"])), None)
        reason = (f"touches '{svc}', which only appears in non-fatal WARN lines" if svc
                  else "no overlap with the error signature in the logs")
        ruled_out.append({"sha": c["sha"], "reason": reason})

    result = {"status": status, "confidence": review["confidence"] if review else 0.0, "rounds": rounds,
              "checks": review["checks"] if review else {}, "culprit": cand, "ruled_out": ruled_out,
              "failed_deploy": state["deploy"]["failed"], "last_good": state["deploy"]["last_good"],
              "primary_log": state["log"]["primary"], "primary_log_id": state["log"].get("primary_id"),
              "env": state["env"], "ci": state["ci"], "memory_hits": state.get("memory_hits", [])}
    if status == "confirmed" and cand:
        result["cause"] = (f"Commit {cand['sha']} ('{cand['message']}') made {', '.join(cand['introduced'])} a required setting, "
                           f"but production does not define it, so the new version aborted at startup and failed its health check.")
        memory.remember({"tokens": state["log"]["tokens"], "sha": cand["sha"], "message": cand["message"],
                         "confidence": result["confidence"], "deploy": state["deploy"]["failed"]["id"]})
    else:
        lead = f" Leading suspect: commit {cand['sha']} ('{cand['message']}')." if cand else ""
        result["cause"] = "Inconclusive: the evidence does not support a single root cause." + lead
    trace.log("planner", "finish", status=status, confidence=result["confidence"], rounds=rounds,
              culprit=cand["sha"] if cand else None)
    return result
