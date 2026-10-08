# Re-gen Multiagent Implementation Plan

Subsequent user instruction: multiagent is now the default. The original
single_agent rollout default recorded in this completed plan is superseded;
explicit single_agent configuration remains supported.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Coordinate activity, evidence, and approved-rules specialists into an auditable report for human verification.

**Architecture:** The Python gateway opts into sequential specialist calls and deterministic coordination. Existing single-agent analysis remains the default. Typed stage snapshots are persisted incrementally and shown to reviewers.

**Tech Stack:** Existing Python, FastAPI, Pydantic, SQLite, Foundry/OpenAI client, pytest, and browser JavaScript; no new dependencies.

**Spec:** docs/superpowers/specs/2026-10-08-regen-multiagent-design.md

## Global Constraints

- Keep single_agent as the default during rollout and select multiagent explicitly for testing.
- Keep the current gateway method and exact Analysis contract for both modes.
- The server owns evidence_received and generates receipts from the saved image manifest.
- Device coordinates remain local and are not sent to specialists.
- No database transaction spans a model call.
- Any required specialist failure fails the attempt; no silent fallback.
- No approval, rejection, verification, rewards, knowledge-source changes, or infrastructure deployment.
- Preserve pre-existing working-tree changes and historical records.

## Review Focus

- Null versus asserted facts: disagreement checks must not mistake absent rule-side facts for contradictions (Task 2).
- Concurrent attempts: callbacks must persist only to their bound running attempt (Task 3).
- Failure after extraction: traces survive safely without leaking provider exceptions (Task 3).
- Historical databases: repeated initialization must preserve old records and nullable trace reads (Task 3).
- Untrusted findings: reviewer UI must render HTML-looking strings as text (Task 4).

## File responsibilities

- Create regen_api/activity.py for typed reported-fact extraction.
- Create regen_api/orchestration.py for coordinator stage execution and deterministic merging.
- Extend regen_api/schemas.py with typed extraction and trace models, plus nullable Attempt trace.
- Extend regen_api/settings.py with mode and activity-model configuration.
- Extend regen_api/foundry.py with gateway dispatch and nullable AnalysisResult trace.
- Extend regen_api/store.py and service.py for bound incremental trace persistence.
- Extend regen_api/static/app.js for expandable current/historical trace rendering.
- Add tests/test_activity.py, test_orchestration.py, test_orchestration_store.py, and tests/browser_orchestration.cjs.
- Extend INSTRUCTIONS.md with opt-in startup and rollback instructions; preserve existing edits.

### Task 1: Activity specialist and configuration

**Interfaces:** ActivityFacts(StrictModel) contains activity_type, quantity, species, species_category, activity_date, location, community_group, evidence_reported. ActivityExtraction contains facts, model, response_id. extract_activity(client, model: str, description: str) -> ActivityExtraction. Settings.analysis_mode defaults to single_agent; Settings.activity_model defaults to gpt-5-mini.

- [x] Write tests/test_activity.py for test_activity_schema_exact_fields, test_unknown_facts_remain_null, test_structured_request_quotes_description, test_invalid_activity_response, and test_mode_configuration. Assert exact eight fact fields, absence of tool/image/receipt inputs, strict JSON schema, required field presence, finite numeric quantity, and safe INVALID_ACTIVITY_EXTRACTION failure for malformed/incomplete output. Assert accepted modes are exactly single_agent and multiagent, default model is gpt-5-mini, and unknown mode raises ValueError.
- [x] Run `.venv/bin/python -m pytest tests/test_activity.py -q`; verify failures identify missing extraction/configuration.
- [x] Implement the interfaces in activity.py and schemas.py and add REGEN_ANALYSIS_MODE/REGEN_ACTIVITY_MODEL parsing in settings.py. Require completed response and strict typed JSON; treat description as untrusted data and forbid invention, policy checks, and decisions.
- [x] Run `.venv/bin/python -m pytest tests/test_activity.py -q`; require all pass.
- [x] Commit only Task 1 files as `feat: add typed Re-gen activity specialist`.

### Task 2: Sequential coordinator and gateway integration

**Interfaces:** SpecialistStage has role (activity/evidence/rules), identity, response_id, state (SUCCEEDED/FAILED/SKIPPED), findings (ActivityFacts/ImageAssessment/Analysis/null), and failure_code. OrchestrationTrace has coordinator_version="1", mode="multiagent", stages. coordinate_analysis(gateway, description: str, images: list, on_image_assessment=None, on_orchestration_trace=None) -> AnalysisResult. merge_analysis(facts: ActivityFacts, rules: Analysis, assessment: ImageAssessment | None, receipts: list[str]) -> Analysis. FoundryGateway.analyze adds optional on_orchestration_trace; AnalysisResult.orchestration_trace is nullable.

