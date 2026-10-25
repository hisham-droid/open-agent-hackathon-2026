"""Data access. SAMPLE_MODE reads local files; a Zetaris-backed source can implement the same interface."""
import json
import pathlib


class SampleDataset:
    source = "sample files"

    def __init__(self, root):
        root = pathlib.Path(root)
        read = lambda name: json.loads((root / name).read_text())
        self.commits = sorted(read("commits.json"), key=lambda c: c["ts"])
        self.deploys = read("deploys.json")
        self.ci_runs = read("ci_runs.json")
        self.prod_env = read("prod_env.json")
        lines = (root / "logs.jsonl").read_text().splitlines()
        self.logs = [json.loads(line) for line in lines if line.strip()]

    def commit(self, sha):
        return next((c for c in self.commits if c["sha"] == sha), None)
