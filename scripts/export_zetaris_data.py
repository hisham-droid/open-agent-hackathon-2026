"""Export sample_data/ as flat {"rows": [...]} JSON files that Zetaris REST tables can read."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "sample_data", ROOT / "zetaris_data"


def write(name, rows):
    (DST / f"{name}.json").write_text(json.dumps({"rows": rows}, indent=1))
    print(f"{name}: {len(rows)} rows")


def main():
    DST.mkdir(exist_ok=True)
    commits = json.loads((SRC / "commits.json").read_text())
    write("commits", [{"sha": c["sha"], "ts": c["ts"], "author": c["author"], "message": c["message"],
                       "files": ",".join(c["files"]), "diff": c["diff"]} for c in commits])
    write("deploys", json.loads((SRC / "deploys.json").read_text()))
    ci = json.loads((SRC / "ci_runs.json").read_text())
    write("ci_runs", [{**r, "env_keys": ",".join(r["env_keys"])} for r in ci])
    logs = [json.loads(l) for l in (SRC / "logs.jsonl").read_text().splitlines() if l.strip()]
    write("logs", [{"seq": i, **l} for i, l in enumerate(logs, 1)])
    env = json.loads((SRC / "prod_env.json").read_text())
    write("prod_env", [{"deploy_id": env["deploy_id"], "key": k, "value": v} for k, v in env["keys"].items()])


if __name__ == "__main__":
    main()
