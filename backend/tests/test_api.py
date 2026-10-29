from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from app.db import User
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DEMO_EMAIL', 'demo@example.com')
    monkeypatch.setenv('DEMO_PASSWORD', 'test-password-long-enough')
    app = create_app('sqlite:///' + str(tmp_path / 'test.db'))
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer ' + client.post('/auth/login', json={'email': 'demo@example.com', 'password': 'test-password-long-enough'}).json()['access_token']
        yield client


def make_event(session, start=0, end=30, **changes):
    return {'schema_version': 1, 'event_id': str(uuid4()), 'session_id': session, 'sequence': 1, 'resource_id': 'video-1', 'event_type': 'heartbeat', 'occurred_at': datetime.now(timezone.utc).isoformat(), 'position_seconds': end, 'payload': {'from_seconds': start, 'to_seconds': end}, **changes}


def test_events_idempotent_and_coverage_ignores_seek_and_repetition(client):
    session = client.post('/resources/video-1/sessions').json()['session_id']
    events = [make_event(session, 0, 30), make_event(session, 30, 90, event_type='seek', sequence=2), make_event(session, 90, 120, sequence=3), make_event(session, 120, 100, event_type='seek', sequence=4), make_event(session, 100, 120, sequence=5)]
    assert all(r['status'] == 'accepted' for r in client.post('/events/batch', json={'events': events}).json()['results'])
    assert all(r['status'] == 'duplicate' for r in client.post('/events/batch', json={'events': events}).json()['results'])
    progress = client.get('/resources/video-1/progress').json()
    assert progress['covered_seconds'] == 60
    assert progress['event_count'] == 5
    assert progress['coverage'] == pytest.approx(60 / 596.5)


def test_isolation_and_no_user_spoofing(client):
    session = client.post('/resources/video-1/sessions').json()['session_id']
    with client.app.state.sessions() as db:
        db.add(User(id='other', email='other@example.com', password_hash=PasswordHash.recommended().hash('another-test-password'), interests=[]))
        db.commit()
    token = client.post('/auth/login', json={'email': 'other@example.com', 'password': 'another-test-password'}).json()['access_token']
    client.headers['Authorization'] = 'Bearer ' + token
    result = client.post('/events/batch', json={'events': [make_event(session)]}).json()
    assert result['results'][0]['status'] == 'rejected'
    assert client.get('/resources/video-1/progress').json()['event_count'] == 0
    assert client.post('/events/batch', json={'events': [make_event(session, user_id='victim')]}).status_code == 422


def test_validation_partial_rejection_and_logout(client):
    session = client.post('/resources/video-1/sessions').json()['session_id']
    result = client.post('/events/batch', json={'events': [make_event(session, 0, 700), make_event(session)]}).json()
    assert [r['status'] for r in result['results']] == ['rejected', 'accepted']
    assert client.post('/events/batch', json={'events': [make_event(session)] * 101}).status_code == 422
    assert client.post('/auth/logout').status_code == 204
    assert client.get('/resources').status_code == 401


def test_login_failure_profile_search_and_feedback(client):
    assert client.post('/auth/login', json={'email': 'demo@example.com', 'password': 'incorrect'}).status_code == 401
    assert len(client.get('/resources?kind=file').json()) == 1
    assert client.get('/resources?q=missing').json() == []
    assert client.patch('/me/profile', json={'interests': ['collaboratif']}).status_code == 200
    assert client.get('/recommendations?algorithm=content').json()['items'][0]['id'] == 'file-1'
    assert client.put('/resources/video-1/feedback', json={'favorite': True, 'useful': True}).status_code == 200
    assert client.get('/resources/video-1/feedback').json() == {'favorite': True, 'useful': True}
    assert client.get('/resources/unknown/progress').status_code == 404


def test_bounded_body(client):
    assert client.post('/events/batch', content=b'x' * 262145).status_code == 413
