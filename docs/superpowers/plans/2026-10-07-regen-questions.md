# Ask Re-gen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Answer general and Re-gen questions in a separate local conversation.

**Architecture:** A read-only questions endpoint calls the existing Foundry
model with automatic question routing and required approved-knowledge Search
for programme answers.
The browser holds a bounded conversation separate from activity state.

**Tech Stack:** Existing FastAPI, Pydantic, Azure AI Projects/Responses, vanilla JS.

**Spec:** docs/superpowers/specs/2026-10-07-regen-questions-design.md

## Global Constraints

- Keep regen11, exact14 analysis, human-only decisions and required activity location unchanged.
- No new dependencies, persisted cloud agent versions or durable chat tables.
- Preserve earlier uncommitted Search/CLI edits through selective staging.
- Required completed Search on every programme turn; policy comes only from retrieved rules.
- Questions require no geolocation and never change submission records.
- Question max4000; history max12 messages/24000 characters, each max12000.

## Review Focus

- Ambiguous programme follow-ups or mixed everyday/programme questions retrieve fresh approved knowledge.
- Spoofed history roles and extra decision/location fields never reach action tools or storage.
- Failed, incomplete or empty provider replies cannot appear as successful answers.
- A late reply after navigation stays with its conversation and does not redirect or discard an activity draft.
- History trimming keeps complete pairs within both count and character limits.

### Task 1: Read-only question API and model gateway

**Files:** Create regen_api/questions.py and tests/test_questions.py; modify
regen_api/schemas.py, settings.py, foundry.py, main.py, tests/conftest.py.

**Interfaces:** Consumes FoundryGateway._get_client and safe_failure;
produces FoundryGateway.ask(QuestionInput) -> QuestionAnswer and POST /api/questions.

- [ ] Write tests for normal free-text answers, follow-ups with tool_choice required,
  bounds/invalid roles/extra fields, invalid routing JSON, explicit programme fallback,
  sanitized errors and zero record changes.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_questions.py`; expect FAIL on missing API/types.
- [ ] Implement typed request/response, direct model question handler and lazy cached
  Search tool from the existing project connection. Validate replies and HTTPS citations.
- [ ] Run question tests then whole suite; expect PASS.
- [ ] Commit only this task's files.

### Task 2: Ask Re-gen interface

**Files:** Create regen_api/static/questions.js and tests/browser_questions.cjs;
modify static/index.html, app.js, app.css and tests/test_web.py.

**Interfaces:** Consumes POST /api/questions; produces #ask navigation and
window-scoped in-memory conversation without geolocation/submission mutations.

- [ ] Write actual-script tests for normal and follow-up sends, complete-pair history
  trimming, duplicate suppression, draft retention on failure, navigation, reset
  and literal HTML rendering. Assert served Ask Re-gen assets.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_web.py`; expect FAIL for missing UI/script.
- [ ] Implement independent question state and composer, examples, source links,
  view-local progress, reset and #ask routing. Keep existing submission draft behavior.
- [ ] Run web tests and whole suite; expect PASS.
- [ ] Commit only this task's files.

### Task 3: Live validation and documentation

**Files:** Create docs/superpowers/2026-10-07-regen-questions-validation.md;
modify only question-specific INSTRUCTIONS.md hunks.

**Interfaces:** Consumes Tasks1/2 and existing authenticated localhost prototype.

- [ ] Run live question/follow-up checks for everyday facts, conservation, approved
  rules, unavailable programme policy and no authority to approve/reward.
- [ ] Inspect CUA inventory; if unavailable, record actual visual/hardware QA limit.
- [ ] Restart idle server and compare all records/original hashes; expect unchanged.
- [ ] Write local usage, API examples, history/privacy limits and evidence notes.
- [ ] Run whole suite, JS syntax and diff checks; expect PASS. Commit task files.
- [ ] Dispatch one fresh whole-change review; fix Important/Critical findings in one
  RED→GREEN pass, record rulings, retain branch/local server and remove only plan scratch.
