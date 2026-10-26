# Investigation report

**Question:** Why did the latest production deploy fail?

**Status:** confirmed  |  **Confidence:** 100%  |  **Rounds:** 4

## Likely cause
Commit 9f8e7d6 ('Rename DB_POOL to DATABASE_POOL_SIZE for clarity') made DATABASE_POOL_SIZE a required setting, but production does not define it, so the new version aborted at startup and failed its health check.

_Worked through 3 commits since the last good deploy and 7 log lines from the failed deploy._

## Evidence
- Deploy `d-102` (77bb88c) failed; last good deploy was `d-101` (d4e5f6a) [deploy:d-102, deploy:d-101]
- First error in the failed deploy: `KeyError: 'DATABASE_POOL_SIZE' required environment variable not set` [log:d-102:7]
- Commit 9f8e7d6 adds a requirement on DATABASE_POOL_SIZE [commit:9f8e7d6]
- Production check: DATABASE_POOL_SIZE is not set in production [env:d-102]
- CI run `ci-9f8e7d6` green: True; CI has what the commit needs: True (this is why tests did not catch it)

## In plain English
_template (no model output was used)_

Commit 9f8e7d6 ('Rename DB_POOL to DATABASE_POOL_SIZE for clarity') made DATABASE_POOL_SIZE a required setting, but production does not define it, so the new version aborted at startup and failed its health check.

- Production deploy d-102 (commit 77bb88c) failed. [deploy:d-102]
- Deploy d-101 (commit d4e5f6a) was the last good production deploy. [deploy:d-101]
- First error in the failed deploy: KeyError: 'DATABASE_POOL_SIZE' required environment variable not set [log:d-102:7]
- Commit 9f8e7d6 ('Rename DB_POOL to DATABASE_POOL_SIZE for clarity') adds a requirement on DATABASE_POOL_SIZE. [commit:9f8e7d6]
- Production check: DATABASE_POOL_SIZE is not set in production. [env:d-102]
- CI run ci-9f8e7d6 green=True; CI defines the setting=True. [ci:ci-9f8e7d6]

**Suggested fix:** Add DATABASE_POOL_SIZE to the production environment, or give it a safe default, and make CI run with a production-like environment so this is caught before deploy. [commit:9f8e7d6] [env:d-102]

## Checks
- log_signature: pass
- commit_introduces: pass
- prod_env_missing: pass
- ci_explains_green: pass

## Ruled out
- 55aa66b: no overlap with the error signature in the logs
- 77bb88c: touches 'mailer', which only appears in non-fatal WARN lines

## Memory (H-MEM)
- Nothing relevant in memory yet (cold start).
- Saved lesson `lesson:required-config-missing-in-prod` to long-term memory for future runs.

Full step-by-step trace: `trace.jsonl`.