"""NVIDIA Nemotron client (OpenAI-compatible chat API). Used as the H-MEM mining generator.
Any failure raises, and the miner falls back to direct summaries, so the agent never depends on it."""
import json
import os
import urllib.request

BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3.5-bolt-e4b"
FALLBACK_MODELS = ["nvidia/nemotron-3-ultra-550b-a55b"]


class NemotronGenerator:
    def __init__(self, api_key, model=None, base_url=None, timeout=30, opener=None):
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.timeout = timeout
        self.opener = opener or urllib.request.urlopen

    @classmethod
    def from_env(cls):
        key = os.environ.get("NVIDIA_API_KEY", "").strip()
        if not key or os.environ.get("DISABLE_NEMOTRON", "").lower() in ("1", "true"):
            return None
        return cls(key, os.environ.get("NVIDIA_MODEL") or None)

    def __call__(self, prompt):
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": 300,
                           "messages": [{"role": "system", "content": "detailed thinking off"},
                                        {"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        with self.opener(req, timeout=self.timeout) as resp:
            text = json.load(resp)["choices"][0]["message"].get("content")
        if not text:
            raise ValueError("empty completion")
        return text
