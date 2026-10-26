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

## In plain English
_written by `nvidia/nemotron-3-ultra-550b-a55b` through Meterless Nightshift; every citation checked against collected evidence_

Production deploy d-102 failed because the required environment variable DATABASE_POOL_SIZE is missing in the production environment. A recent commit introduced a requirement for this variable, but production does not define it, while CI does, allowing CI to pass.

- The failed deploy d-102 produced a KeyError indicating that the required environment variable DATABASE_POOL_SIZE was not set. [deploy:d-102] [log:d-102:7]
- A commit added a requirement for the DATABASE_POOL_SIZE environment variable. [commit:9f8e7d6]
- The production environment is missing DATABASE_POOL_SIZE and does not define any of the suspect settings. [env:d-102]
- The CI environment defines the required setting, so the CI run passes. [ci:ci-9f8e7d6]
- Other commits were ruled out as they do not overlap with the error signature or only appear in non-fatal warnings. [commit:55aa66b] [commit:77bb88c]

**Suggested fix:** Add the DATABASE_POOL_SIZE environment variable to the production environment to satisfy the new requirement. [env:d-102] [commit:9f8e7d6]

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