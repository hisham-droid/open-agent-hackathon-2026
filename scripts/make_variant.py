"""Write a second, different incident (a new variable, commit and deploys) so memory carry-over can be demonstrated.
Usage: python3 scripts/make_variant.py OUT_DIR"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SWAPS = [("DATABASE_POOL_SIZE", "REDIS_TIMEOUT_SECONDS"), ("DB_POOL", "REDIS_TIMEOUT"), ("9f8e7d6", "3c4d5e6"),
         ("77bb88c", "88cc99d"), ("d-102", "d-202"), ("d-101", "d-201"), ("d-100", "d-200"), ("d-103", "d-203")]


def make(out):
    out = pathlib.Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "sample_data", out)
    for f in out.iterdir():
        t = f.read_text()
        for a, b in SWAPS:
            t = t.replace(a, b)
        f.write_text(t)
    return out


if __name__ == "__main__":
    print(make(sys.argv[1] if len(sys.argv) > 1 else "variant_data"))
