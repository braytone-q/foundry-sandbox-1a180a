import json
from types import SimpleNamespace as NS

import pytest

from regen_api.foundry import AnalysisFailure, FoundryGateway
from regen_api.settings import Settings
from tests.test_activity import extraction_response, facts
from tests.test_contract import payload, response
from tests.test_image_consistency import descriptors, vision_response


def gateway_for(results):
    calls = []
    iterator = iter(results)
    def call(**kw):
        calls.append(kw)
        result = next(iterator)
        if isinstance(result, Exception):
            raise result
        return result
    gateway = FoundryGateway(Settings())
    gateway._client = NS(responses=NS(create=call))
    return gateway, calls


def test_text_only_order_grounding_and_exact_contract():
    gateway, calls = gateway_for([extraction_response(), response()])
    traces = []
    result = gateway.analyze('quoted "activity"', on_orchestration_trace=traces.append)
    assert len(calls) == 2
    assert calls[0]['model'] == 'gpt-5-mini'
    assert calls[1]['tool_choice'] == 'required'
    assert calls[1]['extra_body']['agent_reference']['version'] == '11'
    assert json.dumps('quoted "activity"') in calls[1]['input'][0]['content'][0]['text']
    assert 'input_image' not in json.dumps(calls[1])
    assert result.analysis.quantity == 150
    assert len(result.analysis.model_dump()) == 14
    assert result.analysis.evidence_received == []
    assert result.response_id == 'response-test'
    assert [s.role for s in result.orchestration_trace.stages] == ['activity', 'evidence', 'rules']
    assert [s.state for s in result.orchestration_trace.stages] == ['SUCCEEDED', 'SKIPPED', 'SUCCEEDED']
    assert [len(t.stages) for t in traces] == [1, 2, 3]
    assert traces[0].stages[0].findings.quantity == 150


@pytest.mark.parametrize('changes,expected', [
    ({'quantity': 300}, 'FLAG_FOR_REVIEW'),
    ({'quantity': None}, 'READY_FOR_HUMAN_REVIEW'),
    ({'species': 'invented oak'}, 'FLAG_FOR_REVIEW'),
    ({'activity_type': 'waste_collection'}, 'FLAG_FOR_REVIEW'),
])
def test_disagreements_cannot_overwrite_reported_facts(changes, expected):
    gateway, _ = gateway_for([extraction_response(), response(payload() | changes)])
    result = gateway.analyze('reported activity')
    assert result.analysis.quantity == 150
    assert result.analysis.species is None
    assert result.analysis.activity_type == 'tree_planting'
    assert result.analysis.recommendation == expected
    assert bool(result.analysis.inconsistencies) == (expected == 'FLAG_FOR_REVIEW')


@pytest.mark.parametrize('verdict,expected', [
    ('UNRELATED', 'FLAG_FOR_REVIEW'), ('UNCLEAR', 'FLAG_FOR_REVIEW'),
    ('SUPPORTS', 'READY_FOR_HUMAN_REVIEW'),
])
def test_image_guards_and_canonical_receipts(tmp_path, verdict, expected):
    gateway, calls = gateway_for([extraction_response(), vision_response((verdict,)),
        response(payload() | {'evidence_received': ['invented verified image'],
                              'evidence_reported': ['invented report']})])
    assessments = []
    result = gateway.analyze('reported', descriptors(tmp_path), on_image_assessment=assessments.append)
    assert result.analysis.recommendation == expected
    assert result.analysis.evidence_received == ['Image 1: test-0.png']
    assert result.analysis.evidence_reported == ['3 photos reported']
    assert len(assessments) == 1
    assert result.image_assessment.images[0].image_id == '0'
    assert 'input_image' in json.dumps(calls[1])
    assert 'input_image' not in json.dumps(calls[2])
    assert result.orchestration_trace.stages[1].findings.overall in {'MISMATCH', 'INCONCLUSIVE', 'SUPPORTS'}


@pytest.mark.parametrize('stage,code', [
    ('activity', 'INVALID_ACTIVITY_EXTRACTION'),
    ('rules', 'RETRIEVAL_MISSING'),
    ('provider', 'UPSTREAM_ERROR'),
])
def test_required_stage_failure_stops_calls_and_retains_safe_trace(stage, code):
    outputs = ([extraction_response(status='incomplete')] if stage == 'activity' else
        [extraction_response(), response(retrieval=False)] if stage == 'rules' else
        [RuntimeError('private bearer-token')])
    gateway, calls = gateway_for(outputs)
    traces = []
    with pytest.raises(AnalysisFailure) as exc:
        gateway.analyze('reported', on_orchestration_trace=traces.append)
    assert exc.value.code == code
    assert len(calls) == len(outputs)
    assert traces[-1].stages[-1].state == 'FAILED'
    assert traces[-1].stages[-1].failure_code == code
    assert 'private' not in traces[-1].model_dump_json()
    if stage == 'rules':
        assert traces[-1].stages[0].findings.quantity == 150


def test_vision_failure_retains_activity_and_skips_rules(tmp_path):
    gateway, calls = gateway_for([extraction_response(), vision_response(())])
    traces = []
    with pytest.raises(AnalysisFailure) as exc:
        gateway.analyze('reported', descriptors(tmp_path), on_orchestration_trace=traces.append)
    assert exc.value.code == 'INVALID_IMAGE_INSPECTION'
    assert len(calls) == 2
    assert traces[-1].stages[-1].role == 'evidence'
    assert traces[-1].stages[-1].state == 'FAILED'


def test_single_agent_still_uses_only_grounded_call():
    calls = []
    gateway = FoundryGateway(Settings(analysis_mode='single_agent'))
    gateway._client = NS(responses=NS(create=lambda **kw: calls.append(kw) or response()))
    result = gateway.analyze('reported')
    assert len(calls) == 1 and calls[0]['tool_choice'] == 'required'
    assert result.orchestration_trace is None
