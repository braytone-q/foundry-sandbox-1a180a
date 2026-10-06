# Re-gen API and human review implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. The user has authorized automatic approval of design-process steps; execute inline without additional design prompts.

**Goal:** Deliver a local browser submission and human-review workflow backed by a real Foundry API integration and durable SQLite history.

**Architecture:** Add a `regen_api` package with strict schemas, a Foundry adapter, a transactional store, workflow service, and FastAPI endpoints. Serve a plain HTML/CSS/JS interface from that application. Preserve the current scripts and cloud configuration.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, sqlite3, Uvicorn, existing Azure SDKs, pytest, and browser JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-06-regen-api-review-design.md`

## Global constraints

- Default agent reference is `regen` version `11`; default request timeout is 90 seconds with SDK retries disabled.
- Accept only the existing 14 analysis fields and three AI recommendation values.
- Text-only inputs require `evidence_received == []`; no programme-required fields are invented.
- Human actions require explicit input and never derive from an AI recommendation.
- Store source revisions, analysis attempts, and review events independently; do not hold database transactions during Azure calls.
- Bind the documented server to `127.0.0.1:8000`; no sign-in claims or shared hosting in this phase.
- Description maximum 16,000 characters; reviewer name maximum 120; notes maximum 4,000.
- SQLite defaults to `runtime/regen.sqlite3`; ignore runtime and execution scratch files.
- Existing CLI/provisioning scripts, index documents, agent instructions, and role assignments are unchanged.

## Review focus

- A failed retry after a successful analysis must not permit review against the older successful attempt.
- A concurrent retry/revision/review must not bypass a running attempt or stale record version.
- A generic provider error must not expose credential material or fabricate a successful analysis.
- Whitespace-only inputs and boolean/string quantities must not bypass strict validation.
- Untrusted record text and unsafe citation URLs must not become executable browser markup.

## Task 1: Strict analysis contract and Foundry adapter

**Files:** Create `regen_api/__init__.py`, `settings.py`, `schemas.py`, `foundry.py`, `requirements-api.txt`, `requirements-dev.txt`, `pytest.ini`, `tests/test_contract.py`.

**Interfaces:**
- Produce `Settings.from_env() -> Settings` with endpoint, agent_name, agent_version, database_path and timeout_seconds.
- Produce `Analysis.model_validate(data) -> Analysis` and `SubmissionInput`, `RevisionInput`, `RetryInput`, `ReviewInput`.
- Produce `AnalysisResult(analysis, response_id, citations)` and `AnalysisFailure(code, message)`.
- Produce `parse_response(response) -> AnalysisResult` and `FoundryGateway.analyze(description: str) -> AnalysisResult`, `close() -> None`.

- [ ] Write tests before implementation: valid existing schema passes; missing keys, extra keys, prohibited decisions, received evidence, contradictory READY, empty clarification, boolean/string quantity fail; unsafe citation links are omitted; missing retrieval and invalid JSON fail with safe codes.
  Assertions include `Analysis.model_validate(payload).recommendation == "READY_FOR_HUMAN_REVIEW"` and a `ValidationError` for `quantity=True`.
- [ ] Run `.venv/bin/python -m pytest tests/test_contract.py -q`. Expected: initial failure because the contract is absent.
- [ ] Implement strict Pydantic models, environment settings, typed gateway boundary, final-message parsing, retrieval checks, and safe failure mapping. Lazy-create live clients; close all client resources on shutdown.
- [ ] Run `.venv/bin/python -m pytest -q`. Expected: all Task 1 tests pass without Azure calls.
- [ ] Commit only Task 1 files and record the successful check in the ledger.

## Task 2: Persistence, workflow, and HTTP API

**Files:** Create `regen_api/store.py`, `service.py`, `main.py`, `tests/test_api.py`, `tests/conftest.py`; modify `.gitignore`.

**Interfaces:**
- Consume Task 1's request models, `AnalysisResult`, `AnalysisFailure`, and `FoundryGateway`.
- Produce `Store.initialize()`, `create(description, agent_name, agent_version)`, `begin_attempt(id, expected_version, agent_name, agent_version, description=None)`, `finish_attempt(attempt_id, result=None, failure=None)`, `review(id, input)`, `get(id)`, `list(status=None, recommendation=None, analysis_state=None, limit=25, offset=0)`, and `recover_interrupted()`.
- Store mutation methods return the current record or an attempt descriptor with its source text. Raise `NotFound` or `Conflict` for invalid transitions.
- Produce `SubmissionService.create(input)`, `revise(id, input)`, `retry(id, input)`, `review(id, input)` and `create_app(settings=None, gateway=None) -> FastAPI`.
- HTTP records contain id, version, current_revision, description, review_status, timestamps, latest_attempt, revisions, attempts, reviews. Latest attempt contains analysis/state/failure, agent metadata and citations. Lists return `{items, total, limit, offset}`.

- [ ] Write HTTP tests first with a temporary real database and a controlled gateway at the external boundary. Test create/restore, all recommendations leave pending status, explicit review, revision history, stale versions, failed retry blocks old-analysis review, running-attempt conflicts, finalized records, interrupted recovery, pagination/filters, host/origin/JSON protections, safe service errors, and strict request limits.
  Assertions include `record["review_status"] == "PENDING_REVIEW"` after analysis, HTTP 409 for stale review, and retained source after a provider failure.
- [ ] Run `.venv/bin/python -m pytest tests/test_api.py -q`. Expected: failure because HTTP application is absent.
- [ ] Implement the four-table SQLite schema and atomic version checks, safe failure persistence, synchronous SDK workflow, immutable revisions/events, restart recovery, and all specified HTTP routes. Return typed record models so OpenAPI describes actual responses. Filter against the latest current-revision attempt only.
- [ ] Run `.venv/bin/python -m pytest -q`. Expected: all contract and API tests pass with real temporary SQLite persistence and no Azure calls.
- [ ] Commit Task 2 files and record the successful check in the ledger.

## Task 3: Browser submission and human-review interface

**Files:** Create `regen_api/static/index.html`, `app.css`, `app.js`, `tests/test_web.py`.

**Interfaces:**
- Consume Task 2's HTTP contract; use record.version for every mutation.
- Produce same-origin UI for Submit Activity, Review Queue, History, record detail, full-description revisions, retries, and confirmation of explicit named human reviews.
- Production is always the real Foundry integration; controlled browser fixtures live in tests only.

- [ ] Write tests that verify the app serves UI/assets and no app initialization needs Azure. Write a controlled browser-QA server fixture for successful, clarification, and failed attempts, separate from production.
- [ ] Run `.venv/bin/python -m pytest tests/test_web.py -q`. Expected: failure because interface assets are absent.
- [ ] Build a responsive light/forest-green interface with accessible forms, filters, pagination, history, status labels, source/AI separation, safe text rendering and HTTPS citation links. Confirm human review in a dialog before mutation; refresh on 409 and never auto-repeat a review. Disable duplicate clicks while requests are pending.
- [ ] Run `.venv/bin/python -m pytest -q` and `node --check regen_api/static/app.js`. Expected: tests pass and JavaScript syntax check exits zero.
- [ ] Run controlled browser QA for create, clarification/revision, retry, human decision confirmation, filters/history, escaped script input, empty/loading/failure states, and mobile layout.
- [ ] Commit Task 3 files and record test/browser evidence in the ledger.

## Task 4: Live verification, operating guide, and branch review

**Files:** Update `INSTRUCTIONS.md`; add `run_api.sh`. Keep runtime data untracked.

**Interfaces:** Consume the completed app and existing live CLI acceptance script. Produce a verified localhost launch command and API examples.

- [ ] Document installation into the existing virtual environment, browser Azure sign-in, local launch, API docs, tests, settings, review authority, text-only evidence, and local prototype limits.
- [ ] Run `.venv/bin/python -m pytest -q`, JavaScript syntax and shell syntax checks, and `git diff --check`. Expected: all pass.
- [ ] Run the existing three live cases against version 11 and a clearly labeled local API activity through create, clarification/revision, and an explicit test human-review decision. Confirm durable history after a restart. Do not send human decisions to Azure or Search.
- [ ] Start the real local server and inspect it in the browser. Verify normal and narrow viewport behaviour.
- [ ] Commit the app and guide changes, then dispatch one fresh whole-branch reviewer as required by executing-plans. Provide spec, plan, review focus, and ledger decisions. Address material findings with failing regression tests followed by a passing full suite.
- [ ] Finish with the running local URL, passing test/live results, and any material limitations. Leave unrelated current changes intact; no cloud publication or destructive cleanup.
