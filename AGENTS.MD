# Re-gen Development Rules

## Product goal

Re-gen is an Agentic AI environmental activity verification system.

The AI prepares conservation activity submissions for human verification.

## Architecture

Microsoft Foundry Agent
→ Azure AI Search knowledge
→ structured environmental activity analysis
→ human verification

## Authority boundaries

The AI must never:

- approve activities
- reject activities
- mark activities verified
- issue Green Merit points
- issue tokens
- issue payments

These remain deterministic or human-controlled operations.

## Knowledge grounding

Verification requirements must come from the approved Re-gen knowledge source.

Do not hard-code new programme requirements into prompts unless explicitly requested.

If no rule exists, use `FLAG_FOR_REVIEW`.

## Evidence

Separate:

- `evidence_reported`
- `evidence_received`

Never claim to inspect evidence that was not actually supplied.

## Output schema

```json
{
  "activity_type": null,
  "quantity": null,
  "species": null,
  "species_category": null,
  "activity_date": null,
  "location": null,
  "community_group": null,
  "evidence_reported": [],
  "evidence_received": [],
  "missing_information": [],
  "inconsistencies": [],
  "recommendation": "",
  "reason": "",
  "clarification_question": null
}