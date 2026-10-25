import json
import pathlib
import sys
import tempfile
import unittest

from agent.hmem import HMem
from agent.hmem.mining import parse_json_array
from agent.main import run

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from make_variant import make  # noqa: E402

Q = "Why did the latest production deploy fail?"
LESSON = "lesson:required-config-missing-in-prod"


def session(tmp, data, name, run_id):
    return run(Q, data, pathlib.Path(tmp) / name, pathlib.Path(tmp) / "mem", run_id=run_id)


def jl(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


class HMemTests(unittest.TestCase):
    def test_cold_start_then_lesson_is_saved_to_long_term(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, report = session(tmp, ROOT / "sample_data", "o1", "s1")
            saved = json.loads((pathlib.Path(tmp) / "mem" / "long_term.json").read_text())
        self.assertFalse(r["memory"]["fast_path"])
        self.assertEqual(r["memory"]["lesson_id"], LESSON)
        self.assertIn(LESSON, json.dumps(saved))
        self.assertIn("cold start", report)

    def test_lesson_carries_over_to_a_different_incident(self):
        with tempfile.TemporaryDirectory() as tmp:
            session(tmp, ROOT / "sample_data", "o1", "s1")
            variant = make(pathlib.Path(tmp) / "variant")
            r, report = session(tmp, variant, "o2", "s2")
            trace = jl(pathlib.Path(tmp) / "o2" / "trace.jsonl")
        self.assertEqual(r["status"], "confirmed")
        self.assertEqual(r["culprit"]["sha"], "3c4d5e6")  # a different commit than session 1
        self.assertTrue(r["memory"]["fast_path"])
        self.assertEqual(r["memory"]["feedback"]["verdict"], "helpful")
        self.assertTrue(any(t["action"] == "plan_from_memory" for t in trace))
        # the evaluator still verified everything from evidence
        self.assertTrue(all(v == "pass" for v in r["checks"].values()))
        self.assertIn("Memory (H-MEM)", report)

    def test_confidence_grows_with_helpful_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            session(tmp, ROOT / "sample_data", "o1", "s1")
            variant = make(pathlib.Path(tmp) / "variant")
            r2, _ = session(tmp, variant, "o2", "s2")
            r3, _ = session(tmp, variant, "o3", "s3")
        self.assertGreater(r3["memory"]["feedback"]["confidence_after"], r2["memory"]["feedback"]["confidence_after"])

    def test_memory_does_not_skip_verification_when_evidence_contradicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            session(tmp, ROOT / "sample_data", "o1", "s1")
            variant = make(pathlib.Path(tmp) / "variant")
            envf = variant / "prod_env.json"
            raw = json.loads(envf.read_text())
            raw["keys"]["REDIS_TIMEOUT_SECONDS"] = "30"  # production now defines the variable
            envf.write_text(json.dumps(raw))
            r, _ = session(tmp, variant, "o2", "s2")
        self.assertNotEqual(r["status"], "confirmed")
        self.assertTrue(r["memory"]["fast_path"])  # memory suggested the shortcut...
        self.assertEqual(r["memory"]["feedback"]["verdict"], "wrong")  # ...but evidence rejected it

    def test_audit_ledger_records_reads_and_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            session(tmp, ROOT / "sample_data", "o1", "s1")
            variant = make(pathlib.Path(tmp) / "variant")
            session(tmp, variant, "o2", "s2")
            audit = jl(pathlib.Path(tmp) / "o2" / "logs" / "hmem_audit.jsonl")
            retrieval = jl(pathlib.Path(tmp) / "o2" / "logs" / "hmem_retrieval_trace.jsonl")
        ops = {a["action"] for a in audit}
        self.assertTrue({"read", "create", "update", "hydrate"} <= ops, ops)
        self.assertTrue(any(o.startswith("feedback:") for o in ops), ops)
        self.assertTrue(retrieval)

    def test_unrelated_query_retrieves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            session(tmp, ROOT / "sample_data", "o1", "s1")
            mem = HMem(pathlib.Path(tmp) / "mem", log_dir=pathlib.Path(tmp) / "l")
            mem.start_run("x")
            payload = mem.retrieve("quarterly marketing budget for the summer picnic", "planner", "x")
        self.assertEqual(payload["memories"], [])

    def test_mining_fallback_and_model_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ev = {"kind": "tool_result", "summary": "Production env missing FOO_BAR"}
            fallback = HMem(pathlib.Path(tmp) / "a", log_dir=pathlib.Path(tmp) / "la")
            made, mode = fallback.mine(ev, "deploy", "r", "t")
            self.assertEqual(mode, "fallback")
            self.assertEqual(made[0]["layer"], "short_term")
            model = HMem(pathlib.Path(tmp) / "b", log_dir=pathlib.Path(tmp) / "lb",
                         generator=lambda p: '```json\n["Prod lacks FOO_BAR", "CI defines FOO_BAR"]\n```')
            made, mode = model.mine(ev, "deploy", "r", "t")
            self.assertEqual(mode, "model")
            self.assertEqual(len(made), 2)
            broken = HMem(pathlib.Path(tmp) / "c", log_dir=pathlib.Path(tmp) / "lc", generator=lambda p: "not json")
            self.assertEqual(broken.mine(ev, "deploy", "r", "t")[1], "fallback")

    def test_parse_json_array_tolerates_noise(self):
        self.assertEqual(parse_json_array('Sure! ["a", "b"] done'), ["a", "b"])
        self.assertIsNone(parse_json_array("nothing"))

    def test_wrong_feedback_lowers_confidence_and_flags_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            session(tmp, ROOT / "sample_data", "o1", "s1")
            mem = HMem(pathlib.Path(tmp) / "mem", log_dir=pathlib.Path(tmp) / "l")
            mem.start_run("x")
            before = mem.store.get(LESSON)["confidence"] if hasattr(mem.store, "get") else 0.6
            updated = mem.feedback(LESSON, "wrong", "tester", reason="test")
        self.assertLess(updated["confidence"], before)
        self.assertIn("review", updated["tags"])


if __name__ == "__main__":
    unittest.main()
