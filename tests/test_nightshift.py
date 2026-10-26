import io
import json
import os
import unittest

from agent.nightshift import NightshiftGenerator


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class NightshiftTests(unittest.TestCase):
    def test_request_shape_and_model_attribution(self):
        seen = {}

        def opener(req, timeout):
            seen["url"], seen["auth"], seen["body"] = req.full_url, req.get_header("Authorization"), json.loads(req.data)
            return FakeResp(json.dumps({"model": "nvidia/nemotron-x", "choices": [{"message": {"content": '["a"]'}}]}).encode())

        g = NightshiftGenerator("http://localhost:8088/v1", "rt-local", model="meterless/auto", opener=opener)
        self.assertEqual(g("hi"), '["a"]')
        self.assertEqual(seen["url"], "http://localhost:8088/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer rt-local")
        self.assertEqual(g.last_model, "nvidia/nemotron-x")  # the model that answered is recorded
        self.assertEqual(g.calls, 1)

    def test_from_env(self):
        old = dict(os.environ)
        try:
            os.environ.pop("METERLESS_RUNTIME_TOKEN", None)
            self.assertIsNone(NightshiftGenerator.from_env())
            os.environ["METERLESS_RUNTIME_TOKEN"] = "t"
            self.assertIsNotNone(NightshiftGenerator.from_env())
            os.environ["DISABLE_NIGHTSHIFT"] = "1"
            self.assertIsNone(NightshiftGenerator.from_env())
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
