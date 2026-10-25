"""Three sessions against one persistent memory directory, to show learning carry over.
Session 1: original incident (cold start). Session 2: a different incident (new variable, new commit).
Session 3: the same new incident again. Writes sample_outputs/session-N/ and prints a summary."""
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agent.main import run  # noqa: E402
from make_variant import make  # noqa: E402

Q = "Why did the latest production deploy fail?"


def main():
    out_root = ROOT / "sample_outputs"
    for old in out_root.glob("session-*"):
        shutil.rmtree(old)
    for old in ("report.md", "trace.jsonl"):
        (out_root / old).unlink(missing_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp())
    mem = tmp / "memory"
    variant = make(tmp / "variant")
    plan = [("session-1", ROOT / "sample_data"), ("session-2", variant), ("session-3", variant)]
    for name, data in plan:
        r, report = run(Q, data, out_root / name, mem, run_id=name)
        (out_root / name / "report.md").write_text(report)
        m = r["memory"]
        print(f"{name}: {r['status']} culprit={r['culprit']['sha']} conf={r['confidence']} rounds={r['rounds']} "
              f"memory_fast_path={m['fast_path']} feedback={m['feedback']}")
    shutil.copytree(mem, out_root / "memory_snapshot", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
