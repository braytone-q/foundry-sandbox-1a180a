import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tests.location_fixtures import fresh_location
from tests.test_images import parts, picture


@pytest.mark.parametrize("changes", [None, {"latitude":91.0}, {"longitude":-181.0}, {"accuracy_m":-1.0},
    {"latitude":"0.1"}, {"latitude":True}, {"source":"ip_address"}, {"latitude":float("inf")},
    {"captured_at":"2026-10-07T00:00:00"}, {"extra":"bad"}, {"captured_at":"yesterday"},
    {"captured_at":(datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat()},
    {"captured_at":(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()}])
def test_invalid_or_missing_fix_cannot_save_source(app_bundle, changes):
    client,_,gateway,settings=app_bundle
    body={"description":"Planted seedlings"}
    if changes is not None:body["device_location"]=fresh_location(**changes)
    # Use literal JSON serialization so nonfinite input exercises the server boundary.
    result=client.post('/api/submissions',content=json.dumps(body),headers={'Content-Type':'application/json'})
    assert result.status_code==422,result.text
    assert client.get('/api/submissions').json()['total']==0 and not gateway.descriptions


@pytest.mark.parametrize("location", [None, 'not JSON', '{}', '{"latitude":0}'])
def test_multipart_requires_valid_fix_before_image_storage(app_bundle, location):
    client,_,gateway,settings=app_bundle
    data={'description':'Planted seedlings'}
    if location is not None:data['device_location']=location
    result=client.post('/api/submissions/with-images',data=data,files=parts())
    assert result.status_code==422
    assert not gateway.descriptions
    assert not any(p.is_file() for p in (settings.database_path.parent/'evidence').rglob('*'))


def test_location_snapshots_current_revision_retry_and_restart(app_bundle):
    client,_,gateway,settings=app_bundle
    first_fix=fresh_location(latitude=-1.1,longitude=37.0)
    first=client.post('/api/submissions/with-images',data={'description':'Original source','device_location':json.dumps(first_fix)},files=parts()).json()
    assert first['device_location']==first_fix
    new_fix=fresh_location(latitude=-2.1,longitude=38.0)
    updated=client.post(f'/api/submissions/{first["id"]}/revisions',json={
        'description':'Updated source','expected_version':first['version'],'device_location':new_fix}).json()
    assert [r['device_location'] for r in updated['revisions']]==[first_fix,new_fix]
    retried=client.post(f'/api/submissions/{first["id"]}/analyze',json={'expected_version':updated['version']}).json()
    assert retried['device_location']==new_fix and retried['latest_attempt']['device_location']==new_fix
    assert retried['attempts'][-1]['device_location']==first_fix
    assert client.get(first['images'][0]['url']).content==picture()
    from regen_api.main import create_app
    with TestClient(create_app(settings,gateway),base_url='http://127.0.0.1') as restored:
        assert restored.get(f'/api/submissions/{first["id"]}').json()==retried


def test_legacy_source_has_no_invented_location(app_bundle):
    client,app,gateway,settings=app_bundle
    # Internal old-record creation deliberately has no location.
    attempt=app.state.store.create('Legacy source','regen','11')
    record=app.state.service._analyze(attempt)
    assert record['device_location'] is None
    assert record['revisions'][0]['device_location'] is None
    assert record['latest_attempt']['device_location'] is None
