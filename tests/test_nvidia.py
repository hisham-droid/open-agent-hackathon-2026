import io
import json
import unittest

from agent.nvidia import NemotronGenerator


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class NvidiaTests(unittest.TestCase):
    def test_request_shape_and_parsing(self):
        seen = {}

        def opener(req, timeout):
            seen["url"], seen["auth"] = req.full_url, req.get_header("Authorization")
            seen["body"] = json.loads(req.data)
            return FakeResp(json.dumps({"choices": [{"message": {"content": '["a"]'}}]}).encode())

        g = NemotronGenerator("k", model="m", opener=opener)
        self.assertEqual(g("hi"), '["a"]')
        self.assertTrue(seen["url"].endswith("/chat/completions"))
        self.assertEqual(seen["auth"], "Bearer k")
        self.assertEqual(seen["body"]["model"], "m")

    def test_from_env_respects_missing_key_and_kill_switch(self):
        import os
        old = dict(os.environ)
        try:
            os.environ.pop("NVIDIA_API_KEY", None)
            self.assertIsNone(NemotronGenerator.from_env())
            os.environ["NVIDIA_API_KEY"] = "k"
            self.assertIsNotNone(NemotronGenerator.from_env())
            os.environ["DISABLE_NEMOTRON"] = "1"
            self.assertIsNone(NemotronGenerator.from_env())
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
