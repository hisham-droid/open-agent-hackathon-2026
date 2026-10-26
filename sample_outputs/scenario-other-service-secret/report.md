# Investigation report

**Question:** Why did the latest production deploy fail?

**Status:** confirmed  |  **Confidence:** 100%  |  **Rounds:** 4

## Likely cause
Commit 77bb88c ('Add retry to email sender, read API token from env') made MAIL_API_TOKEN a required setting, but production does not define it, so the new version aborted at startup and failed its health check.

_Worked through 3 commits since the last good deploy and 7 log lines from the failed deploy._

## Evidence
- Deploy `d-102` (77bb88c) failed; last good deploy was `d-101` (d4e5f6a) [deploy:d-102, deploy:d-101]
- First error in the failed deploy: `KeyError: 'MAIL_API_TOKEN' required environment variable not set` [log:d-102:7]
- Commit 77bb88c adds a requirement on MAIL_API_TOKEN [commit:77bb88c]
- Production check: MAIL_API_TOKEN is not set in production [env:d-102]
- CI run `ci-77bb88c` green: True; CI has what the commit needs: True (this is why tests did not catch it)

## In plain English
_template (no model output was used)_

Commit 77bb88c ('Add retry to email sender, read API token from env') made MAIL_API_TOKEN a required setting, but production does not define it, so the new version aborted at startup and failed its health check.

- Production deploy d-102 (commit 77bb88c) failed. [deploy:d-102]
- Deploy d-101 (commit d4e5f6a) was the last good production deploy. [deploy:d-101]
- First error in the failed deploy: KeyError: 'MAIL_API_TOKEN' required environment variable not set [log:d-102:7]
- Commit 77bb88c ('Add retry to email sender, read API token from env') adds a requirement on MAIL_API_TOKEN. [commit:77bb88c]
- Production check: MAIL_API_TOKEN is not set in production. [env:d-102]
- CI run ci-77bb88c green=True; CI defines the setting=True. [ci:ci-77bb88c]

**Suggested fix:** Add MAIL_API_TOKEN to the production environment, or give it a safe default, and make CI run with a production-like environment so this is caught before deploy. [commit:77bb88c] [env:d-102]

## Checks
- log_signature: pass
- commit_introduces: pass
- prod_env_missing: pass
- ci_explains_green: pass

## Ruled out
- 9f8e7d6: no overlap with the error signature in the logs
- 55aa66b: no overlap with the error signature in the logs

## Memory (H-MEM)
- Nothing relevant in memory yet (cold start).
- Saved lesson `lesson:required-config-missing-in-prod` to long-term memory for future runs.

Full step-by-step trace: `trace.jsonl`.