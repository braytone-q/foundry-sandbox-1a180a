import json
from types import SimpleNamespace as NS

import pytest
from pydantic import ValidationError


def payload():
    return dict(activity_type="tree_planting", quantity=150, species=None,
                species_category="indigenous", activity_date="today",
                location="Kiptapkei nursery", community_group=None,
                evidence_reported=["3 photos reported"], evidence_received=[],
                missing_information=[], inconsistencies=[],
                recommendation="READY_FOR_HUMAN_REVIEW", reason="Retrieved rule is complete.",
                clarification_question=None)


def response(data=None, retrieval=True):
    output = [NS(type="azure_ai_search_call_output", status="completed")] if retrieval else []
    output.append(NS(type="message", role="assistant", content=[NS(type="output_text",
        text=json.dumps(payload() if data is None else data), annotations=[])]))
    return NS(status="completed", id="response-test", output=output)


def test_accepts_existing_analysis_contract():
    from regen_api.schemas import Analysis
    assert Analysis.model_validate(payload()).recommendation == "READY_FOR_HUMAN_REVIEW"


@pytest.mark.parametrize("changes", [
    {"recommendation": "APPROVED"}, {"quantity": True}, {"quantity": "150"},
    {"evidence_received": [123]}, {"extra_decision": "APPROVE"},
    {"missing_information": ["location"]}, {"inconsistencies": ["100 versus 150"]},
    {"recommendation": "NEEDS_CLARIFICATION", "clarification_question": "Where?"},
    {"reason": "  "}, {"quantity": float("nan")},
])
def test_rejects_invalid_or_authoritative_analysis(changes):
    from regen_api.schemas import Analysis
    with pytest.raises(ValidationError):
        Analysis.model_validate(payload() | changes)


def test_missing_keys_are_not_manufactured():
    from regen_api.schemas import Analysis
    data = payload()
    del data["quantity"]
    with pytest.raises(ValidationError):
        Analysis.model_validate(data)


def test_generic_unknown_activity_can_be_flagged_without_contradictions():
    from regen_api.schemas import Analysis
    assert Analysis.model_validate(payload() | {
        "recommendation": "FLAG_FOR_REVIEW", "reason": "No approved rule found."
    }).recommendation == "FLAG_FOR_REVIEW"


def test_clarification_requires_a_question():
    from regen_api.schemas import Analysis
    with pytest.raises(ValidationError):
        Analysis.model_validate(payload() | {
            "recommendation": "NEEDS_CLARIFICATION", "missing_information": ["location"]
        })


def test_final_assistant_message_and_safe_citations_are_extracted():
    from regen_api.foundry import parse_response
    r = response()
    r.output.insert(0, NS(type="azure_ai_search_call", content=[NS(type="output_text", text='{"query":"rules"}')]))
    r.output[-1].content[0].annotations = [
        NS(type="url_citation", title="Rule", url="https://example.com/rule"),
        NS(type="url_citation", title="Unsafe", url="javascript:alert(1)"),
    ]
    result = parse_response(r)
    assert result.analysis.quantity == 150
    assert result.response_id == "response-test"
    assert [c.url for c in result.citations] == ["https://example.com/rule"]


@pytest.mark.parametrize("kind", ["no_search", "bad_json", "failed", "tool_error", "two_messages"])
def test_failed_or_ungrounded_responses_are_visible_failures(kind):
    from regen_api.foundry import AnalysisFailure, parse_response
    r = response(retrieval=kind != "no_search")
    if kind == "bad_json":
        r.output[-1].content[0].text = 'not JSON'
    elif kind == "failed":
        r.status = "incomplete"
    elif kind == "tool_error":
        r.output[0].error = {"message": "sensitive error"}
    elif kind == "two_messages":
        r.output.append(r.output[-1])
    with pytest.raises(AnalysisFailure) as exc:
        parse_response(r)
    assert "sensitive" not in exc.value.message


@pytest.mark.parametrize("model,data", [
    ("SubmissionInput", {"description": "   "}),
    ("SubmissionInput", {"description": "x" * 16001}),
    ("SubmissionInput", {"description": "planting", "decision": "APPROVE"}),
    ("ReviewInput", {"action": "APPROVE", "reviewer_name": " ", "notes": "ok", "expected_version": 1}),
    ("ReviewInput", {"action": "VERIFIED", "reviewer_name": "Human", "notes": "ok", "expected_version": 1}),
    ("ReviewInput", {"action": "APPROVE", "reviewer_name": "Human", "notes": " ", "expected_version": 1}),
    ("RetryInput", {"expected_version": True}),
])
def test_request_boundaries_reject_blank_extra_or_authoritative_inputs(model, data):
    if model == "SubmissionInput":
        from tests.location_fixtures import fresh_location
        data = data | {"device_location": fresh_location()}
    from regen_api import schemas
    with pytest.raises(ValidationError):
        getattr(schemas, model).model_validate(data)
def test_gateway_requires_knowledge_retrieval_before_analysis():
    from regen_api.foundry import FoundryGateway
    from regen_api.settings import Settings
    calls = []

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return response()

    gateway = FoundryGateway(Settings())
    gateway._client = NS(responses=Responses())
    result = gateway.analyze("We planted seedlings.")
    assert result.analysis.recommendation == "READY_FOR_HUMAN_REVIEW"
    assert calls[0]["tool_choice"] == "required"
