# Re-gen consistency and location implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user auto-approved design gates. One fresh final reviewer; no task implementer agents.

**Goal:** Flag image-description mismatches and require fresh device coordinates before new submissions.
**Architecture:** Structured vision inspection precedes Search-grounded analysis; immutable revision coordinates and attempt inspection snapshots feed browser review.
**Tech Stack:** Existing FastAPI, SQLite, Pillow, Foundry SDK, browser JS, pytest/Node.
**Spec:** docs/superpowers/specs/2026-10-07-regen-consistency-location-design.md

## Global constraints

- Preserve exact14 Analysis fields, Search retrieval and human authority; no cloud/index/role changes.
- Existing20 image,8MiB and decoder limits stand. No fabricated pixels, receipts or coordinates.
- Require browser geolocation: high accuracy, maximumAge0, timeout15000, app deadline20000ms.
- Location freshness <=5min old, <=30sec future; finite latitude[-90,90], longitude[-180,180], accuracy>=0, aware timestamp.
- Old records retain null location/inspection. Retry uses original revision fix; keep precise coordinates local.
- Preserve unrelated Search/CLI working-tree edits and current installed/authenticated environment.

## Review focus

- A vision call that omits, duplicates or misnumbers an image must fail rather than silently support the activity.
- A grounded READY recommendation must not bypass unrelated or uncertain image evidence.
- Location capture completing after navigation must not revise a different record or discard a newer draft.
- Stale/missing/invalid coordinates must fail before files or analysis are saved; old records must still render.
- A failed second model call, retry or migration must retain original files and immutable revision provenance.

## Task 1: Inspect image relevance and gate recommendations

**Files:** Create regen_api/vision.py, tests/test_image_consistency.py; modify foundry.py, schemas.py, store.py, settings.py, app.js, tests/test_image_analysis.py, controlled gateways.
**Interfaces:** inspect_images(client, model, description, images)->ImageAssessment; apply_image_assessment(Analysis,ImageAssessment)->Analysis. AnalysisResult.image_assessment optional. Store additive analysis_attempts.image_assessment_json, Attempt.image_assessment optional.

- [ ] Write failing tests for UNRELATED/CONTRADICTS forcing FLAG even when Search analysis is READY, mixed and UNCLEAR aggregation, all SUPPORTS, exactlyN unique ordinals, blank or malformed output, safe provider failures and retained originals; inspect actual20 image input parts and second call Search required.
- [ ] Run `.venv/bin/python -m pytest tests/test_image_consistency.py tests/test_image_analysis.py -q`; expect missing inspection/guard failures.
- [ ] Implement strict vision schema and actual image input call, persist per-attempt assessment, feed observations to Search agent and enforce mismatch/inconclusive guard after parse. Display reported versus observed activity. No extra programme requirements.
- [ ] Run full `.venv/bin/python -m pytest -q`; expect all pass, including existing storage/history.
- [ ] Commit only task files; task-done records fresh full-suite verification.

## Task 2: Require device coordinates in storage and submit flows

**Files:** Create static/location.js, tests/test_location.py, tests/browser_location.cjs; modify schemas.py, store.py, service.py, main.py, index.html, app.js, images.js and request test helpers.
**Interfaces:** DeviceLocation strict numeric/aware timestamp; SubmissionInput.device_location required. Store.create(...device_location), begin_attempt(...device_location) snapshot and API current/revision/attempt responses. captureDeviceLocation()->Promise<object> rejects missing permission/fix. submissionBody(description,files,version,deviceLocation) adds JSON or multipart field.

- [ ] Write RED tests for missing/out-of-range/nonfinite/naive/stale/future fix, strict multipart object and fields, no calls/files on rejection, revision/retry/restart snapshot, legacy null; JS captures fresh fix, denial/unsupported/app timeout blocks POST and preserves selected images, no duplicate submit, navigation during revision await remains record-bound.
- [ ] Run `.venv/bin/python -m pytest tests/test_location.py tests/test_web.py -q`; expect required-location/JS gaps.
- [ ] Implement additive revision_locations table, strict input validation, optional legacy output, required JSON/multipart location, automatic browser capture before create/revise and current/history display. Preserve form draft on capture failure and keep coordinates out of provider requests.
- [ ] Update existing valid input fixtures to supply current test coordinates; keep deliberate invalid/missing cases raw. Run full suite and Node/JS syntax checks; expect green.
- [ ] Commit only task files and ledger verification.

## Task 3: Verify live behavior and document testing

**Files:** Modify INSTRUCTIONS.md (select only own changes) and save validation notes in docs/superpowers.
**Interfaces:** Real server uses final schema; existing records and the user's latest image retained.

- [ ] Run full suite, JS/shell syntax, git diff --check. Confirm green.
- [ ] Restart only identified API process after no running attempt; use API retry for user's latest unreviewed poster record. Expect MISMATCH or INCONCLUSIVE and FLAG, visible description comparison; original prior attempts remain.
- [ ] Test live clearly unrelated synthetic image versus planting claim and actual20 image inspection path with labeled synthetic device fixes. Verify missing coordinates reject before writes; originals/revision/attempt history persist across restart. Do not use real device coordinates or record human approvals.
- [ ] Try CUA availability for UI verification; otherwise explicitly record executable JS checks and hardware/visual limits.
- [ ] Document permission requirement, required device_location API example, inspection statuses and physical proof limits. Commit isolated docs.
- [ ] Ledger completion, dispatch fresh whole-change reviewer, fix Important/Critical findings with RED->GREEN and full suite. Keep working branch/local app; report findings and deferred minors.
