# Re-gen MVP image ingestion

## Intent and authorization

The user wants the existing local MVP to ingest images, with a limit of 20.
Interpret this as up to 20 images per activity revision. Preserve the existing
description, analysis, and explicit human-review workflow. The user's automatic
design approval remains in effect. Default to upload plus AI image analysis;
the optional preference question can still steer that choice.

## Approach

Extend the local SQLite/file store and the existing Foundry adapter. Local files
fit this trusted local prototype; Azure Blob Storage would add deployment and
access configuration the MVP does not need. Storing files only for humans would
avoid vision calls but would leave the agent unable to examine the evidence.

Accept 1–20 non-animated JPEG, PNG, or WebP uploads, at most 8 MiB each, no more
than 32 million decoded pixels and no dimension larger than 16,000. Inspect and
fully decode the file rather than trusting its extension or declared MIME type.
Reject invalid batches completely before creating a source record or revision.
The multipart request limit is 161 MiB, checked against actual bytes as well as
Content-Length. Never use supplied filenames as filesystem paths.

Original bytes and SHA-256 remain in local storage beside the database, under
`evidence/`. Save metadata with server-generated UUIDs, safe display filenames,
actual MIME type, size, dimensions, and UTC upload timestamp. The image endpoint
serves only a file located through its database ID; no raw directory is exposed.

## Revision and persistence contract

Add `evidence_images` and `revision_images` tables without rewriting existing
records. Existing revisions have zero images. Image associations are immutable:
text revisions retain current images; an image-bearing revision appends new
images, with the combined total capped at 20. Existing images cannot be deleted
or replaced in this phase. A new activity can omit images through the existing
JSON endpoint. Retries use the same current-revision image set.

Stage and validate all uploaded files first. Move UUID-named files and insert
metadata/associations within the short source-save transaction, cleaning up new
files if it fails. Concurrent, stale, running, and final-state checks remain
atomic. No database lock is held during Azure processing. Source and image
receipts remain saved when analysis fails. A filesystem error returns a safe
storage message; retries do not rewrite originals.

Submission responses add `images` metadata for the current revision. Revisions
and attempts add `image_ids` so old review events still identify the exact
evidence associated with the reviewed source and attempt. Existing response
fields and all JSON routes remain available.

## HTTP extension

- `POST /api/submissions/with-images`: multipart `description` and repeated
  `images` files; returns 201 with the saved record, even when AI analysis fails.
- `POST /api/submissions/{id}/revisions/with-images`: multipart `description`,
  integer `expected_version`, and repeated `images`; append a full description
  revision retaining earlier images; returns 201.
- `GET /api/images/{image_id}`: original bytes, verified MIME type, inline
  disposition, nosniff, no-store; nonexistent IDs return 404.

Allow multipart only on the two upload routes; existing mutations still require
JSON. Keep local Host and same-origin protections. Enforce image counts, strict
form field names, meaningful description, file limits, and optimistic versions.
Excess byte limits return 413, unsupported types 415, invalid image/form data 422,
and stale/running/final transitions 409. Invalid uploads leave no partial records.

## Foundry and evidence truth

The hosted agent, approved Search index, and role assignments stay unchanged.
Required Search retrieval and the three AI recommendation values still apply.
Pass the description and actual images through Responses `input_image` data
URIs. Apply EXIF orientation, flatten transparency onto white, and resize a copy
to a maximum 1600-pixel edge before JPEG encoding. Original files stay intact.

The analysis keeps exactly the existing 14 fields. `evidence_received` is a
server-owned receipt list of the files actually passed to the model, with ordinal
labels and display filenames. Validate the model JSON structurally and then set
that receipt list from the verified input manifest. Reject claims of received
evidence when no images were passed. Never derive receipt facts from prose or
filenames alone. Uploaded files remain visible when a call fails, without a
claim that AI analysis completed.

Explain in the input that image content can support observations but cannot
authenticate capture date, location, species, or exact counts by itself. Do not
add programme requirements or treat off-frame material as a contradiction.
The AI cannot approve, reject, verify, reward, or issue payments.

## Browser experience

Add a multi-file picker and preview grid to submission and revision forms, with
the 20-image/8-MiB/type limits visible. Allow removal before upload, show selected
count and bytes, and disable duplicate uploads while saving/analyzing. Submit
FormData only when new files are selected; preserve the JSON text-only path.

Show current images in the detail page with thumbnails, filenames and full-image
links. Older revisions expose their image sets from retained metadata. Label
uploaded images separately from AI analysis and human status. Keep names as
text, revoke preview object URLs, allow same-origin/blob images in CSP only,
and retain existing response-ordering and record-bound confirmation guards.

## Verification

Use real generated image fixtures and temporary SQLite/file storage; mock only
the external Foundry call. Test 20 accepted and 21 rejected, corrupt/spoofed and
animated files, byte/dimension limits, invalid multipart fields, original-byte
retrieval, cleanup, revisions/retries, final/stale/running conflicts, restart,
and failed analysis preserving uploaded evidence. Test actual image input parts
and server-owned evidence receipts. Browser checks cover selection/removal,
20-image submission, gallery/history and responsive layout. One labeled live
20-image synthetic test confirms the deployed agent accepts the image payload.
Run the full existing suite and obtain one fresh whole-change review.
