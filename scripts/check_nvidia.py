"""Live check for the NVIDIA key. Run on your own machine: python3 scripts/check_nvidia.py"""
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.env import load_env  # noqa: E402
from agent.nvidia import BASE_URL, NemotronGenerator  # noqa: E402
import os  # noqa: E402

load_env()
key = os.environ.get("NVIDIA_API_KEY", "")
if not key:
    sys.exit("NVIDIA_API_KEY is empty in .env")
req = urllib.request.Request(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {key}"})
try:
    models = [m["id"] for m in json.load(urllib.request.urlopen(req, timeout=30))["data"]]
except Exception as e:
    sys.exit(f"Could not list models: {e}")
nemo = [m for m in models if "nemotron" in m.lower()]
print(f"key accepted; {len(models)} models, {len(nemo)} Nemotron:")
print("\n".join("  " + m for m in nemo[:25]))
gen = NemotronGenerator.from_env()
print(f"\nusing model: {gen.model}  (override with NVIDIA_MODEL in .env)")
print("reply:", gen('Reply with a strict JSON array of two short strings about CI. Nothing else.'))
