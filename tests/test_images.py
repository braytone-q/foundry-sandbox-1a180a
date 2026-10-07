import hashlib
import io
import struct
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.test_api import create, review_body


def picture(format="PNG", animated=False):
    out = io.BytesIO()
    image = Image.new("RGB", (12, 8), "#397c4c")
    options = {"save_all": True, "append_images": [Image.new("RGB", (12, 8), "red")]} if animated else {}
    image.save(out, format, **options)
    return out.getvalue()


def parts(number=1, blob=None, filename="photo.png", content_type="image/png"):
    return [("images", (f"{i}-{filename}", picture() if blob is None else blob, content_type)) for i in range(number)]


def upload(client, number=1, **kwargs):
    return client.post("/api/submissions/with-images", data={"description": "We planted seedlings and supplied photographs."},
                       files=parts(number, **kwargs))


def assert_no_records_or_files(app_bundle):
    client, _, gateway, settings = app_bundle
    assert client.get("/api/submissions", params={"status": "ALL"}).json()["total"] == 0
    assert gateway.descriptions == []
    assert not any(p.is_file() for p in (settings.database_path.parent / "evidence").rglob("*"))


def test_twenty_actual_images_are_saved_and_originals_are_served(app_bundle):
    client, _, _, _ = app_bundle
    result = upload(client, 20)
    assert result.status_code == 201, result.text
    record = result.json()
    assert record["review_status"] == "PENDING_REVIEW"
    assert len(record["images"]) == 20
    assert record["revisions"][0]["image_ids"] == record["latest_attempt"]["image_ids"]
    assert len(set(record["latest_attempt"]["image_ids"])) == 20
    image = record["images"][0]
    assert image["sha256"] == hashlib.sha256(picture()).hexdigest()
    assert image["width"] == 12 and image["height"] == 8 and image["size_bytes"] == len(picture())
    served = client.get(image["url"])
    assert served.status_code == 200 and served.content == picture()
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert "path" not in image and "stored_name" not in image
    assert client.get("/api/images/missing").status_code == 404


@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_file_type_is_verified_from_content(client, format, mime):
    result = upload(client, blob=picture(format), filename="arbitrary.txt", content_type="application/octet-stream")
    assert result.status_code == 201, result.text
    image = result.json()["images"][0]
    assert image["media_type"] == mime
    assert client.get(image["url"]).content == picture(format)


def test_twenty_one_images_is_rejected_as_a_whole(app_bundle):
    result = upload(app_bundle[0], 21)
    assert result.status_code == 422
    assert_no_records_or_files(app_bundle)


