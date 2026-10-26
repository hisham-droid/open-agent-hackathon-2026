import sys
import unittest

sys.path.insert(0, ".")
from agent import server  # noqa: E402


class ServerTests(unittest.TestCase):
    def test_scenarios_listed_and_page_exists(self):
        self.assertGreaterEqual(len(server.scenario_list()), 5)
        self.assertIn(b"Build-Failure Detective", (server.WEB / "index.html").read_bytes())

    def test_investigate_returns_result_and_trace(self):
        server.MEM = server.pathlib.Path(__import__("tempfile").mkdtemp())
        d = server.investigate("infrastructure-outage", use_model=False)
        self.assertEqual(d["result"]["status"], "inconclusive")
        self.assertTrue(any(s["agent"] == "explainer" for s in d["trace"]))


if __name__ == "__main__":
    unittest.main()
