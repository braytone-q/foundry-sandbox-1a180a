from tests.location_fixtures import fresh_location
import shutil
import subprocess

import pytest


def test_browser_assets_are_served_without_azure(app_bundle):
    client, _, gateway, _ = app_bundle
    page = client.get("/")
    assert page.status_code == 200
    assert "Submit Activity" in page.text and "Review Queue" in page.text
    assert 'src="/static/app.js"' in page.text
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert gateway.descriptions == []
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_question_interface_assets_are_available_without_azure(client):
    assert 'Ask Re-gen' in client.get('/').text
    assert 'src="/static/questions.js"' in client.get('/').text
    assert client.get('/static/questions.js').status_code == 200


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for question UI checks")
@pytest.mark.parametrize('case', ['success', 'followup', 'duplicate', 'failure', 'navigation', 'reset', 'limits', 'examples', 'transport'])
def test_browser_questions(case):
    result = subprocess.run(['node', 'tests/browser_questions.cjs', case], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_image_picker_assets_and_blob_previews_are_served(client):
    page = client.get("/")
    assert 'src="/static/images.js"' in page.text
    assert client.get("/static/images.js").status_code == 200
    assert "img-src 'self' blob:" in page.headers["content-security-policy"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for browser image checks")
def test_browser_image_selection_and_multipart():
    result = subprocess.run(["node", "tests/browser_images.cjs"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for device-location checks")
def test_browser_location_capture():
    result = subprocess.run(["node", "tests/browser_location.cjs"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_source_script_markup_round_trips_as_data(client):
    source = '<script>alert("untrusted")</script>'
    response = client.post("/api/submissions", json={"device_location": fresh_location(), "description": source})
    assert response.json()["description"] == source
    assert source not in client.get("/").text


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for browser response-ordering checks")
@pytest.mark.parametrize("case", ["refresh", "filters", "confirmation", "image_draft", "image_comparison", "location", "location_denied", "location_navigation"])
def test_browser_response_ordering(case):
    result = subprocess.run(["node", "tests/browser_races.cjs", case], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