@pytest.mark.parametrize("blob,status", [(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', 415),
                                         (picture()[:-15], 422), (picture(animated=True), 415)])
def test_invalid_or_animated_batch_leaves_no_partial_submission(app_bundle, blob, status):
    client = app_bundle[0]
    result = client.post("/api/submissions/with-images", data={"description": "Source"},
                         files=parts() + parts(blob=blob))
    assert result.status_code == status, result.text
    assert_no_records_or_files(app_bundle)


def test_image_bytes_are_limited(app_bundle):
    result = upload(app_bundle[0], blob=picture() + b"x" * (8 * 1024 * 1024))
    assert result.status_code == 413
    assert_no_records_or_files(app_bundle)


@pytest.mark.parametrize("width,height", [(16001, 1), (6000, 6000)])
def test_decode_dimensions_are_limited_before_loading(app_bundle, width, height):
    data = bytearray(picture())
    data[16:24] = struct.pack(">II", width, height)
    data[29:33] = struct.pack(">I", zlib.crc32(data[12:29]))
    result = upload(app_bundle[0], blob=bytes(data))
    assert result.status_code == 422, result.text
    assert_no_records_or_files(app_bundle)


def test_filename_never_becomes_a_storage_path(client):
    result = client.post("/api/submissions/with-images", data={"description": "Source"},
                         files=[("images", ('../../<script>alert(1)</script>.png', picture(), "image/png"))])
    assert result.status_code == 201, result.text
    image = result.json()["images"][0]
    assert "/" not in image["filename"] and ".." not in image["filename"]
    assert client.get(image["url"]).content == picture()


def test_form_fields_and_origin_are_strict(app_bundle):
    client = app_bundle[0]
    assert client.post("/api/submissions/with-images", data={"description": "Source", "decision": "APPROVE"}, files=parts()).status_code == 422
    assert client.post("/api/submissions/with-images", data={"description": " "}, files=parts()).status_code == 422
    assert client.post("/api/submissions/with-images", data={"description": "Source"}, files=parts(),
                       headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/submissions", data={"description": "Source"}, files=parts()).status_code == 415
    assert_no_records_or_files(app_bundle)


def test_actual_body_bytes_are_limited_without_content_length(app_bundle, monkeypatch):
    from regen_api.main import create_app
    import regen_api.main as main
    client, _, gateway, settings = app_bundle
    monkeypatch.setattr(main, "MAX_UPLOAD_BODY_BYTES", 100)
    with TestClient(create_app(settings, gateway), base_url="http://127.0.0.1") as limited:
        body = b'--test\r\nContent-Disposition: form-data; name="description"\r\n\r\n' + b'x' * 300 + b'\r\n--test--\r\n'
        response = limited.post("/api/submissions/with-images", content=iter([body]),
                                headers={"Content-Type": "multipart/form-data; boundary=test"})
        assert response.status_code == 413, response.text
    assert_no_records_or_files(app_bundle)


def test_revisions_retry_and_restart_keep_exact_image_history(app_bundle):
    client, _, gateway, settings = app_bundle
    first = upload(client, 1).json()
    base = f'/api/submissions/{first["id"]}'
    second_response = client.post(base + "/revisions/with-images", data={"description": "Updated source", "expected_version": first["version"]}, files=parts(2))
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    assert len(second["images"]) == 3
    assert len(second["revisions"][0]["image_ids"]) == 1 and len(second["revisions"][1]["image_ids"]) == 3
    third = client.post(base + "/revisions", json={"description": "Text correction", "expected_version": second["version"]}).json()
    assert len(third["images"]) == 3
    retried = client.post(base + "/analyze", json={"expected_version": third["version"]}).json()
    assert retried["latest_attempt"]["image_ids"] == third["latest_attempt"]["image_ids"]
    from regen_api.main import create_app
    with TestClient(create_app(settings, gateway), base_url="http://127.0.0.1") as restarted:
        assert restarted.get(base).json() == retried
        for image in retried["images"]:
            assert restarted.get(image["url"]).content == picture()


def test_failed_analysis_keeps_images(app_bundle):
    client, _, gateway, _ = app_bundle
    gateway.failure = TimeoutError()
    response = upload(client)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["latest_attempt"]["state"] == "FAILED" and len(record["images"]) == 1
    assert client.get(record["images"][0]["url"]).content == picture()


def test_revision_count_stale_running_and_final_protection(app_bundle):
    client, app, _, _ = app_bundle
    record = upload(client, 20).json()
    base = f'/api/submissions/{record["id"]}'
    def revise(version):
        return client.post(base + "/revisions/with-images", data={"description": "Updated", "expected_version": version}, files=parts())
    assert revise(record["version"] - 1).status_code == 409
    assert revise(record["version"]).status_code == 422
    assert client.get(base).json() == record
    client.post(base + "/reviews", json=review_body(record))
    final = client.get(base).json()
    assert revise(final["version"]).status_code == 409
    separate = create(client)
    app.state.store.begin_attempt(separate["id"], separate["version"], "regen", "11")
    running = client.get(f'/api/submissions/{separate["id"]}').json()
    assert client.post(f'/api/submissions/{separate["id"]}/revisions/with-images',
                       data={"description": "Update", "expected_version": running["version"]}, files=parts()).status_code == 409


def test_failed_file_save_rolls_back_revision_and_preserves_earlier_files(app_bundle, monkeypatch):
    client, _, _, settings = app_bundle
    first = upload(client).json()
    original = Path.replace
    moves = 0
    def fail_second(self, target):
        nonlocal moves
        moves += 1
        if moves == 2:
            raise OSError("private storage path must not be exposed")
        return original(self, target)
    monkeypatch.setattr(Path, "replace", fail_second)
    response = client.post(f'/api/submissions/{first["id"]}/revisions/with-images',
                           data={"description": "Update", "expected_version": first["version"]}, files=parts(2))
    assert response.status_code == 500 and "private storage" not in response.text
    assert client.get(f'/api/submissions/{first["id"]}').json() == first
    assert client.get(first["images"][0]["url"]).content == picture()
    assert len([p for p in (settings.database_path.parent / "evidence").rglob("*") if p.is_file()]) == 1
