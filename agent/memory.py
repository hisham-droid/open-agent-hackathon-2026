"""Case memory behind a small interface so a Meterless engine can replace the backend."""
import json
import pathlib


class LocalJSONMemory:
    backend = "local-json"

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except json.JSONDecodeError:
                return []
        return []

    def recall(self, tokens):
        wanted = set(tokens)
        return [c for c in self._load() if wanted & set(c.get("tokens", []))]

    def remember(self, case):
        cases = self._load()
        cases.append(case)
        self.path.write_text(json.dumps(cases, indent=2))
