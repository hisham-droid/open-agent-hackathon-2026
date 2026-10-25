import json
import pathlib
import shutil
import tempfile
import unittest

from agent.main import run

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample_data"


def fresh_copy(tmp):
    dst = pathlib.Path(tmp) / "data"
    shutil.copytree(SAMPLE, dst)
    return dst


def go(data, tmp, name="out"):
    return run("Why did the latest production deploy fail?", data, pathlib.Path(tmp) / name, pathlib.Path(tmp) / "mem.json")


class AgentTests(unittest.TestCase):
    def test_finds_planted_root_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, report = go(SAMPLE, tmp)
        self.assertEqual(r["status"], "confirmed")
        self.assertEqual(r["culprit"]["sha"], "9f8e7d6")
        self.assertGreaterEqual(r["confidence"], 0.85)
        self.assertIn("log:d-102:7", report)

    def test_follows_the_data_not_a_hardcoded_answer(self):
        """Move the root-cause change onto a different commit; the agent must follow it."""
        with tempfile.TemporaryDirectory() as tmp:
            data = fresh_copy(tmp)
            commits = json.loads((data / "commits.json").read_text())
            a = next(c for c in commits if c["sha"] == "9f8e7d6")
            b = next(c for c in commits if c["sha"] == "55aa66b")
            for k in ("message", "files", "diff"):
                a[k], b[k] = b[k], a[k]
            (data / "commits.json").write_text(json.dumps(commits))
            r, _ = go(data, tmp)
        self.assertEqual(r["culprit"]["sha"], "55aa66b")

    def test_refuses_to_confirm_when_evidence_contradicts(self):
        """If production already defines the variable, the agent must not claim a confirmed cause."""
        with tempfile.TemporaryDirectory() as tmp:
            data = fresh_copy(tmp)
            env = json.loads((data / "prod_env.json").read_text())
            env["keys"]["DATABASE_POOL_SIZE"] = "20"
            (data / "prod_env.json").write_text(json.dumps(env))
            r, report = go(data, tmp)
        self.assertEqual(r["status"], "inconclusive")
        self.assertLess(r["confidence"], 0.85)
        self.assertIn("Inconclusive", report)

    def test_trace_shows_reject_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            go(SAMPLE, tmp)
            lines = [json.loads(l) for l in (pathlib.Path(tmp) / "out" / "trace.jsonl").read_text().splitlines()]
        reviews = [l for l in lines if l["agent"] == "evaluator"]
        self.assertGreaterEqual(len([r for r in reviews if r["verdict"] == "reject"]), 2)
        self.assertEqual(reviews[-1]["verdict"], "accept")
        self.assertTrue(any(l["action"] == "replan" for l in lines))
        self.assertEqual([l["seq"] for l in lines], list(range(1, len(lines) + 1)))

    def test_memory_recalls_prior_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = go(SAMPLE, tmp, "run1")
            second, report = go(SAMPLE, tmp, "run2")
        self.assertEqual(first["memory_hits"], [])
        self.assertEqual(len(second["memory_hits"]), 1)
        self.assertIn("Seen before", report)


if __name__ == "__main__":
    unittest.main()
