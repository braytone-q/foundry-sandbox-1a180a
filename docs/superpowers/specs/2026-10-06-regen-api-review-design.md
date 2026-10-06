# Re-gen local API and human-review prototype

Date: 2026-10-06

## Purpose and agreed scope

Build a working local API and browser interface around Re-gen's existing
Microsoft Foundry agent. A local operator can submit environmental activities,
inspect the grounded AI analysis, and explicitly record a human verifier's
decision. The user selected a local prototype rather than a shared Azure pilot.

The approved architecture is FastAPI, SQLite, and a browser interface served by
the same application. Use the working `regen` agent version `11` and its existing
Azure AI Search connection. Preserve the existing provisioning, configuration,
runner, and live acceptance scripts. This phase does not change the Azure index,
its seven rule documents, agent instructions, or Azure role assignments.

The browser interface supports text submissions in this phase. Photographs
mentioned in text remain reported evidence. Actual file upload, enterprise
sign-in, shared hosting, notifications, and reward calculations are outside this
prototype's scope.

Success means that a submission can be analyzed using the live Foundry agent,
saved across application restarts, clarified through a new revision, and reviewed
by an explicit human action with a preserved history. Failed AI attempts remain
visible and cannot masquerade as a successful analysis or human decision.

## Authority and evidence boundaries

- The AI returns only `NEEDS_CLARIFICATION`, `READY_FOR_HUMAN_REVIEW`, or
  `FLAG_FOR_REVIEW`. These remain recommendations.
- Human actions are `APPROVE`, `REJECT`, or `REQUEST_CLARIFICATION`. Only the
  review API accepts these, following an explicit operator action. Neither the
  analysis adapter nor the analysis service can write a human review event.
- A review records the reviewer name, notes, timestamp, submission revision,
  analysis attempt, and action. The reviewer name is required audit metadata,
  not a new programme verification requirement.
- An AI recommendation never triggers a human decision automatically.
- Programme requirements continue to come from Azure AI Search. API validation
  checks structure and internal consistency, not hard-coded activity requirements.
- No endpoint, UI action, background process, or model integration calculates
  Green Merit points, tokens, payments, or rewards.
- All agent inputs are text in this phase, so `evidence_received` must be empty.
  Received evidence cannot be inferred from attachment claims in a description.
- Approval is a human review record in this prototype, not a reward or payment
  instruction and not an AI-issued verification result.

## Components

Add a focused `regen_api` package without moving the existing scripts:

- `settings.py`: project endpoint, agent name and version, database path, and
  model-request timeout configuration.
- `schemas.py`: request/response models, AI analysis validation, and distinct
  recommendation, human action, and workflow status enums.
- `foundry.py`: Foundry client lifecycle, Responses invocation, retrieval checks,
  output parsing, and safe failure classification. It has no database access.
- `store.py`: SQLite initialization, persistence, transactions, and optimistic
  concurrency checks. It has no Foundry integration.
- `service.py`: submission, analysis, revision, and human-review workflows.
- `main.py`: FastAPI routes, dependency wiring, local-origin protections, and
  static interface hosting.
- `static/index.html`, `static/app.css`, and `static/app.js`: browser experience
  with no separate frontend framework or build process.

Add automated tests under `tests/`. Configure test discovery to use that
directory; the existing interactive `test_search.py` is not a pytest test.
Keep `verify_agent.py` as the explicitly invoked live acceptance suite.

## Local operation and configuration

The documented launch command binds to `127.0.0.1`, normally port `8000`.
The browser and API share an origin. There are no permissive CORS settings.
Reject unexpected Host headers and cross-origin browser mutations. Mutating
requests require JSON bodies; command-line clients on the trusted local machine
may call the API without an Origin header.

This is a trusted, single-operator local workspace. It has no account management
or authenticated multi-user roles. Reviewer names are operator assertions, not
verified identities. Do not describe this prototype as a shared or authenticated
verification service. A future shared deployment needs a separate authentication
and authorization design before exposure beyond localhost.

