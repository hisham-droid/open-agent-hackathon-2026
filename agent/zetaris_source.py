"""Zetaris-backed data source. Same interface as SampleDataset, but every fact comes from SQL run on Zetaris.

Uses the Zetaris REST API (HTTP only, no JDBC driver, no Java). Credentials come from environment variables.
"""
import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_REST_URL = "http://localhost:8888/api/v1.0"

QUERIES = {
    "commits": "SELECT sha, ts, author, message, files, diff FROM buildlog.commits ORDER BY ts",
    "deploys": "SELECT id, sha, ts, env, status FROM buildlog.deploys ORDER BY ts",
    "ci_runs": "SELECT run_id, sha, ts, status, env_keys FROM buildlog.ci_runs ORDER BY ts",
    "logs": "SELECT seq, ts, deploy_id, level, service, msg FROM buildlog.logs ORDER BY seq",
    "prod_env": "SELECT deploy_id, env_key, env_value FROM buildlog.prod_env",
}


class ZetarisError(RuntimeError):
    pass


class ZetarisClient:
    def __init__(self, base=None, api_key=None, org_id=None, timeout=120):
        self.base = (base or os.environ.get("ZETARIS_REST_URL") or DEFAULT_REST_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("ZETARIS_API_KEY")
        self.org_id = org_id or os.environ.get("ZETARIS_ORG_ID", "1")
        self.timeout = timeout
        if not self.api_key:
            raise ZetarisError("ZETARIS_API_KEY is not set (see .env.example).")

    def run(self, sql, limit=1000):
        body = {"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": limit}
        req = Request(self.base + "/sql-editor/sqls/run", data=json.dumps(body).encode(), method="POST",
                      headers={"Authorization": f"Bearer {self.api_key}", "X-Org-ID": str(self.org_id),
                               "X-Request-ID": str(uuid.uuid4()), "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                out = json.loads(resp.read().decode() or "null")
        except HTTPError as e:
            raise ZetarisError(f"HTTP {e.code} from Zetaris: {e.read(300).decode(errors='replace')}") from e
        except (URLError, OSError) as e:
            raise ZetarisError(f"Cannot reach Zetaris at {self.base}: {getattr(e, 'reason', e)}") from e
        rows = out.get("data") if isinstance(out, dict) else None
        return [list(r) for r in (rows or [])]


def _split(value):
    return [x for x in (value or "").split(",") if x]


class ZetarisDataset:
    source = "zetaris"

    def __init__(self, runner=None):
        """runner(sql) -> list of rows. Defaults to the live REST client; tests inject a fake."""
        self.runner = runner or ZetarisClient().run
        self.queries = []
        rows = {name: self._query(name) for name in QUERIES}
        self.commits = sorted(({"sha": r[0], "ts": r[1], "author": r[2], "message": r[3],
                                "files": _split(r[4]), "diff": r[5] or ""} for r in rows["commits"]),
                              key=lambda c: c["ts"])
        self.deploys = [{"id": r[0], "sha": r[1], "ts": r[2], "env": r[3], "status": r[4]} for r in rows["deploys"]]
        self.ci_runs = [{"run_id": r[0], "sha": r[1], "ts": r[2], "status": r[3], "env_keys": _split(r[4])}
                        for r in rows["ci_runs"]]
        self.logs = [{"ts": r[1], "deploy_id": r[2], "level": r[3], "service": r[4], "msg": r[5]}
                     for r in rows["logs"]]
        env_rows = rows["prod_env"]
        self.prod_env = {"deploy_id": env_rows[0][0] if env_rows else None,
                         "keys": {r[1]: r[2] for r in env_rows}}
        self.row_counts = {name: len(r) for name, r in rows.items()}

    def _query(self, name):
        sql = QUERIES[name]
        self.queries.append(sql)
        return self.runner(sql)

    def commit(self, sha):
        return next((c for c in self.commits if c["sha"] == sha), None)
