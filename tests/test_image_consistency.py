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
    gateway = FoundryGateway(Settings());calls=[]
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
    calls=[];gateway=FoundryGateway(Settings())
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


def test_failed_second_call_keeps_source_and_originals(app_bundle):
    client,_,gateway,settings=app_bundle
    real=FoundryGateway(settings)
    def call(**kw):
        if "model" in kw:return vision_response()
        raise TimeoutError("private details")
    real._client=NS(responses=NS(create=call));gateway.analyze=real.analyze
    record=upload(client).json()
    assert record["latest_attempt"]["state"]=="FAILED"
    assert record["latest_attempt"]["analysis"] is None
    assert "private" not in record["latest_attempt"]["failure_message"]
    assert client.get(record["images"][0]["url"]).content==picture()
