"""H-MEM: hierarchical, auditable agent memory (Python implementation of the Meterless H-MEM Agent Engine).

Implemented services: MemoryStoreService, MemoryRetrievalService, MemoryMiningService (with no-model fallback),
TrustLedgerService (JSONL), feedback adaptation, warm start with forgetting curve.
Not implemented: dreaming, sleep/consolidation, conflict resolution.
"""
import pathlib

from . import mining, retrieval
from .ledger import TrustLedger
from .store import MemoryStore, now_ts


class HMem:
    backend = "h-mem (python implementation of the Meterless H-MEM Agent Engine)"

    def __init__(self, base_dir, log_dir=None, generator=None):
        base = pathlib.Path(base_dir)
        self.log_dir = pathlib.Path(log_dir) if log_dir else base / "logs"
        self.ledger = TrustLedger(self.log_dir / "hmem_audit.jsonl")
        self.retrieval_trace = self.log_dir / "hmem_retrieval_trace.jsonl"
        self.retrieval_trace.parent.mkdir(parents=True, exist_ok=True)
        self.retrieval_trace.write_text("")
        self.store = MemoryStore(base, self.ledger)
        self.generator = generator

    def start_run(self, run_id):
        return self.store.hydrate(actor=f"run:{run_id}")

    def mine(self, event, agent_id, run_id, task_id):
        return mining.mine(self.store, event, agent_id, run_id, task_id, self.generator)

    def retrieve(self, query, agent_id, run_id):
        return retrieval.retrieve(self.store, query, agent_id, run_id, self.retrieval_trace)

    def feedback(self, memory_id, verdict, actor, reason=""):
        return self.store.feedback(memory_id, verdict, actor, reason)

    def remember_lesson(self, failure_class, content, derived_from, agent_id, run_id, task_id, tags):
        rec = {"id": f"lesson:{failure_class}", "content": content, "type": "procedural", "layer": "working",
               "tags": [f"failure-class:{failure_class}"] + tags, "source": f"{agent_id}:outcome",
               "confidence": 0.6, "derivedFrom": derived_from, "agentId": agent_id, "runId": run_id, "taskId": task_id}
        mem = self.store.upsert(rec, actor=agent_id)
        # validated knowledge survives across runs
        self.store.promote(mem["id"], "long_term", actor=agent_id)
        return mem

    def close(self):
        self.store.persist()
