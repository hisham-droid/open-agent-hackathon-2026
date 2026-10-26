import json
import sys
import tempfile
import unittest

sys.path.insert(0, ".")
from agent.ask import ask  # noqa: E402
from agent.main import run  # noqa: E402


class Gen:
    last_model = "m"

    def __init__(self, out):
        self.out = out

    def __call__(self, p):
        return json.dumps(self.out)


def res():
    with tempfile.TemporaryDirectory() as tmp:
        return run("why", "sample_data", tmp + "/o", tmp + "/m")[0]


class AskTests(unittest.TestCase):
    def test_template_explains_ruled_out_commit(self):
        a = ask("Why did you rule out 77bb88c?", res())
        self.assertIn("77bb88c", a["answer"]); self.assertEqual(a["cites"], ["commit:77bb88c"])

    def test_model_answer_accepted_when_grounded(self):
        a = ask("how sure are you", res(), Gen({"answer": "All four checks passed.", "cites": ["verdict"]}))
        self.assertEqual(a["mode"], "model")

    def test_model_answer_rejected_when_invented_or_uncited(self):
        for bad in ({"answer": "Commit abc1234 did it.", "cites": ["verdict"]},
                    {"answer": "Fine.", "cites": ["log:nope"]}, {"answer": "Fine.", "cites": []}):
            self.assertEqual(ask("why", res(), Gen(bad))["mode"], "template")


if __name__ == "__main__":
    unittest.main()
