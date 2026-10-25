"""Tiny .env loader (no dependencies). Existing environment variables win."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_env(path=None):
    path = pathlib.Path(path) if path else ROOT / ".env"
    if not path.exists():
        return False
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if value and key.strip() not in os.environ:
            os.environ[key.strip()] = value
    return True
