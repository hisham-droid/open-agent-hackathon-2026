"""Planner -> specialists -> evaluator loop. The evaluator can reject, which forces the planner to retry or branch."""
from .explain import explain
from .specialists import DeploySpecialist, LogSpecialist, CommitSpecialist, CISpecialist, shape_of

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


FAILURE_CLASS = "required-config-missing-in-prod"
FAST_PATH_MIN_CONFIDENCE = 0.5


def investigate(ds, trace, memory, question, run_id="run-1"):
    deploy_sp, log_sp, commit_sp, ci_sp = DeploySpecialist(), LogSpecialist(), CommitSpecialist(), CISpecialist()
    planner, evaluator = Planner(), Evaluator()
    state = {"cand_idx": 0, "rejected": [], "commits": None, "env": None, "ci": None, "log": None,
             "fast_path": False, "memory_payload": None, "memory_top": None}
    trace.log("planner", "start", question=question, data_source=ds.source, memory_backend=memory.backend, run_id=run_id)
    if getattr(ds, "queries", None):
        trace.log("data", "load", source=ds.source, sql=ds.queries, row_counts=getattr(ds, "row_counts", {}))
    trace.log("hmem", "hydrate", **memory.start_run(run_id))

    def mine(agent, task, summary, kind="tool_result"):
        made, mode = memory.mine({"kind": kind, "summary": summary}, agent, run_id, task)
        gen = getattr(memory, "generator", None)
        trace.log("hmem", "mine", source_agent=agent, task=task, memories=[m["id"] for m in made], mode=mode,
                  model=getattr(gen, "last_model", None) if mode == "model" else None, provider="meterless-nightshift" if gen else None)

    def run(action):
        if action == "deploy.locate":
            r = deploy_sp.locate_failure(ds)
            state["deploy"] = r
            trace.log("deploy", action, failed=r and r["failed"]["id"], last_good=r and r["last_good"] and r["last_good"]["id"],
                      window=r and r["window"], evidence=r and r["evidence"])
        elif action == "log.analyze":
            r = log_sp.analyze(ds, state["deploy"]["failed"]["id"])
            state["log"] = r
            trace.log("logs", action, primary=r["primary"] and r["primary"]["msg"], tokens=r["tokens"], evidence=r["evidence"])
            if r["primary"]:
                # Query by failure shape, not by this incident's variable name, so lessons generalise across incidents.
                shape = shape_of(r["primary"]["msg"])
                query = f"{shape} deploy failed startup"
                payload = memory.retrieve(query, "planner", run_id)
                state["memory_payload"] = payload
                trace.log("hmem", "retrieve", strategy=payload["strategy"], reason=payload["retrievalReason"],
                          hits=[{"id": m["id"], "score": m["score"], "confidence": m["confidence"]} for m in payload["memories"]])
                top = next((m for m in payload["memories"] if m["type"] == "procedural" and m["layer"] == "long_term"
                            and m["confidence"] >= FAST_PATH_MIN_CONFIDENCE), None)
                if top:
                    state["memory_top"], state["fast_path"] = top, True
                # Mine after retrieving so a run never recalls its own fresh observation as prior knowledge.
                mine("logs", action, f"First error in deploy {state['deploy']['failed']['id']}: {r['primary']['msg']}")
        elif action == "commits.analyze":
            r = commit_sp.analyze(ds, state["deploy"]["window"], state["log"]["tokens"])
            state["commits"] = r
            trace.log("commits", action, ranked=[{"sha": c["sha"], "score": c["score"], "introduced": c["introduced"]} for c in r])
            if r and r[0]["introduced"]:
                mine("commits", action, f"Commit {r[0]['sha']} ('{r[0]['message']}') introduced {', '.join(r[0]['introduced'])}")
        elif action == "env.check":
            cand = evaluator.candidate(state)
            r = deploy_sp.check_env(ds, cand["introduced"], cand.get("required"))
            state["env"] = r
            trace.log("deploy", action, candidate=cand["sha"], missing=r["missing"], present=r["present"], evidence=r["evidence"])
            mine("deploy", action, f"Production env missing {r['missing'] or 'nothing'}; defines {r['present'] or 'none'}")
        elif action == "ci.analyze":
            cand = evaluator.candidate(state)
            r = ci_sp.analyze(ds, cand["sha"], cand["introduced"], cand.get("required"))
            state["ci"] = r
            trace.log("ci", action, candidate=cand["sha"], green=r["green"], ci_defines_token=r["defines_token"], evidence=r["evidence"])
            mine("ci", action, f"CI run {r['run']} green={r['green']}, CI defines the variable={r['defines_token']}")

    actions = ["deploy.locate", "log.analyze"]
    rounds, review = 0, None
    while rounds < 8:
        rounds += 1
        for a in actions:
            run(a)
            if a == "deploy.locate" and state["deploy"] is None:
                trace.log("planner", "abort", reason="no failed production deploy found")
                return {"status": "no_failure_found", "confidence": 0.0, "rounds": rounds}
        if rounds == 1 and state["fast_path"]:
            # Memory shapes the plan (run the likely checks together) but never lowers the evidence bar:
            # the evaluator below still requires every check to pass.
            trace.log("planner", "plan_from_memory", memory_id=state["memory_top"]["id"], score=state["memory_top"]["score"],
                      steps=["commits.analyze", "env.check", "ci.analyze"],
                      note="evaluator still verifies every check from evidence")
            run("commits.analyze")
            if evaluator.candidate(state):
                run("env.check")
                run("ci.analyze")
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
              "env": state["env"], "ci": state["ci"]}
    fid = state["deploy"]["failed"]["id"]
    result["scope"] = {"commits_in_window": len(state["deploy"]["window"]),
                       "log_lines": sum(1 for l in ds.logs if l["deploy_id"] == fid),
                       "ci_runs": len(ds.ci_runs), "candidates_checked": len(state["rejected"]) + (1 if cand else 0)}
    mem = {"retrieved": [m for m in (state["memory_payload"] or {}).get("memories", [])],
           "strategy": (state["memory_payload"] or {}).get("strategy"), "fast_path": state["fast_path"],
           "feedback": None, "lesson_id": None}

    if status == "confirmed" and cand:
        if state["env"] and state["env"].get("kind") == "package":
            result["cause"] = (f"Commit {cand['sha']} ('{cand['message']}') moved {', '.join(cand['introduced'])} to a new version, but "
                               f"{'; '.join(state['env']['notes'])}, so the new code failed at startup. CI installed the new version, which is why it stayed green.")
        else:
            result["cause"] = (f"Commit {cand['sha']} ('{cand['message']}') made {', '.join(cand['introduced'])} a required setting, "
                               f"but production does not define it, so the new version aborted at startup and failed its health check.")
    else:
        lead = f" Leading suspect: commit {cand['sha']} ('{cand['message']}')." if cand else ""
        result["cause"] = "Inconclusive: the evidence does not support a single root cause." + lead

    # Feedback adaptation: the outcome tells memory whether the recalled knowledge helped.
    if state["fast_path"]:
        verdict = "helpful" if status == "confirmed" else "wrong"
        updated = memory.feedback(state["memory_top"]["id"], verdict, "evaluator",
                                  reason=f"memory-guided plan ended {status} at confidence {result['confidence']}")
        mem["feedback"] = {"memory_id": state["memory_top"]["id"], "verdict": verdict,
                           "confidence_after": updated["confidence"] if updated else None}
        trace.log("hmem", "feedback", **mem["feedback"])

    if status == "confirmed" and cand and state["env"] and state["env"]["missing"]:
        pkg = state["env"].get("kind") == "package"
        lesson = memory.remember_lesson(
            "dependency-version-skew-in-prod" if pkg else FAILURE_CLASS,
            ("Deploy fails at startup with an ImportError or missing module. Check whether a recent commit moved that package "
             "to a new version, then which version production actually runs. CI can stay green because it installs the new "
             "version while production keeps the old one.") if pkg else
            "Deploy fails at startup with a KeyError or 'required environment variable not set'. Check whether a recent "
            "commit made that variable required, then whether production defines it. CI can stay green when CI defines "
            "the variable but production does not.",
            derived_from=[f"deploy:{state['deploy']['failed']['id']}", f"commit:{cand['sha']}"],
            agent_id="planner", run_id=run_id, task_id="outcome", tags=["startup-failure", "ci-green-prod-red"])
        mem["lesson_id"] = lesson["id"]
        trace.log("hmem", "remember_lesson", memory_id=lesson["id"], layer=lesson["layer"],
                  confidence=lesson["confidence"], access_count=lesson["accessCount"])
    ex = explain(result, getattr(memory, "generator", None))
    result["explanation"] = ex
    trace.log("explainer", "explain", mode=ex["mode"], model=ex["model"], provider=ex["provider"],
              cited_evidence=sorted({c for p in ex["content"]["points"] + [ex["content"]["fix"]] for c in p["cites"]}),
              facts_available=ex["evidence_count"], rejected=ex["rejected"])
    memory.close()
    result["memory"] = mem
    trace.log("planner", "finish", status=status, confidence=result["confidence"], rounds=rounds,
              culprit=cand["sha"] if cand else None, memory_fast_path=state["fast_path"])
    return result
