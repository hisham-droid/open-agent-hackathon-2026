# Investigation report

**Question:** Why did the latest production deploy fail?

**Status:** confirmed  |  **Confidence:** 100%  |  **Rounds:** 4

## Likely cause
Commit 9f8e7d6 ('Rename DB_POOL to DATABASE_POOL_SIZE for clarity') made DATABASE_POOL_SIZE a required setting, but production does not define it, so the new version aborted at startup and failed its health check.

## Evidence
- Deploy `d-102` (77bb88c) failed; last good deploy was `d-101` (d4e5f6a) [deploy:d-102, deploy:d-101]
- First error in the failed deploy: `KeyError: 'DATABASE_POOL_SIZE' required environment variable not set` [log:d-102:7]
- Commit 9f8e7d6 adds a requirement on DATABASE_POOL_SIZE [commit:9f8e7d6]
- Production env missing: DATABASE_POOL_SIZE; defined: none [env:d-102]
- CI run `ci-9f8e7d6` green: True; CI defines the variable: True (this is why tests did not catch it)

## Checks
- log_signature: pass
- commit_introduces: pass
- prod_env_missing: pass
- ci_explains_green: pass

## Ruled out
- 55aa66b: no overlap with the error signature in the logs
- 77bb88c: touches 'mailer', which only appears in non-fatal WARN lines

Full step-by-step trace: `trace.jsonl`.