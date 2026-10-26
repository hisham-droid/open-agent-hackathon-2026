"""Meterless Nightshift client: the agent's AI provider. Nightshift runs on the user's machine and exposes an
OpenAI-compatible endpoint; it routes to hosted NVIDIA Nemotron models (the NVIDIA key lives in Nightshift's
Providers tab, never in this project). Used as the H-MEM mining model. Any failure raises and mining falls back
to plain summaries, so the agent never depends on it. Every request records which model handled it."""
import json
import os
import urllib.request

DEFAULT_BASE_URL = "http://localhost:8088/v1"
DEFAULT_MODEL = "meterless/auto"


class NightshiftGenerator:
    def __init__(self, base_url, token, model=None, timeout=120, opener=None):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.token = token
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout
        self.opener = opener or urllib.request.urlopen
        self.last_model = None   # model that actually answered the latest request
        self.calls = 0

    @classmethod
    def from_env(cls):
        token = os.environ.get("METERLESS_RUNTIME_TOKEN", "").strip()
        if not token or os.environ.get("DISABLE_NIGHTSHIFT", "").lower() in ("1", "true"):
            return None
        return cls(os.environ.get("METERLESS_BASE_URL") or None, token, os.environ.get("METERLESS_MODEL") or None)

    def __call__(self, prompt):
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": 2000,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        with self.opener(req, timeout=self.timeout) as resp:
            data = json.load(resp)
        self.calls += 1
        self.last_model = data.get("model") or self.model
        text = data["choices"][0]["message"].get("content")
        if not text:
            raise ValueError("empty completion")
        return text
