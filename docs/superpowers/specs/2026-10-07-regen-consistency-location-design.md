# Re-gen image consistency and required device coordinates

## Intent and findings

The user wants the actual supplied image compared with the described activity,
and fresh coordinates from the submitting device. The user requires location
before submission; failure to obtain it must block saving. Automatic design
approval remains in effect; implement inline and preserve unrelated edits.

The latest record 9ef2e71f-1d06-4644-ac36-5821f06231df describes planting 300 trees.
Its image is a recruitment poster containing some planting photographs. Agent11
classifies the reported action correctly but does not inspect evidence relevance.
Its instructions focus on extracting reported facts and retrieved rule checks.
The existing input forwards actual pixels, but no structured inspection result
or deterministic mismatch guard exists. Receipt alone does not mean support.

## Image pipeline

Use two calls through the existing Projects OpenAI client. First, the existing
vision-capable gpt-5-mini deployment inspects all supplied images with a strict
JSON schema, independent of programme-rule extraction. It must describe visible
content and compare each image to the quoted, untrusted source description.
Per-image verdict: SUPPORTS, UNRELATED, CONTRADICTS or UNCLEAR. Posters, logos,
screenshots, illustrations or unrelated objects cannot establish a field activity
merely because their text, decorations or inset pictures mention trees.
Do not infer date, exact quantity, species or location from insufficient pixels.
Support is visual consistency, never authentication or final verification.

Validate exactly one observation per supplied image, unique ordinal 1..N and
nonblank visible_content/explanation. Attach IDs and filenames from the saved
manifest, never model-generated IDs. Aggregate: any UNRELATED/CONTRADICTS gives
MISMATCH; otherwise any UNCLEAR gives INCONCLUSIVE; all SUPPORTS gives SUPPORTS.
A failed or malformed inspection fails the attempt with originals retained.

Second, agent regen11 receives the reported description and the inspection
report and retrieves approved Search rules as before. It need not receive pixels
again. Keep the exact 14-field Analysis schema; factual evidence_received receipts
refer to the actual images supplied to this analysis pipeline. Independently
force FLAG_FOR_REVIEW for MISMATCH or INCONCLUSIVE, with image findings in reason
and true mismatches in inconsistencies. A model returning READY cannot override
this guard. Keep activity_type/quantity as reported facts. Human decisions remain
independent. Persist the typed image assessment on the exact attempt; older
attempts have null, shown as not inspected under the new checks.

## Device coordinates

On each create or source-revision submit, automatically call browser geolocation
with enableHighAccuracy:true, maximumAge:0, timeout:15000; a 20000ms application
deadline also bounds a pending permission prompt. Require permission and a fresh
successful fix before sending any POST. Denial, timeout, unavailable/unsupported
location preserves the draft, explains the issue and permits retry. No inferred
coordinates from IP, EXIF or the described place.

DeviceLocation: latitude [-90,90], longitude [-180,180], accuracy_m >=0 finite,
captured_at timezone-aware ISO timestamp, source literal browser_geolocation.
Create/revision input requires it; reject captured_at older than 5 minutes or
more than 30 seconds in the future before file storage/Azure. Persist by source
revision in an additive revision_locations table. Current records, revisions and
attempts expose device_location; retries reuse their revision snapshot. Historical
records remain null, without inventing a retrospective fix. Numeric timestamp
validation never rechecks freshness when rendering old stored output.

Store coordinates locally and show them as device-reported submission location,
accuracy and capture time, separate from the reported activity location. Do not
send precise device coordinates to Azure. Browser/HTTP clients can misreport a
position: this is provenance, not attested proof of the activity site.
Multipart adds JSON device_location; JSON routes require the same typed object.

## UI and verification

Show reported activity labels plus a prominent image consistency card with each
image's visible summary, verdict and comparison. Older attempts explicitly lack
this new check. Show current and historical device fixes. Review confirmations
and response sequencing remain bound to the exact record. A location await must
not move a revision action to another record after navigation.

Use TDD for mismatch override, mixed/inconclusive/supportive cases, exact image
coverage, safe failed vision, real request parts, persistence/retry, invalid and
stale coordinates in JSON/multipart, required permission failure, timeout and
navigation. Live reanalyze the latest failed poster example and test a clearly
unrelated synthetic image and the 20-image path. Preserve all originals/history.
Browser surfaces were unavailable last turn; try current availability, otherwise
state the visual/device hardware limitation and use executable JS/HTTP checks.
