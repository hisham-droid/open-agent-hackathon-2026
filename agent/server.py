"""Local web app: pick an incident, watch the agent investigate, read the cited explanation.
Run: python3 -m agent.server   then open http://localhost:8000"""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .ask import ask
from .env import load_env
from .main import ROOT, run
from .nightshift import NightshiftGenerator

WEB = pathlib.Path(__file__).parent / "web"
MEM = ROOT / ".agent_memory_ui"
LOCK = threading.Lock()
LAST = {}
QUESTION = "Why did the latest production deploy fail?"


def live_zetaris():
    return os.environ.get("SAMPLE_MODE", "true").lower() not in ("1", "true", "yes")


def scenario_list():
    items = []
    if live_zetaris():
        items.append({"id": "zetaris", "title": "Live data from Zetaris", "blurb": "Reads commits, deploys, logs and CI through the Zetaris REST API."})
    items += [
        {"id": "planted", "title": "Renamed setting breaks production", "blurb": "CI is green, production is missing the new variable."},
        {"id": "redis-variant", "title": "Same failure, different names", "blurb": "A new incident. Run it after the first to see memory skip steps."},
        {"id": "other-service-secret", "title": "A different commit is the culprit", "blurb": "The email change adds a token production lacks."},
        {"id": "dependency-version-skew", "title": "A package upgrade breaks production", "blurb": "CI installed the new version, production still runs the old one."},
        {"id": "infrastructure-outage", "title": "No code change explains it", "blurb": "The agent should refuse to blame a commit."},
        {"id": "contradicted-by-prod", "title": "The obvious suspect is already fixed", "blurb": "Production defines the variable. The agent should not confirm."},
    ]
    return items


def investigate(sid, use_model=True):
    from scripts.make_variant import make
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        dataset, data = None, ROOT / "sample_data"
        if sid == "zetaris" and live_zetaris():
            from .zetaris_source import ZetarisDataset
            dataset = ZetarisDataset()
        elif sid == "redis-variant":
            data = make(tmp / "data")
        elif sid not in ("planted",):
            if not (ROOT / "scenarios" / sid).is_dir():
                raise ValueError("unknown scenario")
            data = ROOT / "scenarios" / sid
        gen = NightshiftGenerator.from_env() if use_model else None
        result, report = run(QUESTION, data, tmp / "out", MEM, dataset=dataset, run_id=f"ui-{len(os.listdir(MEM)) if MEM.exists() else 0}", generator=gen)
        trace = [json.loads(l) for l in (tmp / "out" / "trace.jsonl").read_text().splitlines()]
        LAST["result"] = result
        return {"result": result, "report": report, "trace": trace}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/scenarios":
            return self._send(200, {"scenarios": scenario_list(), "model_configured": bool(os.environ.get("METERLESS_RUNTIME_TOKEN"))})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/reset":
            with LOCK:
                shutil.rmtree(MEM, ignore_errors=True)
            return self._send(200, {"ok": True})
        if self.path == "/api/ask":
            q = str(body.get("question", ""))[:300].strip()
            if not q or "result" not in LAST:
                return self._send(400, {"error": "run an investigation first, then ask"})
            with LOCK:
                gen = NightshiftGenerator.from_env() if body.get("use_model", True) else None
                return self._send(200, ask(q, LAST["result"], gen))
        if self.path == "/api/investigate":
            sid = body.get("scenario", "")
            if sid not in {s["id"] for s in scenario_list()}:
                return self._send(400, {"error": "unknown scenario"})
            try:
                with LOCK:
                    out = investigate(sid, use_model=bool(body.get("use_model", True)))
                return self._send(200, out)
            except Exception as e:  # surface the reason in the page instead of a blank screen
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        self._send(404, {"error": "not found"})

    def log_message(self, *a):
        pass


def main():
    load_env()
    sys.path.insert(0, str(ROOT))
    port = int(os.environ.get("PORT", "8000"))
    print(f"Build-Failure Detective on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