Defaults:

- Project endpoint: the existing Re-gen Foundry project endpoint.
- Agent name: `regen`.
- Agent version: `11`, explicitly pinned rather than automatically using latest.
- Database: `runtime/regen.sqlite3`, excluded from Git with the entire runtime
  directory, including SQLite journal files.
- Foundry response-request timeout: 90 seconds, with automatic OpenAI retries
  disabled so a failure is represented as one visible analysis attempt. Credential
  acquisition can add time before the response request begins.

Use environment overrides named `REGEN_PROJECT_ENDPOINT`, `REGEN_AGENT_NAME`,
`REGEN_AGENT_VERSION`, `REGEN_DATABASE_PATH`, and `REGEN_REQUEST_TIMEOUT_SECONDS`.
Use `DefaultAzureCredential` with the already documented local Azure CLI session.
Browser code never receives credentials or invokes Azure directly.

The application supports one server process for this prototype. Each database
operation opens its own connection. A network call must not hold an open SQLite
write transaction. Client resources are created and closed with the application
lifecycle. Serving the interface and reading stored submissions do not require a
working Azure sign-in; analysis failures expose the sign-in problem when invoked.

## Persistence model

Use four tables initialized additively on startup. The new application database
is independent of Azure Search. Do not reset or delete existing databases.

1. `submissions`: server-generated UUID, creation/update timestamps, current
   revision number, monotonically increasing record version, and human workflow
   status (`PENDING_REVIEW`, `CLARIFICATION_REQUESTED`, `APPROVED`, `REJECTED`).
2. `submission_revisions`: immutable full description, revision number,
   submission UUID, and creation timestamp. Revision numbers are unique within
   each submission. The first revision is number one.
3. `analysis_attempts`: server-generated UUID, revision reference, start/finish
   timestamps, state (`RUNNING`, `SUCCEEDED`, `FAILED`), successful analysis JSON
   or safe failure code/message, agent name/version, Foundry response ID when
   available, and optional citation metadata.
4. `review_events`: immutable reviewer name, notes, human action, timestamp,
   submission/revision reference, and successful analysis-attempt reference.

Enable foreign keys. Generate timestamps on the server in timezone-aware UTC;
the interface displays them in the browser's local timezone. Preserve submitted
text without rewriting reported dates such as "today" into invented facts.

Analysis attempts and review events are append-only. No delete or edit-history
endpoint is included. A failed attempt has no successful analysis JSON. A
successful attempt has the validated 14-field analysis object.

Human workflow status is separate from analysis state and AI recommendation.
`READY_FOR_HUMAN_REVIEW` cannot set `APPROVED`; `FLAG_FOR_REVIEW` cannot set
`REJECTED`; `NEEDS_CLARIFICATION` cannot create a human clarification event.

## Submission and analysis workflow

1. Validate a nonblank description of at most 16,000 characters. Extra request
   fields are rejected, including client-supplied recommendations or decisions.
2. Save the submission and first revision, then create a `RUNNING` analysis
   attempt and commit that transaction before contacting Foundry.
3. Invoke the existing agent reference with the current revision's text. Keep
   this blocking SDK call in a synchronous route/service execution context so
   it does not block FastAPI's asynchronous event loop.
4. Require a completed response and an Azure AI Search tool-result event without
   a reported tool failure. A model message without retrieval is an analysis
   failure even if it contains plausible JSON.
5. Parse the final output as one JSON object and validate all fields. On success,
   save the analysis and available response/citation metadata. On failure, save
   a safe diagnostic and retain the source submission for inspection and retry.
6. Return the saved record. Creating a submission returns HTTP 201 even if its
   analysis attempt fails, because the submission was successfully persisted.
   The response explicitly reports `FAILED`; the browser must display that
   state rather than suggesting the submission was lost or ready for review.

