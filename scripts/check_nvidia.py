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
import urllib.error  # noqa: E402

SKIP = ("embed", "guard", "safety", "parse", "reward", "rerank", "clip", "vl", "reasoning")
wanted = os.environ.get("NVIDIA_MODEL")
candidates = ([wanted] if wanted else []) + [m for m in nemo if not any(s in m for s in SKIP)]
candidates += [m for m in models if m not in candidates and any(k in m for k in ("llama-3", "mistral", "qwen")) and not any(s in m for s in SKIP)][:12]
working = []
for model in candidates:
    try:
        reply = NemotronGenerator(key, model, timeout=40)("Reply with a strict JSON array of two short strings about CI. Nothing else.")
        print(f"WORKS: {model} -> {reply[:80]!r}")
        working.append(model)
        if len(working) >= 2:
            break
    except urllib.error.HTTPError as e:
        print(f"failed: {model}: HTTP {e.code} {e.read()[:160]!r}")
    except Exception as e:
        print(f"failed: {model}: {e}")
if not working:
    sys.exit("no chat model worked")
print("\nAdd this line to .env:  NVIDIA_MODEL=" + working[0])
