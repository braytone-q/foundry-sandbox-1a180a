import json
from types import SimpleNamespace as NS

import pytest

from regen_api.foundry import AnalysisFailure, FoundryGateway
from regen_api.settings import Settings
from tests.test_contract import payload, response
from tests.test_images import picture, upload


def vision_response(verdicts=("UNRELATED",)):
    return NS(status="completed", id="vision-test", output_text=json.dumps({"images": [
        {"image_number": n + 1, "verdict": verdict,
         "visible_content": "A recruitment poster with text and inset photographs.",
         "explanation": "This poster does not demonstrate the described planting event."}
        for n, verdict in enumerate(verdicts)]}))


def descriptors(tmp_path, count=1):
    result = []
    for n in range(count):
        path = tmp_path / f"{n}.png"; path.write_bytes(picture())
        result.append({"id": str(n), "filename": f"test-{n}.png", "path": path})
    return result


@pytest.mark.parametrize("verdicts,overall,wanted", [
    (("UNRELATED",), "MISMATCH", "FLAG_FOR_REVIEW"),
    (("CONTRADICTS",), "MISMATCH", "FLAG_FOR_REVIEW"),
    (("SUPPORTS", "UNRELATED"), "MISMATCH", "FLAG_FOR_REVIEW"),
    (("UNCLEAR",), "INCONCLUSIVE", "FLAG_FOR_REVIEW"),
    (("SUPPORTS", "UNCLEAR"), "INCONCLUSIVE", "FLAG_FOR_REVIEW"),
    (("SUPPORTS", "SUPPORTS"), "SUPPORTS", "READY_FOR_HUMAN_REVIEW"),
])
def test_image_inspection_cannot_be_overridden_by_ready_agent(tmp_path, verdicts, overall, wanted):
    gateway = FoundryGateway(Settings(analysis_mode="single_agent"));calls=[]
    def call(**kw):
        calls.append(kw)
        return vision_response(verdicts) if "model" in kw else response()
    gateway._client = NS(responses=NS(create=call))
    result = gateway.analyze("Today we planted 300 trees.", descriptors(tmp_path, len(verdicts)))
    assert result.analysis.recommendation == wanted
    assert result.analysis.activity_type == "tree_planting"  # Still a reported classification.
    assert result.image_assessment.overall == overall
    assert [i.image_id for i in result.image_assessment.images] == [str(i) for i in range(len(verdicts))]
    assert calls[1]["tool_choice"] == "required"
    assert "input_image" in json.dumps(calls[0]) and "input_image" not in json.dumps(calls[1])
    if overall == "MISMATCH":
        assert result.analysis.inconsistencies and "poster" in result.analysis.reason.lower()
    if overall == "INCONCLUSIVE":
        assert not result.analysis.inconsistencies  # Uncertainty is not a fabricated contradiction.


@pytest.mark.parametrize("kind", ["missing", "duplicate", "out_of_range", "blank", "bad_json", "failed"])
def test_invalid_vision_coverage_fails_before_grounded_agent(tmp_path, kind):
    r=vision_response(("SUPPORTS", "SUPPORTS"));d=json.loads(r.output_text)
    if kind=="missing":d["images"].pop()
    elif kind=="duplicate":d["images"][1]["image_number"]=1
    elif kind=="out_of_range":d["images"][1]["image_number"]=3
    elif kind=="blank":d["images"][0]["visible_content"]=" "
    elif kind=="failed":r.status="incomplete"
    r.output_text="no JSON" if kind=="bad_json" else json.dumps(d)
    calls=[];gateway=FoundryGateway(Settings(analysis_mode="single_agent"))
    gateway._client=NS(responses=NS(create=lambda **kw: calls.append(kw) or r))
    with pytest.raises(AnalysisFailure):gateway.analyze("Planted trees",descriptors(tmp_path,2))
    assert len(calls)==1


def test_inspection_is_persisted_on_attempt_and_retry(app_bundle):
    client,_,gateway,settings=app_bundle
    real=FoundryGateway(settings)
    real._client=NS(responses=NS(create=lambda **kw: vision_response() if "model" in kw else response()))
    gateway.analyze=real.analyze
    first=upload(client).json()
    assert first["latest_attempt"]["image_assessment"]["overall"]=="MISMATCH"
    retried=client.post(f'/api/submissions/{first["id"]}/analyze',json={"expected_version":first["version"]}).json()
    assert len(retried["attempts"])==2
    assert retried["attempts"][1]["image_assessment"]==first["latest_attempt"]["image_assessment"]
    assert retried["review_status"]=="PENDING_REVIEW" and not retried["reviews"]