Validate the exact analysis fields from `AGENTS.MD`: `activity_type`, `quantity`,
`species`, `species_category`, `activity_date`, `location`, `community_group`,
`evidence_reported`, `evidence_received`, `missing_information`, `inconsistencies`,
`recommendation`, `reason`, and `clarification_question`.

Nullable fact fields accept strings or null, except quantity, which accepts a
JSON number or null and rejects booleans. Lists contain strings. Recommendation
uses the three-value AI enum. Reason is nonblank. All 14 keys must be present;
unknown fields are rejected rather than silently discarded. Do not coerce a
string quantity into a number or manufacture absent values.

`READY_FOR_HUMAN_REVIEW` requires empty missing-information and inconsistency
lists and a null clarification question. `NEEDS_CLARIFICATION` requires at least
one missing-information entry, an empty inconsistency list, and a nonblank
clarification question. `FLAG_FOR_REVIEW` can represent a genuine
contradiction or the absence of an approved rule, so it need not have a nonempty
inconsistency list. These checks do not introduce programme requirements.

Store citation titles and source URLs only when supplied by the response. Do
not fabricate source metadata. Citation display is optional; a source URL must
use an allowed HTTPS scheme before the browser renders it as a link.

Safe failure categories include Azure authentication, access denied, timeout,
upstream service error, absent retrieval, and invalid analysis. Expose a short
actionable message, not raw credentials, encrypted reasoning, or full exception
payloads. Do not fabricate an AI recommendation when infrastructure fails.

An explicit retry adds an analysis attempt for the current revision. Block a
second analysis or a review while that revision has a running attempt. If the
single server process restarts, mark leftover running attempts as failed with
an interruption message; they must not remain permanently running.

## Revisions and human review

A revision supplies a complete replacement description and the record version
the operator viewed. Preserve all older revisions. Analyze only the new complete
description; historical descriptions remain audit history rather than being
silently mixed into the current agent input.

Allow revisions while the submission is pending or clarification was requested,
provided no analysis is running. Creating a revision resets the human workflow
to `PENDING_REVIEW` and creates a new analysis attempt. Earlier review events and
analyses remain visible in history, but an older successful analysis cannot
authorize a decision on the new revision.

A human review requires a successful latest analysis for the current revision,
a nonblank reviewer name (at most 120 characters), nonblank notes (at most 4,000
characters), an allowed human action, and the expected record version. Notes are
review metadata, not an AI-required activity field.

Permit the human to choose an action independently of the AI recommendation.
Every successful review action inserts a review event and updates workflow
status in one transaction. `REQUEST_CLARIFICATION` leaves the submission available
for a new revision. `APPROVE` and `REJECT` close it to further analysis, revisions,
and review actions in this prototype. Reopening a final decision is outside scope.

Use optimistic concurrency for revision, retry, and review mutations. Validate
the expected version and update it atomically when the mutation succeeds. Return
HTTP 409 on stale state or a competing running attempt, so two tabs cannot
silently overwrite one another or record conflicting final decisions.

## API contract

The API uses `/api` paths with JSON requests/responses and generated OpenAPI
documentation. Response records include submission metadata, current description,
workflow status, record version, latest attempt state/result, and relevant history.

- `GET /api/health`: local service/database readiness and configured agent
  reference. It does not perform a live Azure call or claim Azure connectivity.
- `POST /api/submissions`: body `{description}`; save and analyze; return HTTP
  201 with the saved record, including a failed attempt if analysis fails.
- `GET /api/submissions`: paginated queue/list with optional workflow-status,
  recommendation, and analysis-state filters. Default page size 25, maximum 100;
  default view contains pending and clarification-requested records, newest first.
- `GET /api/submissions/{id}`: current submission, revisions, analysis attempts,
  and human review history. Missing IDs return HTTP 404.
- `POST /api/submissions/{id}/revisions`: body `{description, expected_version}`;
  append and analyze a revision; return HTTP 201 with the updated record.
