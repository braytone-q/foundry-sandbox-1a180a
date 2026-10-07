# Ask Re-gen validation

- Baseline before question mode: 122 passing tests.
- Current complete suite: 183 passed in55.75 seconds. New coverage includes
  general and grounded paths, follow-up context, forced explicit programme
  retrieval, invalid route JSON, strict history/input limits, sanitized failures,
  safe citations, duplicate prevention, navigation, reset and retained drafts.
- Final review found unfinished assistant/Search items could be accepted when
  the outer response was completed. Fourteen regressions failed before the fix
  and passed afterward. General routing messages, grounded answers and all Search
  items now require affirmative completed status. Retrieving the prior live
  programme response confirmed that valid Foundry items include that status.
- Live initial forced-Search tests found unrelated programme citations attached
  to capitals and maths, even after tightening instructions. The automatic typed
  route initially answered general questions without Search/citations, with
  Re-gen/Green Merit mentions forcing Search. The briefing-only extension below
  retains fresh retrieval for policy and relevant follow-ups.
- Seven live localhost/API cases passed: Kenya's capital, multiplication,
  soil conservation, the approved tree-planting requirements, unavailable drone
  survey policy, refusal to approve/issue Green Merit points, and a species-name
  follow-up. The first three used general knowledge with no programme citations.
  The programme/follow-up answers said exact species names are optional. Missing
  policy returned FLAG_FOR_REVIEW; the authority request performed no action.
- All eight existing records were identical before and after live questions.
  Restart verification also preserved all eight records and47 original files,
  including the earlier poster mismatch and location/inspection history.
- Node tests execute the actual app/chat scripts with controlled DOM and HTTP
  boundaries. CUA reports no available apps or browsers; actual browser/mobile
  presentation could not be visually checked.
- No new dependencies, cloud agent versions, programme rules or chat tables were
  created. The existing regen11 analysis remains separate. Conversation state
  lives in the page session; question/context text is sent to Foundry. No device
  coordinates or activity images are fetched or transmitted by question mode.

## Project knowledge follow-up

- Live baseline questions could not name the implemented navigation screens;
  one reply invented Dashboard, Profile and Settings screens. Ask Re-gen now
  receives a maintained briefing of the current project and its implemented
  submission, image, location, storage and human-review workflow. Image limits
  come from the upload implementation constants.
- Prompt-only clarification still applied programme-verification flags and
  unrelated rule citations to undocumented pricing/launch facts. The existing
  typed route now marks briefing-only application answers explicitly. These
  return without Search/citations; programme and mixed questions always retrieve
  when `needs_knowledge=true`, even when the briefing also contributes. Explicit
  Re-gen mentions still force retrieval for drafts classified as ordinary general
  knowledge. Two new routing regressions failed before implementation and passed
  afterward; strict malformed-flag coverage also passes.
- Six opt-in live tests passed in73.51 seconds, covering seven actual questions:
  current project purpose/screens and human decisions, pixel inspection/local
  storage/coordinate privacy, denied-location follow-up, mixed tree-planting
  species policy plus app limits, undocumented pricing/launch facts, unknown
  programme drone policy, and multiplication after project conversation context.
  Exact species remained optional; device location remained required; missing
  programme policy still returned FLAG_FOR_REVIEW. Undocumented product facts
  returned no verification flag or unrelated citations.
- Read-only Azure inspection confirmed `regen` version11 and Ask Re-gen share
  connection `regen-verification-search-mi` and index `regen-verification-index`.
  No agent version or knowledge-index content was changed.
- Restart checks preserved all eight submission records and47 original files;
  live questions also left every full record identical. The server is running
  the updated routing at `http://127.0.0.1:8000/#ask`.
- Review found no Critical or Important product issues. Two Minor live-check
  weaknesses were fixed: coordinate-specific privacy assertions and pagination
  when snapshotting saved records. The incremental routing review approved the
  branch precedence and malformed-response handling.
- Review scope rulings: live answer/citation behavior was checked only for the
  cases above; topic switching now includes project context; remote Search parity
  was refreshed directly; the full regression suite was run; prior unrelated
  Search/CLI edits were left outside this change. Routing and answer reliability
  remain model-dependent beyond the exercised cases. Browser/mobile presentation
  remains unverified because no CUA browser surface is available.

## Live review counts

- The reported question reproduced a refusal to read current app state. The
  question route previously supplied only project facts and chat context, so the
  model had no database counts. A fresh server-owned status summary now reaches
  both answer stages on every request. The single aggregate read closes before
  Azure calls and counts each submission once, regardless of retries/revisions.
- Five regressions failed before the implementation. Six new checks now pass,
  covering empty-store zeroes, all current human statuses, retry/revision counts,
  fresh data after review changes, both answer stages, no source/coordinate
  leakage, rejected client-supplied summaries and sanitized storage errors.
- The live detailed-count question and the exact plain question with the old
  refusal in history both returned pending human review7, clarification0 and
  active queue7, matching the current database and queue filters. Rejected1 was
  separate from the active queue. The mixed species/app-limit question still
  retrieved the optional species rule, and multiplication returned102 without
  programme citations. Four live questions passed; all full records stayed
  identical throughout those checks.
- Restart preserved eight records and47 original files. No descriptions,
  images, device coordinates, IDs or reviewer details enter the status summary;
  questions transmit only aggregate status counts and a snapshot timestamp in
  addition to their existing context. The UI/docs disclose that addition.
- Review found no Critical, Important or Minor issues. Its sandboxed test rerun
  hung and was terminated; verification uses the parent's fresh183-test result.
  Scope rulings: live old-refusal precedence was subsequently verified; current
  authentication worked in the live checks, while broader future classification
  reliability remains model-dependent; UI/doc text was checked separately;
  unrelated existing Search/CLI edits remain excluded.
