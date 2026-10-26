# Investigation report

**Question:** Why did the latest production deploy fail?

**Status:** confirmed  |  **Confidence:** 100%  |  **Rounds:** 4

## Likely cause
Commit 55aa66b ('Upgrade pydantic to 2.5.0') moved pydantic to a new version, but pydantic is 1.10.13 in production while the commit needs 2.5.0, so the new code failed at startup. CI installed the new version, which is why it stayed green.

_Worked through 3 commits since the last good deploy and 7 log lines from the failed deploy._

## Evidence
- Deploy `d-102` (77bb88c) failed; last good deploy was `d-101` (d4e5f6a) [deploy:d-102, deploy:d-101]
- First error in the failed deploy: `ImportError: cannot import name 'field_validator' from 'pydantic' (/app/venv/pydantic/__init__.py)` [log:d-102:7]
- Commit 55aa66b adds a requirement on pydantic [commit:55aa66b]
- Production check: pydantic is 1.10.13 in production while the commit needs 2.5.0 [env:d-102]
- CI run `ci-55aa66b` green: True; CI has what the commit needs: True (this is why tests did not catch it)

## In plain English
_template (no model output was used)_

Commit 55aa66b ('Upgrade pydantic to 2.5.0') moved pydantic to a new version, but pydantic is 1.10.13 in production while the commit needs 2.5.0, so the new code failed at startup. CI installed the new version, which is why it stayed green.

- Production deploy d-102 (commit 77bb88c) failed. [deploy:d-102]
- Deploy d-101 (commit d4e5f6a) was the last good production deploy. [deploy:d-101]
- First error in the failed deploy: ImportError: cannot import name 'field_validator' from 'pydantic' (/app/venv/pydantic/__init__.py) [log:d-102:7]
- Commit 55aa66b ('Upgrade pydantic to 2.5.0') adds a requirement on pydantic (pydantic 2.5.0). [commit:55aa66b]
- Production check: pydantic is 1.10.13 in production while the commit needs 2.5.0. [env:d-102]
- CI run ci-55aa66b green=True; CI defines the setting=True. [ci:ci-55aa66b]

**Suggested fix:** Rebuild and redeploy production so pydantic matches the commit, and make CI install exactly what production runs. [commit:55aa66b] [env:d-102]

## Checks
- log_signature: pass
- commit_introduces: pass
- prod_env_missing: pass
- ci_explains_green: pass

## Ruled out
- 9f8e7d6: no overlap with the error signature in the logs
- 77bb88c: touches 'mailer', which only appears in non-fatal WARN lines

## Memory (H-MEM)
- Nothing relevant in memory yet (cold start).
- Saved lesson `lesson:dependency-version-skew-in-prod` to long-term memory for future runs.

Full step-by-step trace: `trace.jsonl`.