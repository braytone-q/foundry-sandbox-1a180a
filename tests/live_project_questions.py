"""Opt-in checks against the running app and real Foundry model.

Run explicitly: .venv/bin/python -m pytest -q -s tests/live_project_questions.py
These make paid model calls; default pytest discovery excludes this filename.
"""
import re
from collections import Counter

import httpx
import pytest


@pytest.fixture(scope="module")
def live_client():
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=180) as client:
        before = snapshot(client)
        yield client
        assert before == snapshot(client)


def snapshot(client):
    records = {}
    while True:
        response = client.get("/api/submissions", params={"status": "ALL", "limit": 100, "offset": len(records)})
        response.raise_for_status()
        page = response.json()
        for record in page["items"]:
            detail = client.get("/api/submissions/" + record["id"])
            detail.raise_for_status()
            records[record["id"]] = detail.json()
        if len(records) == page["total"]:
            return records
        assert page["items"], "Incomplete submission listing"


def ask(client, question, history=None):
    response = client.post("/api/questions", json={"question": question, "history": history or []})
    response.raise_for_status()
    result = response.json()
    print("\nQuestion:", question, "\nAnswer:", result["answer"], flush=True)
    return result


def test_project_overview_explains_the_current_local_workflow(live_client):
    result = ask(live_client, "What is this project for, and how do I use its current local prototype? "
                 "Name its navigation screens and explain who makes activity decisions.")
    answer = result["answer"].lower()
    assert "conservation" in answer or "environmental" in answer, result["answer"]
    for concept in ("submit activity", "ask re-gen", "review queue", "history", "human", "local"):
        assert concept in answer, f"Missing project fact: {concept}\n{result['answer']}"


def test_project_image_and_location_explanation_survives_a_followup(live_client):
    question = ("In Re-gen, what happens to uploaded images and my device coordinates? Explain whether "
                "actual pixels are inspected, what an unrelated photo causes, where original files "
                "and coordinates stay, and whether precise coordinates go to the AI service.")
    result = ask(live_client, question)
    answer = result["answer"].lower()
    for concept in ("pixel", "flag_for_review", "original", "local", "coordinates"):
        assert concept in answer, f"Missing project fact: {concept}\n{result['answer']}"
    assert re.search(r"\bcoordinates\s+(?:are\s+not|are\s+never|aren't|aren’t)\s+"
                     r"(?:sent|transmitted|shared)\b[^.!?\n]*\b(?:foundry|ai)\b", answer), result["answer"]
    followup = ask(live_client, "Can I continue if I deny that location permission?", [
        {"role": "user", "content": question}, {"role": "assistant", "content": result["answer"]},
    ])
    answer = followup["answer"].lower()
    assert any(term in answer for term in ("cannot", "can't", "can’t", "blocked", "blocks")), followup["answer"]
    assert "draft" in answer, followup["answer"]


def test_project_context_does_not_replace_approved_programme_rules(live_client):
    result = ask(live_client, "For Re-gen tree planting, is an exact species name mandatory? "
                 "Separately, how many images can the current app accept and is device location required?")
    answer = result["answer"].lower()
    assert result["knowledge_searched"]
    assert "optional" in answer and "20" in answer, result["answer"]
    assert "location" in answer and "required" in answer, result["answer"]


def test_undocumented_project_facts_are_not_invented(live_client):
    result = ask(live_client, "What are Re-gen's announced paid subscription prices and confirmed "
                 "public mobile-app launch date? Only give documented project facts.")
    assert any(term in result["answer"].lower() for term in
               ("not documented", "no documented", "not available", "don't have", "do not have", "not found", "found no")), result["answer"]
    assert "FLAG_FOR_REVIEW" not in result["answer"], result["answer"]
    assert result["citations"] == [], "Unrelated activity rules must not support undocumented pricing/launch facts"


def test_undocumented_programme_rules_still_need_human_review(live_client):
    result = ask(live_client, "What is the approved Re-gen mandatory drone-survey altitude "
                 "for verifying beach litter cleanup? If no approved rule exists, say so.")
    assert result["knowledge_searched"] and "FLAG_FOR_REVIEW" in result["answer"], result["answer"]


def test_everyday_questions_still_avoid_programme_citations(live_client):
    result = ask(live_client, "What is 17 multiplied by 6? Answer briefly.", [
        {"role": "user", "content": "How does Re-gen work?"},
        {"role": "assistant", "content": "Re-gen prepares conservation submissions for human review using approved rules."},
    ])
    assert "102" in result["answer"]
    assert not result["knowledge_searched"] and result["citations"] == []


def test_current_review_counts_are_answered_from_real_app_data(live_client):
    counts = Counter(record['review_status'] for record in snapshot(live_client).values())
    result = ask(live_client, 'How many activities are awaiting human review? Give the current '
                 'PENDING_REVIEW and CLARIFICATION_REQUESTED counts and the active Review Queue total.')
    answer = result['answer']
    for status in ('PENDING_REVIEW', 'CLARIFICATION_REQUESTED'):
        assert re.search(status + r'[^\d\n]{0,80}' + str(counts[status]) + r'\b', answer, re.I), answer
    active = counts['PENDING_REVIEW'] + counts['CLARIFICATION_REQUESTED']
    assert re.search(r'(?:active|queue)[^\d\n]{0,80}' + str(active) + r'\b', answer, re.I), answer
    assert not result['knowledge_searched'] and result['citations'] == []


def test_live_counts_override_an_old_refusal_in_conversation(live_client):
    pending = sum(record['review_status'] == 'PENDING_REVIEW' for record in snapshot(live_client).values())
    question = 'How many activities are awaiting human review?'
    result = ask(live_client, question, [
        {'role': 'user', 'content': question},
        {'role': 'assistant', 'content': "I can’t see live app data from here. To find how many activities "
         "are awaiting human review, open the Review Queue screen in the local app."},
    ])
    assert re.search(r'\b' + str(pending) + r'\b', result['answer']), result['answer']
    assert not result['knowledge_searched'] and result['citations'] == []
