"""Specialists: each one reads exactly one kind of evidence and returns facts with evidence ids."""
import re

TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
DEP_RE = re.compile(r"(?:No module named|cannot import name '[^']+' from) '([A-Za-z][A-Za-z0-9_.\-]*)'")
QUOTED_RE = re.compile(r"'[^']*'")
ERROR_LEVELS = ("ERROR", "FATAL")


def tokens_in(text):
    """Settings (UPPER_SNAKE names) and packages (named in import errors) that an error message points at."""
    return sorted(set(TOKEN_RE.findall(text)) | set(DEP_RE.findall(text)))


def shape_of(msg):
    """The failure's shape with this incident's names removed, so lessons transfer between incidents."""
    return QUOTED_RE.sub("''", TOKEN_RE.sub("", msg))


class DeploySpecialist:
    name = "deploy"

    def locate_failure(self, ds):
        failed = [d for d in ds.deploys if d["env"] == "production" and d["status"] == "failed"]
        if not failed:
            return None
        bad = max(failed, key=lambda d: d["ts"])
        good = [d for d in ds.deploys if d["env"] == "production"
                and d["status"] == "success" and d["ts"] < bad["ts"]]
        last_good = max(good, key=lambda d: d["ts"]) if good else None
        shas = [c["sha"] for c in ds.commits]
        hi = shas.index(bad["sha"])
        lo = shas.index(last_good["sha"]) if last_good else -1
        return {"failed": bad, "last_good": last_good, "window": shas[lo + 1:hi + 1],
                "evidence": [f"deploy:{bad['id']}"] + ([f"deploy:{last_good['id']}"] if last_good else [])}

    def check_env(self, ds, tokens, required=None):
        """Does production have what the suspect commit needs? Settings must be defined; packages must be at the version it pins."""
        required = required or {}
        keys, installed = set(ds.prod_env["keys"]), ds.prod_env.get("packages", {})
        missing, present, notes = [], [], []
        for t in tokens:
            if required.get(t):
                have = installed.get(t)
                if have != required[t]:
                    missing.append(t)
                    notes.append(f"{t} is {have or 'not installed'} in production while the commit needs {required[t]}")
                else:
                    present.append(t)
            elif t in keys:
                present.append(t)
            else:
                missing.append(t)
                notes.append(f"{t} is not set in production")
        kind = "package" if any(required.get(t) for t in tokens) else "setting"
        return {"missing": missing, "present": present, "kind": kind, "notes": notes,
                "evidence": [f"env:{ds.prod_env['deploy_id']}"]}


class LogSpecialist:
    name = "logs"

    def analyze(self, ds, deploy_id):
        lines = [(i, l) for i, l in enumerate(ds.logs, 1) if l["deploy_id"] == deploy_id]
        errors = sorted([(i, l) for i, l in lines if l["level"] in ERROR_LEVELS], key=lambda x: (x[1]["ts"], x[0]))
        if not errors:
            return {"primary": None, "tokens": [], "warn_services": [], "evidence": []}
        i, primary = errors[0]
        return {"primary": primary, "primary_id": f"log:{deploy_id}:{i}",
                "tokens": tokens_in(primary["msg"]),
                "warn_services": sorted({l["service"] for _, l in lines if l["level"] == "WARN"}),
                "error_count": len(errors), "evidence": [f"log:{deploy_id}:{i}"]}


class CommitSpecialist:
    name = "commits"

    def analyze(self, ds, window, tokens):
        out = []
        for sha in window:
            c = ds.commit(sha)
            added = "\n".join(l for l in c["diff"].splitlines() if l.startswith("+") and not l.startswith("+++"))
            removed = "\n".join(l for l in c["diff"].splitlines() if l.startswith("-") and not l.startswith("---"))
            introduced = [t for t in tokens if t in added]
            touched = [t for t in tokens if t in removed or t in c["message"]]
            required = {}
            for tok in introduced:
                m = re.search(rf"^\+\s*{re.escape(tok)}\s*(?:==|~=)\s*([\w.\-]+)", added, re.M)
                if m:
                    required[tok] = m.group(1)
            score = 2 * len(introduced) + len(set(touched) - set(introduced))
            out.append({"sha": sha, "message": c["message"], "files": c["files"],
                        "introduced": introduced, "required": required, "mentioned": touched, "score": score,
                        "evidence": [f"commit:{sha}"]})
        return sorted(out, key=lambda x: -x["score"])


class CISpecialist:
    name = "ci"

    def analyze(self, ds, sha, tokens, required=None):
        required = required or {}
        run = next((r for r in ds.ci_runs if r["sha"] == sha), None)
        if run is None:
            return {"run": None, "green": False, "defines_token": False, "evidence": []}
        pk = run.get("packages", {})
        has = lambda t: (pk.get(t) == required[t]) if required.get(t) else (t in run["env_keys"])
        return {"run": run["run_id"], "green": run["status"] == "passed",
                "defines_token": all(has(t) for t in tokens) if tokens else False,
                "evidence": [f"ci:{run['run_id']}"]}