@pytest.mark.parametrize("failure_kind,failure_code", [
    ("timeout", "TIMEOUT"), ("retrieval", "RETRIEVAL_MISSING"),
    ("invalid", "INVALID_ANALYSIS"),
])
def test_failed_second_call_keeps_source_originals_and_inspection(app_bundle, failure_kind, failure_code):
    client,_,gateway,settings=app_bundle
    real=FoundryGateway(settings)
    def call(**kw):
        if "model" in kw:return vision_response()
        if failure_kind == "timeout":raise TimeoutError("private details")
        if failure_kind == "retrieval":return response(retrieval=False)
        return response(payload() | {"reason": " "})
    real._client=NS(responses=NS(create=call));gateway.analyze=real.analyze
    record=upload(client).json()
    assert record["latest_attempt"]["state"]=="FAILED"
    assert record["latest_attempt"]["analysis"] is None
    assert record["latest_attempt"]["failure_code"] == failure_code
    assessment = record["latest_attempt"]["image_assessment"]
    assert assessment is not None
    assert assessment["overall"] == "MISMATCH" and assessment["response_id"] == "vision-test"
    assert assessment["images"][0]["image_id"] == record["images"][0]["id"]
    assert record["latest_attempt"]["device_location"] == record["device_location"]
    assert "private" not in record["latest_attempt"]["failure_message"]
    assert client.get(record["images"][0]["url"]).content==picture()
    assert client.post(f'/api/submissions/{record["id"]}/reviews', json={
        "action": "APPROVE", "reviewer_name": "Test verifier", "notes": "Must remain blocked.",
        "expected_version": record["version"],
    }).status_code == 409


def test_restart_between_vision_and_search_keeps_completed_inspection(app_bundle):
    from fastapi.testclient import TestClient
    from regen_api.main import create_app
    from tests.conftest import ControlledGateway

    class SimulatedProcessStop(BaseException):
        pass

    client, app, gateway, settings = app_bundle
    original = upload(client).json()
    attempt = app.state.store.begin_attempt(original["id"], original["version"], "regen", "11")
    real = FoundryGateway(settings)
    observed = []
    def call(**kw):
        if "model" in kw:return vision_response()
        observed.append(app.state.store.get(original["id"])["latest_attempt"])
        raise SimulatedProcessStop()
    real._client = NS(responses=NS(create=call));gateway.analyze = real.analyze
    with pytest.raises(SimulatedProcessStop):
        app.state.service._analyze(attempt)
    assert observed[0]["state"] == "RUNNING"
    assert observed[0]["image_assessment"] is not None
    with TestClient(create_app(settings, ControlledGateway()), base_url="http://127.0.0.1") as restarted:
        recovered = restarted.get(f'/api/submissions/{original["id"]}').json()
        latest = recovered["latest_attempt"]
        assert latest["failure_code"] == "INTERRUPTED" and latest["analysis"] is None
        assert latest["image_assessment"] == observed[0]["image_assessment"]
        assert latest["image_assessment"]["overall"] == "MISMATCH"
        assert recovered["device_location"] == original["device_location"]
        assert restarted.get(original["images"][0]["url"]).content == picture()


def test_saved_agent_uses_supported_request_and_actual_receipt_strings(tmp_path):
    gateway=FoundryGateway(Settings(analysis_mode="single_agent"))
    def call(**kwargs):
        if 'model' in kwargs:return vision_response()
        # Foundry rejects runtime text-format overrides when agent_reference is supplied.
        assert 'text' not in kwargs
        return response(payload() | {'evidence_received':[{'filename':'invented.jpg','verified':True}]})
    gateway._client=NS(responses=NS(create=call))
    result=gateway.analyze('Today we planted 300 trees',descriptors(tmp_path))
    assert result.analysis.recommendation=='FLAG_FOR_REVIEW'
    assert result.analysis.evidence_received==['Image 1: test-0.png']
    assert len(result.analysis.model_dump())==14
