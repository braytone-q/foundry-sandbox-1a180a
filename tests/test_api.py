from tests.location_fixtures import fresh_location
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from regen_api.foundry import AnalysisFailure


def create(client, description="We planted 150 seedlings today at Kiptapkei and reported photos."):
    r = client.post("/api/submissions", json={"device_location": fresh_location(), "description": description})
    assert r.status_code == 201, r.text
    return r.json()


def review_body(record, action="APPROVE"):
    return dict(action=action, reviewer_name="Local test verifier", notes="Reviewed for API testing.",
                expected_version=record["version"])


def test_create_restore_and_openapi(app_bundle):
    client, app, gateway, settings = app_bundle
    record = create(client)
    assert record["review_status"] == "PENDING_REVIEW"
    assert record["latest_attempt"]["analysis"]["quantity"] == 150
    assert record["latest_attempt"]["agent_version"] == "11"
    from regen_api.main import create_app
    with TestClient(create_app(settings, gateway), base_url="http://127.0.0.1") as restarted:
        assert restarted.get(f'/api/submissions/{record["id"]}').json() == record
        assert restarted.get("/api/health").json()["status"] == "ready"
        assert "SubmissionRecord" in restarted.get("/openapi.json").json()["components"]["schemas"]


@pytest.mark.parametrize("recommendation", ["READY_FOR_HUMAN_REVIEW", "NEEDS_CLARIFICATION", "FLAG_FOR_REVIEW"])
def test_no_recommendation_can_make_a_human_decision(app_bundle, recommendation):
    client, _, gateway, _ = app_bundle
    gateway.data["recommendation"] = recommendation
    if recommendation == "NEEDS_CLARIFICATION":
        gateway.data.update(missing_information=["nursery location"], clarification_question="Where?")
    record = create(client)
    assert record["review_status"] == "PENDING_REVIEW"
    assert record["reviews"] == []


@pytest.mark.parametrize("action,status", [("APPROVE", "APPROVED"), ("REJECT", "REJECTED"),
                                           ("REQUEST_CLARIFICATION", "CLARIFICATION_REQUESTED")])
def test_explicit_review_is_durable_and_distinct_from_ai(client, action, status):
    record = create(client)
    r = client.post(f'/api/submissions/{record["id"]}/reviews', json=review_body(record, action))
    assert r.status_code == 201, r.text
    reviewed = r.json()
    assert reviewed["review_status"] == status
    assert reviewed["reviews"][0]["action"] == action
    assert reviewed["reviews"][0]["attempt_id"] == record["latest_attempt"]["id"]
    assert reviewed["latest_attempt"]["analysis"] == record["latest_attempt"]["analysis"]
    assert reviewed["version"] > record["version"]


def test_revision_preserves_history_and_sends_only_current_description(app_bundle):
    client, _, gateway, _ = app_bundle
    original = create(client, "Original field description")
    reviewed = client.post(f'/api/submissions/{original["id"]}/reviews',
                          json=review_body(original, "REQUEST_CLARIFICATION")).json()
    r = client.post(f'/api/submissions/{original["id"]}/revisions', json={
        "device_location": fresh_location(), "description": "Corrected complete description", "expected_version": reviewed["version"]})
    assert r.status_code == 201, r.text
    updated = r.json()
    assert updated["description"] == "Corrected complete description"
    assert gateway.descriptions[-1] == "Corrected complete description"
    assert len(updated["revisions"]) == 2 and len(updated["attempts"]) == 2
    assert updated["revisions"][0]["description"] == "Original field description"
    assert updated["reviews"][0]["revision"] == 1
    assert updated["latest_attempt"]["revision"] == 2
    assert updated["review_status"] == "PENDING_REVIEW"


def test_failed_attempt_is_saved_and_failed_retry_blocks_older_analysis(app_bundle):
    client, _, gateway, _ = app_bundle
    record = create(client)
    gateway.failure = RuntimeError("credential-secret must never reach the response")
    retried = client.post(f'/api/submissions/{record["id"]}/analyze',
                          json={"expected_version": record["version"]})
    assert retried.status_code == 200
    failed = retried.json()
    assert failed["latest_attempt"]["state"] == "FAILED"
    assert failed["latest_attempt"]["analysis"] is None
    assert "credential-secret" not in retried.text
    assert failed["description"] == record["description"]
    assert len(failed["attempts"]) == 2
    assert client.post(f'/api/submissions/{record["id"]}/reviews',
                       json=review_body(failed)).status_code == 409
    assert client.get("/api/submissions", params={"analysis_state": "FAILED"}).json()["total"] == 1
    assert client.get("/api/submissions", params={"recommendation": "READY_FOR_HUMAN_REVIEW"}).json()["total"] == 0
    gateway.failure = None
    success = client.post(f'/api/submissions/{record["id"]}/analyze',
                         json={"expected_version": failed["version"]}).json()
    assert success["latest_attempt"]["state"] == "SUCCEEDED"
    assert len(success["attempts"]) == 3


@pytest.mark.parametrize("failure", [TimeoutError(), AnalysisFailure("AUTHENTICATION", "Sign in to Azure."),
                                      AnalysisFailure("ACCESS_DENIED", "Check Search access.")])
