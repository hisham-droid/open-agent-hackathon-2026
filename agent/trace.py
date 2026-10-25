"""Append-only JSONL trace. Every agent step is logged as it happens."""
import json
import pathlib
import time


class Trace:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")
        self.seq = 0

    def log(self, agent, action, **fields):
        self.seq += 1
        rec = {"seq": self.seq, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "agent": agent, "action": action, **fields}
        with self.path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        return rec
