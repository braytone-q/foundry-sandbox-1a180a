# Re-gen multiagent validation — 2026-10-08

## Implemented behavior

Opt-in application-level coordination runs activity extraction, optional actual
image inspection, and the existing Search-grounded Foundry rules agent. Typed
stage findings are saved incrementally and shown on current and historical
attempts. The coordinator preserves reported facts, generates canonical image
receipts, and flags contradictory specialist claims and mismatched/inconclusive
images. Human decisions remain separate.

## Automated verification

- Activity/configuration tests: 13 passed after 13 expected missing-contract failures.
- Coordinator and gateway regression tests: 80 passed after 13 expected missing-coordinator failures.
- Storage/API integration tests: 5 passed after 5 missing-storage/API failures.
- Final complete suite: `.venv/bin/python -m pytest -q` — 217 passed in 91.66s.
- The suite includes executable Node checks for current/historical traces,
  skipped and failed stages, legacy null traces, literal HTML-looking findings,
  and unchanged failed-attempt human-review controls, plus existing browser checks.
- `node --check regen_api/static/app.js` and `git diff --check` passed.

FastAPI TestClient stalled under filesystem/network sandbox restrictions; the
suite passed with reviewed elevated execution. Test-only DOM emulation was
extended locally to support the existing history card's classList operation.

## Live Azure verification

Two explicitly synthetic submissions used a temporary database and the existing
Azure credentials, model deployment, pinned regen v11 agent, and Search setup.
The temporary database and synthetic evidence were removed after the checks.
No existing submissions or human review statuses were changed.

- Text: SUCCEEDED; activity SUCCEEDED, evidence SKIPPED, rules SUCCEEDED;
  recommendation FLAG_FOR_REVIEW; final analysis retained exactly 14 fields.
- Synthetic red-square image against a reported planting activity: SUCCEEDED;
  all three specialists SUCCEEDED; image overall MISMATCH; final recommendation
  FLAG_FOR_REVIEW; receipt `Image 1: synthetic-red-square.png`.
- Both records remained PENDING_REVIEW with no human review events.

## Execution decisions

- Native implementation with one independent final reviewer followed the
  recommended method, accepted with the user's automatic approval instruction.
  Tradeoff: no separate reviewer for each task.
- Sandbox denial of git worktree creation triggered the documented in-place
  fallback. Unrelated working-tree edits were preserved and excluded from commits.
  Tradeoff: implementation shares the current feature branch.
- Stage findings use role-validated typed unions to prevent incompatible
  specialist payloads. Tradeoff: future trace versions must migrate explicitly.
- Null rule-side facts do not contradict reported extraction. A non-null rule
  assertion against a different or unknown extracted fact is flagged while the
  reported extraction is preserved. Tradeoff: conservative extra review flags.

## Rollout

Use `REGEN_ANALYSIS_MODE=multiagent ./run_api.sh` to opt in. The default remains
single_agent; restart in that mode to roll back without losing stored traces.
Each provider request has its own existing timeout; the sequential attempt can
take longer overall and incurs an additional extraction inference call.

## Independent review

A fresh read-only reviewer examined the feature commit range
`d48e658..fa0ef3d` and found no Critical, Important, or Minor issues. The reviewer
independently ran 26 activity/orchestration tests, browser trace checks, and
commit-range whitespace checks successfully. The implementation is ready for
opt-in use; the review's pending live-image condition was subsequently satisfied
by the successful Azure smoke test above.

The reviewer excluded pre-existing authentication, deployment, dependency, and
connection edits from judgment. This scope decision stands because those edits
were preserved without modification or inclusion in feature commits; this
review does not certify unrelated work. Live image compatibility was set aside
while the test was running and is now covered by the successful live result.

The work is retained on the current feature branch. No merge, push, or deployment
was performed as part of this implementation.
