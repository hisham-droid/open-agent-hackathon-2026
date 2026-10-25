"""MemoryRetrievalService: hybrid ranking and a structured reinjection payload with trace metadata."""
import json
import math
import pathlib
import re
import time

from .embedding import cosine, embed, words
from .store import TOKEN_RE, now_ts

LAYER_WEIGHT = {"long_term": 1.0, "working": 0.9, "short_term": 0.8}
THRESHOLD = 0.35
TOP_N = 5
FAILURE_WORDS = ("deploy", "failed", "error", "startup", "crash", "exception", "abort")


def _overlap(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a) if a else 0.0


def score_memory(rec, q, now):
    qwords, qvec = q["words"], q["vec"]
    mwords = words(rec["content"])
    tag_words = [w for t in rec.get("tags", []) for w in words(t.replace(":", " "))]
    parts = {
        "semantic": cosine(qvec, rec["embedding"]),
        "keyword": _overlap(qwords, mwords),
        "tag": _overlap(tag_words, qwords),
        "domain": 1.0 if rec.get("domain") == q["domain"] else 0.0,
        "entity": _overlap(q["entities"], rec.get("entities", [])),
    }
    base = (0.30 * parts["semantic"] + 0.35 * parts["keyword"] + 0.10 * parts["tag"]
            + 0.10 * parts["domain"] + 0.15 * parts["entity"])
    base *= LAYER_WEIGHT[rec["layer"]]
    age_days = max(0.0, (now - rec["lastAccessed"]) / 86400.0)
    recency = 0.05 * math.exp(-age_days / 7.0)
    scope = 0.05 if q.get("run_id") and rec.get("runId") == q["run_id"] else 0.0
    score = base + recency + scope
    if any(o.get("supersedes") == rec["id"] for o in q["all"]):
        score *= 0.3
        parts["superseded_penalty"] = True
    parts.update({"layer_weight": LAYER_WEIGHT[rec["layer"]], "recency": round(recency, 4), "agent_scope": scope})
    # confidence scales the final score so memories that proved wrong rank lower next time
    score *= (0.5 + 0.5 * rec.get("confidence", 0.5))
    return max(0.0, min(1.0, score)), {k: (round(v, 3) if isinstance(v, float) else v) for k, v in parts.items()}


def retrieve(store, query, agent_id, run_id, trace_path=None, top_n=TOP_N, threshold=THRESHOLD):
    now = now_ts()
    recs = store.all()
    q = {"words": words(query), "vec": embed(query), "entities": sorted(set(TOKEN_RE.findall(query))),
         "domain": "incident-investigation" if any(w in query.lower() for w in FAILURE_WORDS) else "general",
         "run_id": run_id, "all": recs}
    scored = []
    for rec in recs:
        s, why = score_memory(rec, q, now)
        if s >= threshold:
            scored.append((s, rec, why))
    scored.sort(key=lambda x: -x[0])
    top = scored[:top_n]
    strategy = "minimal" if len(top) <= 1 else ("task_focused" if len(top) <= 3 else "comprehensive")
    payload = {
        "strategy": strategy,
        "retrievalReason": f"hybrid ranking for agent '{agent_id}' in run '{run_id}'; domain={q['domain']}; "
                           f"{len(scored)} of {len(recs)} memories above threshold {threshold}",
        "threshold": threshold, "considered": len(recs), "query": query,
        "memories": [{"id": r["id"], "content": r["content"], "type": r["type"], "layer": r["layer"],
                      "score": round(s, 3), "confidence": r["confidence"], "tags": r["tags"],
                      "derivedFrom": r.get("derivedFrom", []), "why": why} for s, r, why in top],
    }
    for s, r, _ in top:
        r["accessCount"] += 1
        r["lastAccessed"] = now
        store.ledger.log(r["id"], "read", agent_id, {"score": round(s, 3), "runId": run_id})
    if trace_path:
        p = pathlib.Path(trace_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "agentId": agent_id, "runId": run_id,
                                "payload": payload}) + "\n")
    return payload
