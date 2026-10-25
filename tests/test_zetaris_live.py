"""Live test against a running Zetaris. Opt-in only, so normal test runs never need Zetaris.

Run on the machine where Zetaris is running:
    RUN_LIVE_ZETARIS=1 python3 -m unittest tests.test_zetaris_live -v
"""
import os
import pathlib
import tempfile
import unittest

from agent.env import load_env
from agent.main import run

load_env()


@unittest.skipUnless(os.environ.get("RUN_LIVE_ZETARIS") == "1" and os.environ.get("ZETARIS_API_KEY"),
                     "set RUN_LIVE_ZETARIS=1 and ZETARIS_API_KEY to run")
class ZetarisLiveTests(unittest.TestCase):
    def test_agent_investigates_live_zetaris_data(self):
        from agent.zetaris_source import ZetarisDataset
        ds = ZetarisDataset()
        self.assertEqual(ds.row_counts["commits"], 5)
        with tempfile.TemporaryDirectory() as tmp:
            r, _ = run("Why did the latest production deploy fail?", None, pathlib.Path(tmp) / "out",
                       pathlib.Path(tmp) / "mem.json", dataset=ds)
        self.assertEqual(r["status"], "confirmed")
        self.assertEqual(r["culprit"]["sha"], "9f8e7d6")


if __name__ == "__main__":
    unittest.main()
