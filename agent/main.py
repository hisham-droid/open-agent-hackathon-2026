import argparse
import os
import pathlib
import sys

from .data import SampleDataset
from .memory import LocalJSONMemory
from .orchestrator import investigate
from .report import render
from .trace import Trace

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(question, data, out, memory_path):
    ds = SampleDataset(data)
    out = pathlib.Path(out)
    trace = Trace(out / "trace.jsonl")
    result = investigate(ds, trace, LocalJSONMemory(memory_path), question)
    report = render(question, result)
    (out / "report.md").write_text(report)
    return result, report


def main(argv=None):
    p = argparse.ArgumentParser(description="Build-failure investigator")
    p.add_argument("question", nargs="?", default="Why did the latest production deploy fail?")
    p.add_argument("--data", default=str(ROOT / "sample_data"))
    p.add_argument("--out", default=str(ROOT / "outputs"))
    p.add_argument("--memory", default=str(ROOT / ".agent_memory" / "cases.json"))
    a = p.parse_args(argv)
    if os.environ.get("SAMPLE_MODE", "true").lower() not in ("1", "true", "yes"):
        sys.exit("Live data sources are not wired up yet. Run with SAMPLE_MODE=true.")
    _, report = run(a.question, a.data, a.out, a.memory)
    print(report)


if __name__ == "__main__":
    main()
