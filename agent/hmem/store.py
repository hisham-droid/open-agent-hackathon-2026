"""MemoryStoreService: tiered persistence (short_term in process, working and long_term on disk), enrichment,
warm start with forgetting curve, and feedback adaptation. Every mutation goes through the trust ledger."""
import json
import math
import pathlib
import re
import time

from .embedding import embed

TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
SHA_RE = re.compile(r"\b[0-9a-f]{7}\b")
HALF_LIFE_DAYS = 14.0


def now_ts():
    return time.time()


def enrich(rec):
    text = rec["content"]
    rec.setdefault("entities", sorted(set(TOKEN_RE.findall(text)) | set(SHA_RE.findall(text)))[:10])
    classes = [t.split(":", 1)[1] for t in rec.get("tags", []) if t.startswith("failure-class:")]
    rec.setdefault("domain", "incident-investigation" if (classes or any(
        w in text.lower() for w in ("deploy", "failed", "error", "startup", "crash"))) else "general")
    rec.setdefault("namespace", f"investigation/{classes[0]}" if classes else f"{rec['domain']}/notes")
    rec["embedding"] = embed(text + " " + " ".join(rec.get("tags", [])))
    return rec


class MemoryStore:
    def __init__(self, base_dir, ledger):
        self.dir = pathlib.Path(base_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.short = {}
        self.working = self._load("working.json")
        self.long = self._load("long_term.json")

    def _load(self, name):
        p = self.dir / name
        try:
            return {r["id"]: r for r in json.loads(p.read_text())} if p.exists() else {}
        except (json.JSONDecodeError, KeyError):
            return {}

    def persist(self):
        (self.dir / "working.json").write_text(json.dumps(list(self.working.values()), indent=1))
        (self.dir / "long_term.json").write_text(json.dumps(list(self.long.values()), indent=1))

    def tier(self, layer):
        return {"short_term": self.short, "working": self.working, "long_term": self.long}[layer]

    def all(self):
        return list(self.long.values()) + list(self.working.values()) + list(self.short.values())

    def get(self, mid):
        for t in (self.short, self.working, self.long):
            if mid in t:
                return t[mid]
        return None

    def hydrate(self, actor="store"):
        """Warm start: load durable tiers and apply the forgetting curve to non-long-term records."""
        decayed = 0
        for rec in self.working.values():
            age_days = (now_ts() - rec["lastAccessed"]) / 86400.0
            factor = 0.5 ** (age_days / HALF_LIFE_DAYS)
            if factor < 0.999:
                rec["confidence"] = round(rec["confidence"] * factor, 4)
                decayed += 1
        counts = {"long_term": len(self.long), "working": len(self.working), "decayed": decayed}
        self.ledger.log("-", "hydrate", actor, counts)
        return counts

    def upsert(self, rec, actor):
        """Create, or reinforce when an id already exists (dedupe by id)."""
        rec = enrich(dict(rec))
        existing = self.get(rec["id"])
        if existing is not None:
            prev = {k: existing[k] for k in ("confidence", "accessCount", "layer")}
            existing["confidence"] = round(min(1.0, existing["confidence"] + 0.05), 4)
            existing["accessCount"] += 1
            existing["lastAccessed"] = now_ts()
            existing["derivedFrom"] = sorted(set(existing.get("derivedFrom", [])) | set(rec.get("derivedFrom", [])))
            self.ledger.log(existing["id"], "update", actor, {"reason": "reinforced by new matching outcome"},
                            previous=prev, new={k: existing[k] for k in prev})
            return existing
        rec.setdefault("timestamp", now_ts())
        rec.setdefault("lastAccessed", rec["timestamp"])
        rec.setdefault("accessCount", 0)
        rec.setdefault("confidence", 0.5)
        rec.setdefault("relatedTo", [])
        rec.setdefault("supersedes", None)
        rec.setdefault("derivedFrom", [])
        self.tier(rec["layer"])[rec["id"]] = rec
        self.ledger.log(rec["id"], "create", actor, {"layer": rec["layer"], "type": rec["type"],
                                                      "agentId": rec.get("agentId"), "runId": rec.get("runId"),
                                                      "taskId": rec.get("taskId"), "tags": rec.get("tags", [])})
        return rec

    def promote(self, mid, to_layer, actor):
        rec = self.get(mid)
        if rec is None or rec["layer"] == to_layer:
            return rec
        old = rec["layer"]
        self.tier(old).pop(mid, None)
        rec["layer"] = to_layer
        self.tier(to_layer)[mid] = rec
        self.ledger.log(mid, "promote", actor, {"from": old, "to": to_layer})
        return rec

    def feedback(self, mid, verdict, actor, reason=""):
        """Event-driven feedback adaptation: helpful / not_helpful / wrong."""
        rec = self.get(mid)
        if rec is None:
            return None
        prev = {"confidence": rec["confidence"], "accessCount": rec["accessCount"], "tags": list(rec["tags"])}
        if verdict == "helpful":
            rec["accessCount"] += 1
            rec["confidence"] = round(min(1.0, rec["confidence"] + 0.1), 4)
        elif verdict == "not_helpful":
            rec["confidence"] = round(max(0.0, rec["confidence"] - 0.05), 4)
        elif verdict == "wrong":
            rec["confidence"] = round(max(0.0, rec["confidence"] - 0.25), 4)
            if "review" not in rec["tags"]:
                rec["tags"].append("review")
        else:
            raise ValueError(f"unknown feedback verdict: {verdict}")
        self.ledger.log(mid, f"feedback:{verdict}", actor, {"reason": reason}, previous=prev,
                        new={"confidence": rec["confidence"], "accessCount": rec["accessCount"], "tags": list(rec["tags"])})
        return rec
