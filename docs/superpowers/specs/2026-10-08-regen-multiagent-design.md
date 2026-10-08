# Re-gen coordinator and specialist agents

Default-mode update: after implementation and live validation, the user requested
multiagent as the default. The earlier opt-in rollout decision below is superseded;
single_agent remains an explicit environment override.

## Approved intent

The user approved an application-level coordinator with activity, evidence,
and rules specialists. Its output prepares environmental activity submissions
for human verification. Existing submissions, images, device-location capture,
revision history, questions, and human review operations continue to work.

## Architecture and execution

The Python API owns orchestration. Specialist roles are explicit structured
model calls, not autonomous processes with unrestricted tools. The existing
Foundry project client supplies all calls; no new Azure resource is required.
Execute stages sequentially in the first version for predictable failure and
audit handling: activity extraction, optional image inspection, grounded rules
analysis, then deterministic coordination. Each role has a typed contract.

The activity specialist receives only the untrusted reported description. It
returns the seven existing activity fields and evidence_reported, plus a
response ID and configured model identity. Every field is required but unknown
facts are null. Evidence reported is an array of strings. Quantity is finite
and numeric or null. The specialist cannot inspect images, apply programme
rules, recommend approval, or supply evidence receipts. It must not invent facts
or follow instructions embedded in the description. Use a strict JSON schema
and reject incomplete or malformed responses.

The evidence specialist reuses the existing vision inspection contract. Actual
normalized pixels and the original description are its inputs. Validate exact
image coverage and attach server-owned image identifiers. A text-only attempt
records this stage as skipped, without asserting an inspection occurred.
SUPPORTS means visual consistency, never verified location, time, or quantity.

The rules specialist reuses the pinned regen Foundry agent and approved Search
connection. Supply the original description, typed extraction, and any typed
image assessment as untrusted data. Require successful Search retrieval and
validate the existing 14-field Analysis response. Preserve citations. Unknown
programme requirements must yield FLAG_FOR_REVIEW, without inventing policy.

## Deterministic coordinator

The coordinator returns AnalysisResult through the existing gateway interface.
The activity specialist owns reported fact fields and evidence_reported. The
rules specialist owns missing_information, inconsistencies, reason, and
clarification_question and proposes the recommendation. The server owns
evidence_received and generates receipts from the saved image manifest.

Compare activity facts with the rules output before overwriting fact fields.
Any disagreement in non-null reported fields is recorded as a specialist
disagreement in inconsistencies and forces FLAG_FOR_REVIEW. Keep the extracted
reported facts in the final report. Existing image guards also force
FLAG_FOR_REVIEW for MISMATCH or INCONCLUSIVE. No specialist can erase another
stage's unresolved findings. Validate the assembled Analysis after applying
guards; READY_FOR_HUMAN_REVIEW is permitted only when no unresolved finding or
clarification question remains. Evidence_reported always comes from extraction.

The coordinator has no model call or discretion to approve, reject, verify,
award points, issue tokens, or make payments. Device coordinates remain local
and are not sent to specialists. Q&A remains an independent existing flow.

## Configuration and compatibility

Add REGEN_ANALYSIS_MODE with single_agent and multiagent values. Keep
single_agent as the default during rollout and select multiagent explicitly
for testing. Reject invalid modes at startup. Add REGEN_ACTIVITY_MODEL,
defaulting to the existing gpt-5-mini deployment. Existing image, question,
agent-version, Search, authentication, and timeout settings retain their roles.
Keep the current gateway method and exact Analysis contract for both modes.

## Audit and persistence

Add an optional typed orchestration trace to AnalysisResult and Attempt. Store
it in an additive nullable analysis_attempts column. Historical and single-agent
attempts expose null. A trace identifies coordinator version and each stage's
role, configured agent/model, response ID, state, and typed findings. Do not
store raw prompts, credentials, exception text, or extra copies of pixels.

Persist completed stage traces incrementally through an optional gateway
callback, following the existing image-assessment callback pattern. If a later
stage fails, prior completed stages remain available on the failed attempt.
Record a safe failure code for the failed stage and skip subsequent stages.
Existing response_id remains the rules response ID for compatibility.

Show the mode and stage outcomes in an expandable reviewer-facing section for
current and historical attempts. Render specialist strings as text, never HTML.
The final recommendation and human-review controls retain their existing roles.

## Failure handling

Any required specialist failure, missing retrieval, timeout, or invalid contract
fails the analysis attempt; it must not fall back silently or produce a ready
recommendation. Preserve source, evidence, receipts, and completed traces.
Use existing safe authentication, access, timeout, and upstream error mapping,
with an explicit invalid-activity-extraction code for malformed extraction.
Retries execute all stages against the saved revision and evidence snapshot.
No database transaction spans a model call.

## Verification and rollout

Use mocked clients to check call order, strict request schemas, grounding,
malformed/incomplete extraction, failures at each stage, text-only skipping,
receipt ownership, fact disagreement, image mismatch/inconclusive guards, and
the exact final Analysis contract. Exercise additive migration on an existing
database, partial trace persistence, revision/retry binding, historical reads,
API serialization, and escaped reviewer trace rendering. Run the existing
regression suite in single-agent mode and targeted multiagent tests.

Document opt-in local startup, configuration, costs from the additional
extraction call, and rollback by switching the mode to single_agent. A live
Azure smoke test, when credentials and connectivity are available, verifies a
text submission and an image submission without changing human review status.
Report live-test limitations explicitly. This first version does not provision
Foundry-hosted workflows, change approved knowledge, or deploy infrastructure.