- `POST /api/submissions/{id}/analyze`: body `{expected_version}`; append a retry
  for the current revision; return HTTP 200 with the updated record.
- `POST /api/submissions/{id}/reviews`: body
  `{action, reviewer_name, notes, expected_version}`; save a human review;
  return HTTP 201 with the updated record.

Input validation errors return HTTP 422; stale/illegal workflow transitions
return HTTP 409. Unexpected local persistence failures return a safe HTTP 500.
Creation/revision/retry responses report persisted analysis failures in the record
rather than dropping that record behind an upstream error response.

## Browser experience

Use a responsive conservation-themed interface with a light background, dark
green navigation and actions, readable typography, and text labels alongside
status colors. Do not require external fonts or image assets.

Navigation has Submit Activity, Review Queue, and History. The submission form
collects the activity description, not a fixed set of hard-coded programme fields.
After submission, show the AI recommendation, missing information, clarification
question, inconsistencies, and the reported/received evidence distinction.

The queue supports status/recommendation filters and pagination. Opening a record
shows its current source text, extracted facts, AI reason, evidence, optional
sources, current analysis state, and human review history. The interface clearly
labels AI recommendations separately from human review status.

The human-review panel requires reviewer name and notes and has explicit Approve,
Reject, and Request Clarification actions. Show the proposed human action and
notes in a confirmation step before sending the review mutation. Disabled actions
explain running, failed, stale, or already-final state. A 409 refreshes the record
and asks the operator to inspect the latest state rather than blindly retrying.

Clarification uses an editable copy of the current complete description and saves
a new revision. Failed analyses show their safe failure message and an explicit
Retry Analysis action. Loading and empty states are usable. Disable duplicate
form clicks while requests are pending. History includes both source revisions
and earlier AI/human events, including failed attempts.

Render submitted text, AI output, reviewer names, and notes as text, not trusted
HTML. Use accessible labels, keyboard-operable controls, visible focus states,
and responsive layouts. Display timestamps in local browser time. No UI wording
claims that the AI has approved, rejected, verified, rewarded, or inspected an
absent photograph.

## Verification and completion criteria

Automated tests use temporary SQLite databases and inject a controlled gateway
only at the external Foundry boundary. Production starts in live mode; test
fixtures must not silently become a product demo fallback.

Test these observable behaviours:

- Create, list, filter, paginate, and load a submission across store/app restarts.
- Preserve revisions and failed/successful attempts without overwriting history.
- Validate all analysis fields and reject absent retrieval, malformed JSON,
  prohibited AI decisions, invented received evidence, and internally inconsistent
  recommendations.
- Persist source text and a visible failure on timeout, authentication, access,
  and model failures; permit an explicit retry without changing source history.
- Leave human status pending after every successful AI recommendation.
- Require explicit human action and review metadata; record a decision atomically
  against the latest successful revision.
- Reject stale versions, double final decisions, reviews during analysis, and
  mutation of a finalized record.
- Recover interrupted analysis attempts after a single-process restart.
- Reject unexpected request fields, unexpected hosts, and cross-origin writes.
- Verify human text and AI output render without executing injected HTML/script.

Run the existing three live acceptance cases against agent version 11, then a
live API submission-to-human-review check using a clearly labeled test activity
in the local database. This test writes no human decision to Foundry or Search.
Run browser QA for submission, queue, detail, clarification, review confirmation,
failure display with controlled test data, and a narrow/mobile viewport.

Deliver the working source, passing automated test results, verified local launch
command, and updated operating instructions. Preserve unrelated current work and
the working Azure resources. The local UI must be usable with the real Foundry
integration, with no fabricated successful AI results on service failure.

## Technical references

- [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/):
  validation and OpenAPI schema support for typed responses.
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/): testing the
  API through its HTTP interface.
- Existing `run_agent.py`, `verify_agent.py`, `connect_search_agent.py`, and
  `AGENTS.MD` are the integration and product-boundary references for this repo.
