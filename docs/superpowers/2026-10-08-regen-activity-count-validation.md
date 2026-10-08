# Ask Re-gen saved activity quantities

## Problem and correction

The user asked how many trees were planted in Nanyuki. The assistant incorrectly
said it lacked live planting records, although the local database contained a
human-approved report for 300 trees. The Q&A pipeline previously received human
status counts only, without activity quantities or reported places.

The server now supplies a second read-only aggregate snapshot to both the routing
and Search answer stages. It groups current saved reports by normalized activity
type, reported location, and human review status. Questions use these local totals
without unrelated programme retrieval and distinguish approved reports from
pending, clarification-requested, and rejected reports. Reported quantities are
claims in this local dataset, not independently measured town-wide planting.

Each submission contributes only its latest attempt on the current source revision.
Failed/running/missing latest analyses are excluded and counted as unavailable;
older successes are not reused. Missing/negative quantities are unquantified,
never subtracted or asserted as known zero. Source text, reviewer notes, image
contents, and device coordinates are excluded. Reported place labels are included
as untrusted aggregate data. No review decision or programme rule is changed.

## Verification

- Initial six tests failed for absent aggregation/context before implementation.
- Full regression suite: 226 passed in 70.42s.
- Coverage: case/whitespace/activity-label normalization, retry de-duplication,
  current revision exclusion, approved/pending/rejected separation, unknown
  quantities, negative quantities, privacy, fresh follow-up snapshots, both Q&A
  answer stages, blocked client-injected totals, and sanitized database failure.
- `git diff --check` passed.
- Confirmed no RUNNING analysis before restarting the identified local API.
- Live exact question with the earlier refusal in chat history returned:
  “Human-approved reported planting in nanyuki: 300 trees (1 approved record).”
- Live follow-up asking how many were human-approved also returned 300 from one
  approved record. Both HTTP responses were 200 with knowledge_searched=false
  and no unrelated citations.
- Live question calls were read-only and did not submit or review activities.

## Independent review

A fresh read-only reviewer found no Critical or Important issues. The live
exact-question and follow-up checks above satisfy its readiness condition.

Two nonblocking follow-ups were deferred:

- Review-status and activity snapshots currently use separate read transactions
  and separate timestamps. A concurrent mutation between the reads can make
  cross-summary comparisons inconsistent. A future shared read transaction would
  provide a single coherent capture point; each activity summary remains internally
  consistent today.
- Add direct tests for failed same-revision retry, a running latest attempt, and
  clarification-status aggregation. Existing tests cover failed new revision and
  approved/pending/rejected groups; the shared query handles these deferred cases.

Review scope decisions: unrelated pre-existing changes remain untouched and are
not certified by this review. Actual Foundry wording/stale-history recovery was
verified by the parent live against the running server. Accuracy of extracted
claims and independent proof of planting remain outside this reporting feature;
counts are explicitly reported claims. Production-scale context size/performance
was not benchmarked in this local prototype. The parent ran and inspected the full
226-test suite; the reviewer did not duplicate it.
