import sys
import unittest

sys.path.insert(0, ".")
from scripts.benchmark import benchmark  # noqa: E402


class BenchmarkTests(unittest.TestCase):
    def test_no_false_confirmations_on_random_incidents(self):
        rows = benchmark(40)
        self.assertEqual(sum(r["false_confirm"] or r["wrong_culprit"] for r in rows), 0)
        self.assertEqual(sum(r["ok"] for r in rows), len(rows))


if __name__ == "__main__":
    unittest.main()
