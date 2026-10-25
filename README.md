# Build-failure detective (Open Agent Hackathon 2026)

Track: **The Agent That Can Explain Why**

**User:** a small dev team with no dedicated ops person.
**Problem:** a production deploy fails and nobody knows which change broke it. People guess, roll back, and lose hours.
**What this does:** an agent that investigates the failure across deploy history, logs, commits, CI and the production environment, then reports the likely cause with the evidence behind it, what it ruled out, and how confident it is.

## Run it (no credentials, no dependencies beyond Python 3.10+)

```bash
SAMPLE_MODE=true python3 -m agent.main
python3 -m unittest -v
```

Outputs land in `outputs/report.md` and `outputs/trace.jsonl`. Saved examples are in `sample_outputs/`.

## How it works

- **Planner** decides which specialist to run next based on what the evaluator says is still unproven.
- **Specialists** (deploy, logs, commits, CI) each read one source and return facts with evidence ids like `log:d-102:7`.
- **Evaluator** scores the hypothesis from four checks (error signature in logs, commit introduces it, production lacks it, CI explains the green build). It rejects until everything is verified, which forces the planner to retry and branch. If evidence contradicts the suspect, the agent says "inconclusive" instead of guessing.
- **Memory** recalls earlier cases with the same error signature.
- **Trace** logs every step as JSONL, so you can replay how the answer was reached.

Nothing is hardcoded to the sample answer. The tests move the root cause to a different commit and remove the key evidence, and the agent follows the data.

## Sample data

`sample_data/` is a synthetic project with one planted root cause (a config variable renamed in code but not in production) and decoys (an unrelated email retry change that logs warnings, a lodash bump, a README edit).

## Status and sponsor technology

Honest status as of the last commit:

| Component | Status |
|---|---|
| Agent loop, trace, tests, SAMPLE_MODE | Working |
| Zetaris as the data layer | Not yet integrated |
| Meterless engine (H-MEM) | Not yet integrated (local JSON memory behind the same interface for now) |
| NVIDIA Nemotron | Not yet integrated |

Secrets go in `.env` (see `.env.example`). `.env` is gitignored.

## Pre-existing work

None. Everything in this repo was created during the build window.
