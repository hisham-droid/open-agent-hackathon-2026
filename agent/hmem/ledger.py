"""Append-only trust ledger (JSONL). Every memory mutation and read is auditable evidence."""
import json
import pathlib
import time


class TrustLedger:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, memory_id, action, actor, details=None, previous=None, new=None):
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "memoryId": memory_id, "action": action,
               "actor": actor, "details": details or {}}
        if previous is not None:
            rec["previousState"] = previous
        if new is not None:
            rec["newState"] = new
        with self.path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        return rec

    def entries(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def stats(self):
        out = {}
        for e in self.entries():
            out[e["action"]] = out.get(e["action"], 0) + 1
        return out