def test_create_with_service_failure_keeps_source_and_no_recommendation(app_bundle, failure):
    client, _, gateway, _ = app_bundle
    gateway.failure = failure
    record = create(client, "Preserve this source")
    assert record["description"] == "Preserve this source"
    assert record["latest_attempt"]["state"] == "FAILED"
    assert record["latest_attempt"]["analysis"] is None
    assert record["reviews"] == []


def test_stale_and_final_mutations_are_rejected(client):
    record = create(client)
    base = f'/api/submissions/{record["id"]}'
    reviewed = client.post(base + "/reviews", json=review_body(record)).json()
    assert reviewed["review_status"] == "APPROVED"
    assert client.post(base + "/reviews", json=review_body(record, "REJECT")).status_code == 409
    assert client.post(base + "/reviews", json=review_body(reviewed, "REJECT")).status_code == 409
    assert client.post(base + "/analyze", json={"expected_version": reviewed["version"]}).status_code == 409
    assert client.post(base + "/revisions", json={"device_location": fresh_location(), "description": "changed", "expected_version": reviewed["version"]}).status_code == 409


def test_concurrent_final_decisions_do_not_overwrite(client):
    record = create(client)
    def act(action):
        return client.post(f'/api/submissions/{record["id"]}/reviews', json=review_body(record, action)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(act, ["APPROVE", "REJECT"])) == [201, 409]
    assert len(client.get(f'/api/submissions/{record["id"]}').json()["reviews"]) == 1


def test_running_attempt_blocks_mutations_and_restart_recovers(app_bundle):
    client, app, gateway, settings = app_bundle
    record = create(client)
    app.state.store.begin_attempt(record["id"], record["version"], "regen", "11")
    running = client.get(f'/api/submissions/{record["id"]}').json()
    assert running["latest_attempt"]["state"] == "RUNNING"
    for path, body in [("reviews", review_body(running)), ("analyze", {"expected_version": running["version"]}),
                       ("revisions", {"device_location": fresh_location(), "description": "changed", "expected_version": running["version"]})]:
        assert client.post(f'/api/submissions/{record["id"]}/{path}', json=body).status_code == 409
    from regen_api.main import create_app
    with TestClient(create_app(settings, gateway), base_url="http://127.0.0.1") as restarted:
        recovered = restarted.get(f'/api/submissions/{record["id"]}').json()
        assert recovered["latest_attempt"]["failure_code"] == "INTERRUPTED"
        assert recovered["version"] > running["version"]


def test_queue_filters_and_pagination(client):
    a = create(client, "first")
    b = create(client, "second")
    page = client.get("/api/submissions", params={"limit": 1}).json()
    assert page["total"] == 2 and page["items"][0]["id"] == b["id"]
    assert client.get("/api/submissions", params={"limit": 1, "offset": 1}).json()["items"][0]["id"] == a["id"]
    client.post(f'/api/submissions/{a["id"]}/reviews', json=review_body(a))
    assert client.get("/api/submissions").json()["total"] == 1
    assert client.get("/api/submissions", params={"status": "APPROVED"}).json()["total"] == 1
    assert client.get("/api/submissions", params={"status": "ALL"}).json()["total"] == 2
    assert client.get("/api/submissions", params={"limit": 101}).status_code == 422


def test_local_origin_host_and_content_type_boundaries(client):
    assert client.post("/api/submissions", json={"device_location": fresh_location(), "description": "x"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/submissions", content='{"description":"x"}', headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.post("/api/submissions", json={"device_location": fresh_location(), "description": "x"}, headers={"Origin": "http://127.0.0.1"}).status_code == 201
    assert client.post("/api/submissions", json={"device_location": fresh_location(), "description": "x", "decision": "APPROVE"}).status_code == 422
    assert client.get("/api/submissions/missing").status_code == 404


def test_public_hosts_require_demo_credentials(app_bundle):
    _, _, gateway, settings = app_bundle
    from regen_api.main import create_app

    public_settings = replace(settings, allowed_hosts=frozenset({"demo.example"}))
    with pytest.raises(ValueError, match="Public hosts require demo username and password"):
        create_app(public_settings, gateway)


def test_public_demo_requires_auth_and_allows_only_configured_host(app_bundle):
    _, _, gateway, settings = app_bundle
    from regen_api.main import create_app

    public_settings = replace(
        settings,
        allowed_hosts=frozenset({"demo.example"}),
        demo_username="presenter",
        demo_password="temporary-demo-password",
    )
    with TestClient(create_app(public_settings, gateway), base_url="https://demo.example") as public:
        denied = public.get("/")
        assert denied.status_code == 401
        assert denied.headers["www-authenticate"].startswith("Basic ")
        assert public.get("/", auth=("presenter", "incorrect-password")).status_code == 401
        assert public.get("/", auth=("presenter", "temporary-demo-password")).status_code == 200
        assert public.get("/api/health", headers={"Host": "attacker.example"},
                          auth=("presenter", "temporary-demo-password")).status_code == 400
        created = public.post(
            "/api/submissions",
            json={"device_location": fresh_location(), "description": "Class demo submission"},
            headers={"Origin": "https://demo.example"},
            auth=("presenter", "temporary-demo-password"),
        )
        assert created.status_code == 201, created.text


def test_no_azure_call_is_needed_for_health_or_queue(app_bundle):
    client, _, gateway, _ = app_bundle
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/submissions").json()["total"] == 0
    assert gateway.descriptions == []
