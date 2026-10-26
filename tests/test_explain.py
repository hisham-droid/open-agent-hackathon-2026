import json
import sys
import tempfile
import unittest

sys.path.insert(0, ".")
from scripts.evaluate import evaluate  # noqa: E402
from agent.explain import catalog, explain  # noqa: E402
from agent.main import run  # noqa: E402


def result():
    with tempfile.TemporaryDirectory() as tmp:
        r, report = run("why", "sample_data", tmp + "/o", tmp + "/m")
    return r, report


class Gen:
    last_model = "nvidia/test-model"

    def __init__(self, out):
        self.out = out

    def __call__(self, prompt):
        return self.out if isinstance(self.out, str) else json.dumps(self.out)


GOOD = {"summary": "Commit 9f8e7d6 made DATABASE_POOL_SIZE required but production lacks it.",
        "points": [{"text": "The first error was a missing DATABASE_POOL_SIZE.", "cites": ["log:d-102:7"]},
                   {"text": "Production does not define the setting.", "cites": ["env:d-102"]}],
        "fix": {"text": "Add DATABASE_POOL_SIZE to production.", "cites": ["env:d-102", "commit:9f8e7d6"]}}


class ExplainTests(unittest.TestCase):
    def test_template_when_no_model(self):
        r, report = result()
        self.assertEqual(r["explanation"]["mode"], "template")
        self.assertIn("## In plain English", report)

    def test_accepts_grounded_model_output_and_names_model(self):
        r, _ = result()
        ex = explain(r, Gen(GOOD))
        self.assertEqual(ex["mode"], "model")
        self.assertEqual(ex["model"], "nvidia/test-model")

    def test_rejects_unknown_evidence_id(self):
        r, _ = result()
        bad = json.loads(json.dumps(GOOD)); bad["points"][0]["cites"] = ["log:d-999:1"]
        ex = explain(r, Gen(bad))
        self.assertEqual(ex["mode"], "template"); self.assertIn("unknown evidence", ex["rejected"])

    def test_rejects_invented_commit_or_setting(self):
        r, _ = result()
        for text in ("Commit abc1234 broke it.", "The REDIS_URL setting is wrong."):
            bad = json.loads(json.dumps(GOOD)); bad["points"][1]["text"] = text
            self.assertEqual(explain(r, Gen(bad))["mode"], "template", text)

    def test_rejects_garbage_and_uncited(self):
        r, _ = result()
        self.assertEqual(explain(r, Gen("not json"))["mode"], "template")
        bad = json.loads(json.dumps(GOOD)); bad["points"][0]["cites"] = []
        self.assertEqual(explain(r, Gen(bad))["mode"], "template")

    def test_explanation_is_logged_in_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            run("why", "sample_data", tmp + "/o", tmp + "/m", generator=Gen(GOOD))
            steps = [json.loads(l) for l in open(tmp + "/o/trace.jsonl")]
        e = next(s for s in steps if s["agent"] == "explainer")
        self.assertEqual(e["model"], "nvidia/test-model")

    def test_inconclusive_cannot_claim_a_cause(self):
        from scripts import evaluate as ev
        with tempfile.TemporaryDirectory() as tmp:
            d = ev.build("o", ev.infrastructure_outage, "sample_data", tmp + "/d")
            r, _ = run("why", d, tmp + "/o", tmp + "/m")
        bad = {"summary": "The root cause is the database.", "points": GOOD["points"][:1] * 2,
               "fix": {"text": "x", "cites": [list(catalog(r))[0]]}}
        bad["points"] = [{"text": "Confirmed outage.", "cites": [list(catalog(r))[0]]}] * 2
        self.assertEqual(explain(r, Gen(bad))["mode"], "template")


class EvaluationTests(unittest.TestCase):
    def test_all_scenarios_reach_the_right_verdict(self):
        rows = evaluate()
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(all(r["ok"] for r in rows), rows)


if __name__ == "__main__":
    unittest.main()
