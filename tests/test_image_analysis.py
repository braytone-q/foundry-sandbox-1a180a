import base64
import hashlib
import io
from types import SimpleNamespace as NS

import pytest
from PIL import Image

from regen_api.foundry import AnalysisFailure, FoundryGateway, parse_response
from regen_api.settings import Settings
from tests.test_contract import payload, response
from tests.test_images import parts, picture, upload
from tests.test_image_consistency import vision_response


def test_twenty_saved_images_are_actual_response_inputs(tmp_path):
    calls = []
    gateway = FoundryGateway(Settings())
    gateway._client = NS(responses=NS(create=lambda **kw: calls.append(kw) or (vision_response(("SUPPORTS",) * 20) if "model" in kw else response())))
    images = []
    for number in range(20):
        path = tmp_path / f"{number}.png"
        path.write_bytes(picture())
        images.append({"id": str(number), "path": path, "filename": f"photo-{number}.png"})
    result = gateway.analyze("Test-only images; no activity occurred.", images)
    content = calls[0]["input"][0]["content"]
    actual = [part for part in content if part["type"] == "input_image"]
    assert len(actual) == 20 and calls[1]["tool_choice"] == "required"
    assert calls[1]["extra_body"]["agent_reference"]["version"] == "11"
    for part in actual:
        assert part["image_url"].startswith("data:image/jpeg;base64,")
        with Image.open(io.BytesIO(base64.b64decode(part["image_url"].split(",", 1)[1]))) as decoded:
            assert decoded.size == (12, 8) and decoded.mode == "RGB"
    assert result.analysis.evidence_received == [f"Image {i + 1}: photo-{i}.png" for i in range(20)]
    assert len(result.analysis.model_dump()) == 14


def test_normalized_image_orients_resizes_flattens_and_preserves_original(tmp_path):
    from regen_api.foundry import image_input
    path = tmp_path / "original.png"
    original = Image.new("RGBA", (3200, 1600), (0, 0, 0, 0))
    exif = Image.Exif()
    exif[274] = 6
    original.save(path, exif=exif)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    part = image_input({"path": path})
    with Image.open(io.BytesIO(base64.b64decode(part["image_url"].split(",", 1)[1]))) as decoded:
        assert decoded.size == (800, 1600) and decoded.mode == "RGB"
        assert min(decoded.getpixel((10, 10))) > 250
        assert not decoded.getexif()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_received_evidence_is_canonical_input_receipt():
    data = payload() | {"evidence_received": ["20 pictures prove date and quantity"]}
    result = parse_response(response(data), evidence_received=["Image 1: planted.png"])
    assert result.analysis.evidence_received == ["Image 1: planted.png"]
    assert result.analysis.evidence_reported == ["3 photos reported"]


def test_text_only_cannot_invent_received_evidence():
    with pytest.raises(AnalysisFailure) as exc:
        parse_response(response(payload() | {"evidence_received": ["photograph inspected"]}))
    assert exc.value.code == "INVALID_ANALYSIS"


def test_receipts_do_not_mask_invalid_analysis_or_missing_search():
    for r in [response(payload() | {"evidence_received": "not an array"}), response(retrieval=False)]:
        with pytest.raises(AnalysisFailure):
            parse_response(r, evidence_received=["Image 1: test.png"])


def test_current_revision_and_retry_supply_the_same_saved_images(app_bundle):
    client, _, gateway, _ = app_bundle
    first = upload(client, 2).json()
    base = f'/api/submissions/{first["id"]}'
    revised = client.post(base + "/revisions/with-images", data={"description": "Updated account", "expected_version": first["version"]}, files=parts()).json()
    latest = client.post(base + "/revisions", json={"description": "New words, same images", "expected_version": revised["version"]}).json()
    retried = client.post(base + "/analyze", json={"expected_version": latest["version"]}).json()
    assert len(gateway.image_batches[0]) == 2
    assert [image["id"] for image in gateway.image_batches[-1]] == retried["latest_attempt"]["image_ids"]
    assert gateway.image_batches[1] == gateway.image_batches[2] == gateway.image_batches[3]
    assert all(image["path"].read_bytes() == picture() for image in gateway.image_batches[-1])
    assert len(retried["latest_attempt"]["analysis"]["evidence_received"]) == 3


def test_provider_vision_failure_preserves_source_and_safe_message(app_bundle):
    client, _, gateway, settings = app_bundle
    real = FoundryGateway(settings)
    def fail(**kwargs):
        raise RuntimeError("private bearer-token and storage path")
    real._client = NS(responses=NS(create=fail))
    gateway.analyze = real.analyze
    record = upload(client).json()
    attempt = record["latest_attempt"]
    assert attempt["state"] == "FAILED" and attempt["analysis"] is None
    assert attempt["failure_code"] == "UPSTREAM_ERROR"
    assert "private" not in attempt["failure_message"]
    assert len(record["images"]) == 1 and client.get(record["images"][0]["url"]).content == picture()
