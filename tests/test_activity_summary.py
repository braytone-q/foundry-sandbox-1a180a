import json
import sqlite3

import pytest

from regen_api.foundry import AnalysisFailure, parse_response
from regen_api.store import Store
from tests.test_contract import payload, response
from tests.test_questions import use_question_gateway
from tests.test_api import create, review_body


def save(store, location='Nanyuki', quantity=300, activity_type='tree planting'):
    attempt = store.create('PRIVATE source must not reach Q&A', 'regen', '11')
    store.finish_attempt(attempt['attempt_id'], result=parse_response(response(payload() | {
        'location': location, 'quantity': quantity, 'activity_type': activity_type})))
    return store.get(attempt['id'])


def test_activity_totals_use_current_attempt_once_and_separate_status(tmp_path):
    store = Store(tmp_path / 'summary.sqlite3'); store.initialize()
    first = save(store)
    store.review(first['id'], type('Review', (), review_body(first))())
    pending = save(store, location=' nAnYuKi ', quantity=25, activity_type='tree_planting')
    another = save(store, quantity=10)
    missing = save(store, quantity=None)
    rejected = save(store, quantity=999)
    store.review(rejected['id'], type('Review', (), review_body(rejected, 'REJECT'))())
    waste = save(store, quantity=2.5, activity_type='waste collection')
    # A retry replaces the current report; it must not double the tree total.
    retry = store.begin_attempt(pending['id'], pending['version'], 'regen', '11')
    store.finish_attempt(retry['attempt_id'], result=parse_response(response(payload() | {
        'quantity': 25, 'location': 'NANYUKI', 'activity_type': 'tree_planting'})))
    summary = store.activity_summary()
    assert summary.total_submissions == 6 and summary.analyzed_submissions == 6
    groups = {(g.activity_type, g.review_status): g for g in summary.totals}
    assert groups[('tree_planting', 'APPROVED')].reported_quantity == 300
    assert groups[('tree_planting', 'PENDING_REVIEW')].reported_quantity == 35
    assert groups[('tree_planting', 'PENDING_REVIEW')].quantified_submissions == 2
    assert groups[('tree_planting', 'PENDING_REVIEW')].unquantified_submissions == 1
    assert groups[('tree_planting', 'REJECTED')].reported_quantity == 999
    assert groups[('waste_collection', 'PENDING_REVIEW')].reported_quantity == 2.5
    assert len(summary.totals) == 4
    assert {g.location.casefold() for g in summary.totals} == {'nanyuki'}


def test_failed_latest_attempt_and_revision_do_not_reuse_old_quantity(tmp_path):
    store = Store(tmp_path / 'revision.sqlite3'); store.initialize()
    record = save(store)
    revision = store.begin_attempt(record['id'], record['version'], 'regen', '11', description='New source')
    store.finish_attempt(revision['attempt_id'], failure=AnalysisFailure('UPSTREAM_ERROR', 'Safe failure'))
    summary = store.activity_summary()
    assert summary.totals == []
    assert summary.total_submissions == 1
    assert summary.analyzed_submissions == 0 and summary.unavailable_analysis_submissions == 1


@pytest.mark.parametrize('needs_knowledge', [False, True])
def test_location_activity_context_reaches_every_question_stage_and_refreshes(app_bundle, needs_knowledge):
    client, app, gateway, _ = app_bundle
    gateway.data = payload() | {'activity_type': 'tree planting', 'quantity': 300, 'location': 'Nanyuki'}
    record = create(client, 'PRIVATE activity source and account details')
    client.post('/api/submissions/' + record['id'] + '/reviews', json=review_body(record))
    calls, _ = use_question_gateway(app_bundle, needs_knowledge=needs_knowledge, uses_project_brief=True)
    answer = client.post('/api/questions', json={'question': 'How many trees were planted in Nanyuki?'})
    assert answer.status_code == 200, answer.text
    for request in calls:
        summary = json.loads(request['instructions'].split('APP_ACTIVITY_SUMMARY_JSON: ')[1].splitlines()[0])
        assert summary['totals'][0]['location'] == 'Nanyuki'
        assert summary['totals'][0]['reported_quantity'] == 300
        assert summary['totals'][0]['review_status'] == 'APPROVED'
        assert 'PRIVATE' not in json.dumps(request)
        assert str(record['device_location']['latitude']) not in json.dumps(request)
        assert str(record['device_location']['longitude']) not in json.dumps(request)
    original_calls = len(calls)
    gateway.data = payload() | {'activity_type': 'tree_planting', 'quantity': 50, 'location': 'Nanyuki'}
    create(client)
    assert client.post('/api/questions', json={'question': 'And how many now?'}).status_code == 200
    summary = json.loads(calls[original_calls]['instructions'].split('APP_ACTIVITY_SUMMARY_JSON: ')[1].splitlines()[0])
    assert summary['total_submissions'] == 2
    assert {g['review_status']: g['reported_quantity'] for g in summary['totals']} == {'APPROVED': 300, 'PENDING_REVIEW': 50}


def test_empty_and_unquantified_activity_totals_are_not_fabricated(tmp_path):
    store = Store(tmp_path / 'empty.sqlite3'); store.initialize()
    assert store.activity_summary().totals == []
    save(store, location=None, quantity=None, activity_type=None)
    group = store.activity_summary().totals[0]
    assert group.location is None and group.activity_type is None
    assert group.reported_quantity == 0 and group.quantified_submissions == 0
    assert group.unquantified_submissions == 1


def test_activity_summary_database_failure_does_not_call_model(app_bundle, monkeypatch):
    client, app, _, _ = app_bundle
    calls, _ = use_question_gateway(app_bundle)
    def fail():
        raise sqlite3.OperationalError('private database path')
    monkeypatch.setattr(app.state.store, 'activity_summary', fail, raising=False)
    result = client.post('/api/questions', json={'question': 'How many trees in Nanyuki?'})
    assert result.status_code == 500 and calls == []
    assert 'private' not in result.text


@pytest.mark.parametrize('quantity', [None, -1])
def test_unusable_quantities_do_not_reduce_reported_total(tmp_path, quantity):
    store = Store(tmp_path / 'unusable.sqlite3'); store.initialize()
    save(store, quantity=300)
    save(store, quantity=quantity)
    total = store.activity_summary().totals[0]
    assert total.reported_quantity == 300
    assert total.quantified_submissions == 1 and total.unquantified_submissions == 1


def test_client_cannot_inject_activity_counts(app_bundle):
    client, _, _, _ = app_bundle
    calls, _ = use_question_gateway(app_bundle)
    result = client.post('/api/questions', json={'question': 'How many trees in Nanyuki?',
        'activity_summary': {'reported_quantity': 999999}})
    assert result.status_code == 422 and calls == []
