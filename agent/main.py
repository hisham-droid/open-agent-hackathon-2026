import argparse
import os
import pathlib
import sys

from .data import SampleDataset
from .env import load_env
from .hmem import HMem
from .nightshift import NightshiftGenerator
from .orchestrator import investigate
from .report import render
from .trace import Trace

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(question, data, out, memory_dir, dataset=None, run_id="run-1", generator=None):
    ds = dataset or SampleDataset(data)
    out = pathlib.Path(out)
    trace = Trace(out / "trace.jsonl")
    memory = HMem(memory_dir, log_dir=out / "logs", generator=generator)
    result = investigate(ds, trace, memory, question, run_id=run_id)
    report = render(question, result)
    (out / "report.md").write_text(report)
    return result, report


def main(argv=None):
    p = argparse.ArgumentParser(description="Build-failure investigator")
    p.add_argument("question", nargs="?", default="Why did the latest production deploy fail?")
    p.add_argument("--data", default=str(ROOT / "sample_data"))
    p.add_argument("--out", default=str(ROOT / "outputs"))
    p.add_argument("--memory", default=str(ROOT / ".agent_memory"))
    a = p.parse_args(argv)
    load_env()
    dataset = None
    if os.environ.get("SAMPLE_MODE", "true").lower() not in ("1", "true", "yes"):
        from .zetaris_source import ZetarisDataset, ZetarisError
        try:
            dataset = ZetarisDataset()
        except ZetarisError as e:
            sys.exit(f"Zetaris source failed: {e}")
    _, report = run(a.question, a.data, a.out, a.memory, dataset=dataset, generator=NightshiftGenerator.from_env())
    print(report)


if __name__ == "__main__":
    main()
