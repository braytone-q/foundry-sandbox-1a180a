# Ask Re-gen validation

- Baseline before question mode: 122 passing tests.
- Current complete suite: 174 passed in49.15 seconds. New coverage includes
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
  route now answers general questions without Search/citations. Re-gen/Green
  Merit mentions force Search; policy and relevant follow-ups retrieve fresh rules.
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