- [x] Write tests/test_orchestration.py for extraction→optional vision→rules ordering, required Search retrieval, quoted untrusted specialist inputs, and final exact14 contract. Use mocked responses; assert rules call retains agent_reference version 11 and tool_choice required, text-only evidence stage is SKIPPED, and single_agent makes no extraction call.
- [x] Add test_non_null_disagreement_forces_review, test_null_rules_fact_is_not_disagreement, test_receipts_are_server_owned, test_image_guards_survive_merge, and test_required_stage_failure_stops_calls. Assert extraction facts/evidence_reported survive; disagreeing non-null rule facts produce an inconsistency and FLAG_FOR_REVIEW; unsupported/inconclusive images force FLAG; malformed extraction never invokes rules; missing retrieval never returns success. Cover nullable extraction facts versus rule-side assertions without accepting invented facts.
- [x] Run `.venv/bin/python -m pytest tests/test_orchestration.py -q`; verify expected missing coordinator failures.
- [x] Implement trace models, merge_analysis, coordinate_analysis, gateway mode dispatch, and optional callback. Keep image inspection and parse_response as existing reusable boundaries. Emit a fresh immutable trace after each successful/skipped/failed stage, sanitize exceptions through safe_failure, and validate merged Analysis. Add guards before overwriting facts, deduplicate findings, and preserve the existing single-agent implementation.
- [x] Run `.venv/bin/python -m pytest tests/test_activity.py tests/test_orchestration.py tests/test_contract.py tests/test_image_consistency.py tests/test_image_analysis.py -q`; require all pass.
- [x] Commit only Task 2 files as `feat: coordinate Re-gen analysis specialists`.

### Task 3: Durable attempt traces

**Interfaces:** Store.save_orchestration_trace(attempt_id: str, trace: OrchestrationTrace) -> None persists only to a RUNNING attempt. analysis_attempts.orchestration_trace_json is nullable. Store.finish_attempt stores final trace, retaining earlier snapshots on failure. Attempt.orchestration_trace defaults to null. SubmissionService supplies the trace callback only in multiagent mode, preserving compatibility with existing single-agent fake gateways.

- [x] Write tests/test_orchestration_store.py for legacy database migration, idempotent initialize, JSON readback, revision/retry snapshot binding, partial trace on rules failure, completed-attempt callback rejection, and interleaved attempt callbacks. Assert old attempts return null; failure retains activity findings and sanitized failure_code; callbacks never modify another attempt; source/images and human statuses remain unchanged. Add API serialization coverage using an opt-in mocked multiagent gateway.
- [x] Run `.venv/bin/python -m pytest tests/test_orchestration_store.py -q`; verify failures identify absent persistence.
- [x] Implement additive migration, trace save/read/finalization, and service callback plumbing. Keep database transactions short and ensure returned trace objects match typed API schemas.
- [x] Run `.venv/bin/python -m pytest -q`; require the full Python regression suite to pass.
- [x] Commit only Task 3 files as `feat: retain specialist traces on analysis attempts`.

### Task 4: Reviewer display, documentation, and validation

**Interfaces:** renderOrchestrationTrace(trace) -> HTMLElement renders expandable mode, version, stage identities/states, response IDs, typed findings, and safe failure codes. Null traces render no section. Use the existing DOM text helper and render both latest and historical attempts.

- [x] Write tests/browser_orchestration.cjs covering successful, skipped, failed, historical-null, and HTML-looking finding strings. Assert malicious markup stays literal text and trace display does not change human-review controls. Follow the repository's existing executable Node browser-test pattern.
- [x] Run `node tests/browser_orchestration.cjs`; verify a meaningful failure for absent rendering.
- [x] Implement trace rendering in app.js and document REGEN_ANALYSIS_MODE=multiagent, REGEN_ACTIVITY_MODEL, sequential stages, additional extraction-call cost/latency, failure/retry behavior, local coordinate privacy, and single_agent rollback in INSTRUCTIONS.md.
- [x] Run `.venv/bin/python -m pytest -q`, `node tests/browser_orchestration.cjs`, `node --check regen_api/static/app.js`, and `git diff --check`; require all pass. Run other browser scripts relevant to changed rendering using their existing fixtures.
- [x] If Azure authentication/connectivity is available, perform labeled text and image smoke tests in a temporary database with multiagent mode; verify retrieval, trace, exact14 output, image guard, and unchanged human status. Otherwise record the live-test limitation without weakening unit coverage.
- [x] Save validation results in docs/superpowers/2026-10-08-regen-multiagent-validation.md and commit only Task 4 files as `feat: expose Re-gen specialist analysis history`.
- [x] Obtain one fresh whole-change review, fix consequential findings with targeted failing tests, and rerun affected checks before reporting completion.

## Plan self-review

All approved spec sections map to Tasks 1–4. The same ActivityFacts,
OrchestrationTrace, callback names, and nullable trace field are used throughout.
Tests cover each Review Focus condition, required failures, opt-in compatibility,
grounding, canonical receipts, historical persistence, and reviewer safety.
The user approved native execution and future project gates. Tasks 1–4 are complete. The final independent review found no issues; automated and live Azure verification passed.
