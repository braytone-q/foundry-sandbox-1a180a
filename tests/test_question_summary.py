import json
import sqlite3
from datetime import datetime, timezone

import pytest

from tests.location_fixtures import fresh_location
from tests.test_api import create, review_body
from tests.test_questions import use_question_gateway


def assert_counts(summary, total, pending, clarification, approved, rejected, active):
    data = summary.model_dump()
    captured = datetime.fromisoformat(data.pop('captured_at'))
    assert captured.utcoffset() is not None
    assert captured <= datetime.now(timezone.utc)
    assert data == dict(total_submissions=total, pending_human_review=pending,
                       awaiting_clarification=clarification, approved=approved,
                       rejected=rejected, active_review_queue=active)


def test_empty_database_has_real_zero_counts(app_bundle):
    _, app, _, _ = app_bundle
    assert_counts(app.state.store.review_summary(), 0, 0, 0, 0, 0, 0)


def test_summary_counts_current_human_status_once_per_submission(app_bundle):
    client, app, _, _ = app_bundle
    records = [create(client) for _ in range(5)]
    for record, action in zip(records[1:4], ['APPROVE', 'REJECT', 'REQUEST_CLARIFICATION']):
        result = client.post('/api/submissions/' + record['id'] + '/reviews', json=review_body(record, action))
        assert result.status_code == 201, result.text
    current = records[0]
    for _ in range(2):
        result = client.post('/api/submissions/' + current['id'] + '/analyze', json={'expected_version': current['version']})
        assert result.status_code == 200
        current = result.json()
    assert_counts(app.state.store.review_summary(), 5, 2, 1, 1, 1, 3)
    assert client.get('/api/submissions').json()['total'] == 3

    clarification = client.get('/api/submissions/' + records[3]['id']).json()
    result = client.post('/api/submissions/' + clarification['id'] + '/revisions', json={
        'description': 'Updated field description', 'device_location': fresh_location(),
        'expected_version': clarification['version'],
    })
    assert result.status_code == 201, result.text
    assert_counts(app.state.store.review_summary(), 5, 3, 0, 1, 1, 3)


@pytest.mark.parametrize('needs_knowledge', [False, True])
def test_fresh_server_counts_reach_every_answer_stage_without_source_details(app_bundle, needs_knowledge):
    client, _, _, _ = app_bundle
    record = create(client, 'PRIVATE activity description must not reach chat')
    location = record['device_location']
    calls, _ = use_question_gateway(app_bundle, needs_knowledge=needs_knowledge, uses_project_brief=True)
    assert client.post('/api/questions', json={'question': 'How many activities await human review?'}).status_code == 200
    first_count = len(calls)
    reviewed = client.post('/api/submissions/' + record['id'] + '/reviews', json=review_body(record)).json()
    assert client.post('/api/questions', json={'question': 'And how many now?'}).status_code == 200
    for group, pending, approved in [(calls[:first_count], 1, 0), (calls[first_count:], 0, 1)]:
        assert len(group) == (2 if needs_knowledge else 1)
        snapshots = []
        for request in group:
            summary = json.loads(request['instructions'].split('APP_REVIEW_SUMMARY_JSON: ')[1].splitlines()[0])
            assert summary['pending_human_review'] == pending and summary['approved'] == approved
            assert set(summary) == {'captured_at', 'total_submissions', 'pending_human_review',
                                    'awaiting_clarification', 'approved', 'rejected', 'active_review_queue'}
            assert 'PRIVATE activity description' not in json.dumps(request)
            assert str(location['latitude']) not in json.dumps(request)
            assert str(location['longitude']) not in json.dumps(request)
            snapshots.append(summary)
        assert all(summary == snapshots[0] for summary in snapshots)
    assert client.get('/api/submissions/' + record['id']).json() == reviewed


def test_client_cannot_supply_or_override_the_database_summary(app_bundle):
    client, _, _, _ = app_bundle
    calls, _ = use_question_gateway(app_bundle)
    result = client.post('/api/questions', json={'question': 'How many?', 'review_summary': {'pending_human_review': 999}})
    assert result.status_code == 422 and calls == []


def test_summary_failure_does_not_produce_invented_counts(app_bundle, monkeypatch):
    client, app, _, _ = app_bundle
    calls, _ = use_question_gateway(app_bundle)
    def fail():
        raise sqlite3.OperationalError('private storage details')
    monkeypatch.setattr(app.state.store, 'review_summary', fail, raising=False)
    result = client.post('/api/questions', json={'question': 'How many await review?'})
    assert result.status_code == 500 and calls == []
    assert 'private' not in result.text and 'answer' not in result.json()
