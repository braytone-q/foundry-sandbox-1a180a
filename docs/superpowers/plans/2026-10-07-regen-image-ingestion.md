# Re-gen image ingestion implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, task by task. The user auto-approved design-process steps; do not add approval prompts.

**Goal:** Ingest up to 20 images in the local MVP, analyze actual image inputs, and preserve the evidence for human review.

**Architecture:** Extend immutable source revisions with image associations and local original files. Add multipart endpoints and integrate normalized image copies with the existing Foundry adapter; extend the browser forms and gallery.

**Tech Stack:** Existing FastAPI/SQLite/browser stack, Pillow, python-multipart, pytest, Node.

**Spec:** `docs/superpowers/specs/2026-10-07-regen-image-ingestion-design.md`

## Global constraints

- Maximum 20 images per activity revision; 8 MiB per file; 32 million pixels; 16,000 maximum dimension; 161 MiB actual multipart body limit.
- JPEG, PNG, WebP only, non-animated; retain original bytes and SHA-256.
- Preserve existing JSON routes, text-only submissions, pending human status, and immutable history.
- The 14-field analysis schema remains; evidence_received comes from actual model image input receipts.
- Required Search retrieval, agent regen11, and independent explicit human decisions remain.
- No cloud/index/role changes; preserve earlier uncommitted integration edits.

## Review focus

- A late filesystem failure must not leave visible records with missing images or delete earlier images.
- A stale image-bearing revision must not overwrite newer source/evidence.
- Corrupt/spoofed/animated or decompression-heavy input must not become a trusted image.
- A failed/retried AI call must not lose uploaded files or fabricate completed image inspection.
- Browser selection, navigation, and multipart requests must retain confirmation identity and prevent duplicate uploads.

## Task 1: Validated image storage and API

**Files:** Create `regen_api/images.py`, `tests/test_images.py`; modify `store.py`, `schemas.py`, `service.py`, `main.py`, `requirements-api.txt`.

**Interfaces:**
- `PreparedImage` contains UUID, display name, verified MIME/size/dimensions/hash, timestamp and staged path.
- `prepare_images(files, directory) -> list[PreparedImage]` validates a whole batch and cleans failed staging.
- `Store.create(..., images=[])` and `begin_attempt(..., description=None, images=[])` bind images to a revision; text-only revisions retain images. Attempt descriptors include image metadata/path for analysis.
- `Store.image(id)` resolves metadata/original path; `SubmissionRecord.images` and revision/attempt `image_ids` preserve snapshots.
- Multipart create/revise routes consume normal input models after form parsing, then call the same service; byte-limiting ASGI middleware applies only to upload routes.

- [ ] Write failing tests with actual PNG/JPEG/WebP bytes for 20 accepted/21 rejected, MIME sniffing, corrupt/animated input, dimensions/bytes, strict form fields, file serving and traversal-safe filenames, revision count/history, stale/final/running protection, failed AI preservation, interrupted/restart restoration, and storage-failure cleanup.
- [ ] Run `.venv/bin/python -m pytest tests/test_images.py -q`; expected missing upload routes/helpers fail.
- [ ] Add dependencies and implement validated staging, original-file storage, additive tables, image snapshot metadata, multipart endpoints and body limit. Preserve earlier files on failure. Task 1 uses text-only AI until Task 2 but does not claim images were inspected.
- [ ] Run `.venv/bin/python -m pytest -q`; expected all existing and storage tests pass.
- [ ] Commit only task files and use task-done to ledger verification.

## Task 2: Actual vision input and receipt truth

**Files:** Modify `foundry.py`, `schemas.py`, `service.py`, controlled test gateways; create `tests/test_image_analysis.py`.

**Interfaces:**
- `FoundryGateway.analyze(description, images=None)` accepts persisted image descriptors.
- `image_input(image)` returns a normalized JPEG data-URI input part; original bytes remain unchanged.
- `parse_response(response, evidence_received=None)` validates JSON/retrieval and sets actual image receipts; zero-input invented receipts fail.
- Service passes current-revision images on create, revise and retry; a failed vision request is saved as FAILED with source/images retained.

- [ ] Write failing tests that inspect actual Responses content for all 20 images, EXIF/resize/transparent conversion without original changes, canonical received receipts, image-less fabricated receipts, retry/revision input identity, and safe provider failures.
- [ ] Run `.venv/bin/python -m pytest tests/test_image_analysis.py -q`; expected missing vision/receipt behavior fails.
- [ ] Implement actual image inputs and server-owned receipts; move text-only evidence truth checks from structural schema to the adapter boundary. Keep strict types/14 keys and existing recommendations.
- [ ] Run `.venv/bin/python -m pytest -q`; expected all tests pass.
- [ ] Commit task files and ledger verification.

## Task 3: Upload interface and live verification

**Files:** Create `regen_api/static/images.js`; modify `index.html`, `app.js`, `app.css`, `INSTRUCTIONS.md`, browser fixtures/tests.

**Interfaces:**
- `ImagePicker` tracks selected files, previews, removal, count/byte/type validation and object-URL cleanup.
- Submission/revision handlers consume picker files and submit FormData on the upload routes, otherwise use existing JSON routes.
- Gallery consumes record.images; historical revisions consume image_ids plus retained image metadata.

- [ ] Write failing browser-serving/Node selection tests for 20/21, type/size errors, removal/revocation, safe filenames, FormData and history gallery metadata.
- [ ] Implement responsive upload controls and gallery, progress/failure feedback and Blob CSP support; retain response-ordering and record-bound human confirmation guards.
- [ ] Run `.venv/bin/python -m pytest -q`, JavaScript/shell syntax and git diff --check; expected green.
- [ ] Perform controlled browser QA for select/remove, 20-image upload, gallery/full image, revision and failure/retry/history, mobile, and stale review.
- [ ] Run a labeled live 20-image synthetic fixture through the new API with required Search retrieval; verify receipts, originals and restart preservation. Keep the real server available at localhost.
- [ ] Document supported limits, endpoints, storage/backup and image-analysis limitations; commit only task files.
- [ ] Ledger task completion, dispatch one fresh whole-change reviewer, fix material findings with RED→GREEN regressions and a full green suite, and deliver the running URL and results.
