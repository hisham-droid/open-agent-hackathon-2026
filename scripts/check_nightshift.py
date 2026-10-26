"""Live check for Meterless Nightshift. Run on your machine with Nightshift open: python3 scripts/check_nightshift.py"""
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import os  # noqa: E402
from agent.env import load_env  # noqa: E402
from agent.nightshift import DEFAULT_BASE_URL, NightshiftGenerator  # noqa: E402

load_env()
base = os.environ.get("METERLESS_BASE_URL") or DEFAULT_BASE_URL
token = os.environ.get("METERLESS_RUNTIME_TOKEN", "")
if not token:
    sys.exit("METERLESS_RUNTIME_TOKEN is empty in .env")
req = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {token}"})
try:
    models = [m["id"] for m in json.load(urllib.request.urlopen(req, timeout=30))["data"]]
except Exception as e:
    sys.exit(f"Could not reach Nightshift at {base}: {e}")
nemo = [m for m in models if "nemotron" in m.lower()]
print(f"Nightshift reachable at {base}: {len(models)} models, {len(nemo)} Nemotron")
print("\n".join("  " + m for m in nemo[:20]))
for model in ([os.environ.get("METERLESS_MODEL")] if os.environ.get("METERLESS_MODEL") else []) + nemo[:6]:
    g = NightshiftGenerator(base, token, model)
    try:
        reply = g("Reply with a strict JSON array of two short strings about CI. Nothing else.")
        print(f"WORKS: requested={model} answered_by={g.last_model}\nreply: {reply[:120]}")
        print(f"\nAdd to .env:  METERLESS_MODEL={model}")
        break
    except Exception as e:
        print(f"failed: {model}: {e}")
else:
    sys.exit("no model worked")
