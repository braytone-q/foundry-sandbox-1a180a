"""Run the three Re-gen acceptance cases against an explicitly selected live version."""

import argparse
import json

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT = (
    "https://veloking45-8432-resource.services.ai.azure.com/"
    "api/projects/regen-agentic-ai"
)

CASES = [
    "We watered seedlings in the community nursery today.",
    "We planted 150 indigenous seedlings at Kiptapkei nursery today and attached three photos.",
    "Our group collected plastic waste from the river today.",
]

EXPECTED_KEYS = {
    "activity_type", "quantity", "species", "species_category", "activity_date",
    "location", "community_group", "evidence_reported", "evidence_received",
    "missing_information", "inconsistencies", "recommendation", "reason",
    "clarification_question",
}


def validate_case(number, response):
    assert response.status == "completed", response.status
    assert any(item.type == "azure_ai_search_call_output" for item in response.output), (
        "No Search tool result was received"
    )
    analysis = json.loads(response.output_text)
    assert set(analysis) == EXPECTED_KEYS, "Unexpected analysis schema"
    assert analysis["evidence_received"] == [], "No files were supplied"
    assert analysis["inconsistencies"] == [], "No conflicting facts were submitted"
    if number == 1:
        assert analysis["activity_type"] == "nursery_maintenance", analysis
        assert analysis["recommendation"] == "NEEDS_CLARIFICATION", analysis
        missing = analysis["missing_information"]
        assert len(missing) == 1 and "location" in missing[0].lower(), analysis
        question = analysis["clarification_question"]
        assert question and "quantity" not in question.lower(), analysis
    elif number == 2:
        assert analysis["activity_type"] == "tree_planting", analysis
        assert analysis["quantity"] == 150, analysis
        assert analysis["location"] and "kiptapkei" in analysis["location"].lower(), analysis
        assert analysis["recommendation"] == "READY_FOR_HUMAN_REVIEW", analysis
        assert analysis["missing_information"] == [], analysis
        assert analysis["evidence_reported"], analysis
    else:
        assert analysis["recommendation"] == "FLAG_FOR_REVIEW", analysis
        assert "no approved" in analysis["reason"].lower(), analysis
        assert analysis["missing_information"] == [], analysis
    return analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Live regen agent version to test")
    args = parser.parse_args()
    failures = 0
    with DefaultAzureCredential() as credential, AIProjectClient(
        endpoint=PROJECT_ENDPOINT, credential=credential
    ) as project:
        with project.get_openai_client() as client:
            for number, activity in enumerate(CASES, 1):
                try:
                    response = client.responses.create(
                        input=activity,
                        extra_body={"agent_reference": {
                            "name": "regen", "version": args.version,
                            "type": "agent_reference",
                        }},
                    )
                    analysis = validate_case(number, response)
                    print(f"PASS {number}: {analysis['recommendation']}")
                except (AssertionError, ValueError, KeyError) as exc:
                    failures += 1
                    print(f"FAIL {number}: {exc}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
