import json
import sqlite3
import shutil
import subprocess
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from regen_api.foundry import AnalysisFailure, FoundryGateway, parse_response
from regen_api.main import create_app
from regen_api.schemas import ActivityFacts, OrchestrationTrace, SpecialistStage
from regen_api.settings import Settings
from regen_api.store import Conflict, NotFound, Store
from tests.location_fixtures import fresh_location
from tests.test_activity import extraction_response, facts
from tests.test_contract import response
from tests.test_image_consistency import vision_response
from tests.test_images import parts


def trace():
    return OrchestrationTrace(stages=[SpecialistStage(role='activity', identity='test-model',
        response_id='extracted', state='SUCCEEDED', findings=ActivityFacts.model_validate(facts()))])


def test_legacy_migration_and_idempotent_reads(tmp_path):
    store = Store(tmp_path / 'legacy.sqlite3')
    store.initialize()
    attempt = store.create('Original', 'regen', '11')
    store.finish_attempt(attempt['attempt_id'], result=parse_response(response()))
    with sqlite3.connect(store.path) as db:
        columns = {row[1] for row in db.execute('PRAGMA table_info(analysis_attempts)')}
        if 'orchestration_trace_json' in columns:
            db.execute('ALTER TABLE analysis_attempts DROP COLUMN orchestration_trace_json')
    store.initialize()
    store.initialize()
    record = store.get(attempt['id'])
    assert record['description'] == 'Original'
    assert record['latest_attempt']['orchestration_trace'] is None
    assert record['latest_attempt']['analysis']['quantity'] == 150


def test_trace_binding_and_completed_attempt_rejection(tmp_path):
    store = Store(tmp_path / 'traces.sqlite3'); store.initialize()
    first = store.create('First', 'regen', '11')
    second = store.create('Second', 'regen', '11')
    store.save_orchestration_trace(second['attempt_id'], trace())
    assert store.get(first['id'])['latest_attempt']['orchestration_trace'] is None
    store.save_orchestration_trace(first['attempt_id'], trace())
    store.finish_attempt(first['attempt_id'], failure=AnalysisFailure('UPSTREAM_ERROR', 'Safe error'))
    assert store.get(first['id'])['latest_attempt']['orchestration_trace']['stages'][0]['findings']['quantity'] == 150
    with pytest.raises(Conflict):
        store.save_orchestration_trace(first['attempt_id'], trace())
    with pytest.raises(NotFound):
        store.save_orchestration_trace('missing', trace())
    store.finish_attempt(second['attempt_id'], result=parse_response(response()))
    assert store.get(second['id'])['latest_attempt']['orchestration_trace']['stages'][0]['response_id'] == 'extracted'


def multiagent_app(tmp_path, outputs):
    settings = Settings(database_path=tmp_path / 'api.sqlite3', analysis_mode='multiagent')
    gateway = FoundryGateway(settings)
    calls = []; iterator = iter(outputs)
    def call(**kw):
        calls.append(kw)
        result = next(iterator)
        if isinstance(result, Exception):
            raise result
        return result
    gateway._client = NS(responses=NS(create=call), close=lambda: None)
    return create_app(settings, gateway), calls


def test_failed_rules_retains_trace_and_retry_revision_history(tmp_path):
    app, calls = multiagent_app(tmp_path, [extraction_response(), RuntimeError('private bearer-token'),
        extraction_response(), response(), extraction_response(), response()])
    location = fresh_location()
    with TestClient(app, base_url='http://127.0.0.1') as client:
        result = client.post('/api/submissions', json={'description': 'Original source', 'device_location': location})
        assert result.status_code == 201, result.text
        record = result.json(); failed = record['latest_attempt']
        assert failed['state'] == 'FAILED' and failed['analysis'] is None
        assert [s['state'] for s in failed['orchestration_trace']['stages']] == ['SUCCEEDED', 'SKIPPED', 'FAILED']
        assert failed['orchestration_trace']['stages'][-1]['failure_code'] == 'UPSTREAM_ERROR'
        assert 'private' not in json.dumps(record)
        retried = client.post(f"/api/submissions/{record['id']}/analyze", json={'expected_version': record['version']}).json()
        assert retried['latest_attempt']['state'] == 'SUCCEEDED'
        revised = client.post(f"/api/submissions/{record['id']}/revisions", json={
            'description': 'Revised source', 'device_location': fresh_location(),
            'expected_version': retried['version']}).json()
        assert revised['current_revision'] == 2
        assert len(revised['attempts']) == 3
        assert revised['attempts'][-1]['orchestration_trace'] == failed['orchestration_trace']
        assert revised['review_status'] == 'PENDING_REVIEW' and revised['reviews'] == []
        assert revised['latest_attempt']['orchestration_trace']['stages'][0]['findings']['quantity'] == 150
        assert 'latitude' not in json.dumps(calls) and 'longitude' not in json.dumps(calls)
        assert calls[0]['input'][0]['content'] == calls[2]['input'][0]['content']
        assert 'Revised source' in calls[4]['input'][0]['content']
        saved = client.get(f"/api/submissions/{record['id']}").json()
        assert saved == revised


def test_image_failure_keeps_received_files_and_inspection_trace(tmp_path):
    app, _ = multiagent_app(tmp_path, [extraction_response(), vision_response(), response(retrieval=False)])
    with TestClient(app, base_url='http://127.0.0.1') as client:
        result = client.post('/api/submissions/with-images', data={
            'description': 'Reported planting', 'device_location': json.dumps(fresh_location())}, files=parts())
        assert result.status_code == 201, result.text
        record = result.json()
        attempt = record['latest_attempt']
        assert attempt['state'] == 'FAILED' and attempt['failure_code'] == 'RETRIEVAL_MISSING'
        assert attempt['image_assessment']['overall'] == 'MISMATCH'
        assert attempt['orchestration_trace']['stages'][1]['findings']['overall'] == 'MISMATCH'
        assert attempt['orchestration_trace']['stages'][-1]['state'] == 'FAILED'
        assert client.get(record['images'][0]['url']).status_code == 200


def test_single_agent_attempt_trace_is_null(client):
    record = client.post('/api/submissions', json={
        'description': 'Single-agent source', 'device_location': fresh_location()}).json()
    assert record['latest_attempt']['orchestration_trace'] is None


@pytest.mark.skipif(shutil.which('node') is None, reason='Node required for reviewer rendering checks')
def test_browser_orchestration():
    result = subprocess.run(['node', 'tests/browser_orchestration.cjs'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
