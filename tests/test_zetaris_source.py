"""Offline test: a fake Zetaris runner returns rows shaped like the real views, built from sample_data."""
import json
import pathlib
import tempfile
import unittest

from agent.main import run
from agent.zetaris_source import QUERIES, ZetarisDataset

SAMPLE = pathlib.Path(__file__).resolve().parent.parent / "sample_data"


def fake_runner():
    j = lambda n: json.loads((SAMPLE / n).read_text())
    commits, deploys, ci = j("commits.json"), j("deploys.json"), j("ci_runs.json")
    logs = [json.loads(l) for l in (SAMPLE / "logs.jsonl").read_text().splitlines() if l.strip()]
    env = j("prod_env.json")
    table = {
        QUERIES["commits"]: [[c["sha"], c["ts"], c["author"], c["message"], ",".join(c["files"]), c["diff"]] for c in commits],
        QUERIES["deploys"]: [[d["id"], d["sha"], d["ts"], d["env"], d["status"]] for d in deploys],
        QUERIES["ci_runs"]: [[r["run_id"], r["sha"], r["ts"], r["status"], ",".join(r["env_keys"])] for r in ci],
        QUERIES["logs"]: [[i, l["ts"], l["deploy_id"], l["level"], l["service"], l["msg"]] for i, l in enumerate(logs, 1)],
        QUERIES["prod_env"]: [[env["deploy_id"], k, v] for k, v in env["keys"].items()],
    }
    return lambda sql: table[sql]


class ZetarisSourceTests(unittest.TestCase):
    def test_dataset_is_built_only_from_sql_results(self):
        ds = ZetarisDataset(runner=fake_runner())
        self.assertEqual(ds.source, "zetaris")
        self.assertEqual(ds.queries, list(QUERIES.values()))
        self.assertEqual(ds.row_counts, {"commits": 5, "deploys": 4, "ci_runs": 5, "logs": 10, "prod_env": 5})
        self.assertEqual(ds.commit("9f8e7d6")["files"], ["config/settings.py", ".github/workflows/ci.yml"])

    def test_agent_reaches_same_conclusion_through_zetaris(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = ZetarisDataset(runner=fake_runner())
            r, _ = run("Why did the latest production deploy fail?", None, pathlib.Path(tmp) / "out",
                       pathlib.Path(tmp) / "mem", dataset=ds)
            trace = [json.loads(l) for l in (pathlib.Path(tmp) / "out" / "trace.jsonl").read_text().splitlines()]
        self.assertEqual(r["status"], "confirmed")
        self.assertEqual(r["culprit"]["sha"], "9f8e7d6")
        load = next(t for t in trace if t["agent"] == "data" and t["action"] == "load")
        self.assertEqual(load["source"], "zetaris")
        self.assertEqual(len(load["sql"]), 5)


if __name__ == "__main__":
    unittest.main()
