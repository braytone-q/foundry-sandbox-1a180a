# Image consistency and device location validation

- Baseline: 79 tests passed before this phase.
- Current suite: 122 tests passed in 35.88 seconds. Covers mismatch and uncertainty
  guards, exact per-image coverage, failed provider calls, required coordinate
  ranges/freshness and multipart parsing, location revision/retry persistence,
  location permission failure/deadline, retained drafts and navigation identity.
- Final review found completed image inspections were lost if the later Search
  call failed. Inspections now commit before that call and survive failure or
  interruption. Four regressions failed before the fix and passed afterward:
  Search timeout, missing retrieval, invalid output, and restart between calls.
  Failed/interrupted attempts retain no completed analysis and cannot be reviewed.
- Restart verification preserved all eight records and 47 image originals,
  including device locations and inspection snapshots.
- Existing Foundry agent regen11, Search index and permissions are unchanged.
  A separate strict vision call uses the existing gpt-5-mini deployment.
- The latest actual user poster, record 9ef2e71f-1d06-4644-ac36-5821f06231df,
  was reanalyzed successfully: UNRELATED image verdict, MISMATCH overall,
  FLAG_FOR_REVIEW recommendation. Original source, image and prior attempts remain.
  Its original submission has no retrospective device fix.
- Labeled synthetic negative test ed37f266-4e6b-4f43-8909-b0f847655c33 supplied
  20 blue-background/red-circle PNG images with synthetic test coordinates.
  All 20 were inspected, all20 receipts recorded, MISMATCH and FLAG_FOR_REVIEW
  returned with successful approved-rule retrieval. Every original matched SHA-256.
- Live diagnosis exposed model-generated receipt objects; receipts now come from
  the actual input manifest before typed validation. Missing/non-array receipt
  containers, unsupported analysis keys/types and received-evidence claims with
  zero images still fail. Foundry rejects runtime response-format overrides for
  saved agent references; the strict vision format is supported.
- Browser surfaces are unavailable in this session. Executable JavaScript checks
  use controlled geolocation success/denial/timeout callbacks. Actual device
  provider accuracy, browser permission UI and mobile presentation need personal
  testing. The app blocks new create/revision requests until a location fix exists.
- Human approvals were not recorded in this phase. Uploaded-image matching is
  visual consistency, not authentication of the event, date, exact count or site.
