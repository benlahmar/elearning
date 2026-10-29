import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.data_policy import scheduled_purge
from app.db import AuthSession, Event, Feedback, IngestionRecord, LearningSession, Resource, User, now
from test_api import client, make_event


def promote(client):
    with client.app.state.sessions() as db:
        db.scalar(select(User).where(User.email == 'demo@example.com')).role = 'admin'
        db.commit()


def test_metrics_heatmap_export_and_quality(client):
    promote(client)
    session = client.post('/resources/video-1/sessions').json()['session_id']
    with client.app.state.sessions() as db:
        db.get(Resource, 'video-1').duration = 120
        db.add(User(id='second', email='second@example.com', password_hash='unused', interests=[]))
        db.flush()
        db.add(LearningSession(id='second-session', user_id='second', resource_id='video-1'))
        db.commit()
    events = [make_event(session, 0, 30, payload={'from_seconds':0,'to_seconds':30,'note':'demo@example.com'}), make_event(session, 30, 90, event_type='seek', sequence=2), make_event(session, 90, 120, sequence=3), make_event(session, 120, 100, event_type='seek', sequence=4), make_event(session, 100, 120, sequence=5)]
    assert client.post('/events/batch', json={'events': events}).status_code == 200
    client.post('/events/batch', json={'events': events})
    client.post('/events/batch', json={'events': [make_event(session, 0, 700)]})
    overview = client.get('/admin/analytics').json()
    video = next(v for v in overview['videos'] if v['resource_id']=='video-1')
    assert video['opens'] == 2
    assert video['learners'] == 2
    assert video['average_coverage'] == .25
    assert video['completion_rate'] == 0
    assert video['replayed_seconds'] == 20
    assert (video['backward_seeks'], video['forward_seeks']) == (1, 1)
    assert overview['quality']['accepted'] == 5
    assert overview['quality']['duplicate'] == 5
    assert overview['quality']['rejected'] == 1
    bins = client.get('/admin/analytics/videos/video-1').json()['bins']
    assert bins[0]['viewed_learners'] == 1
    assert bins[3]['viewed_learners'] == 0
    assert bins[3]['skipped_learners'] == 1
    assert bins[10]['replayed_learners'] == 1
    learners = client.get('/admin/analytics/learners').json()
    assert len(learners) == 1
    detail = client.get('/admin/analytics/learners/' + learners[0]['participant']).json()
    assert detail['resources'][0]['coverage'] == .5
    assert len(detail['history']) == 5
    exported = client.get('/admin/exports').json()
    assert len(exported['events']) == 5
    encoded = json.dumps(exported)
    assert 'demo@example.com' not in encoded
    assert 'password' not in encoded
    assert 'note' not in encoded
    assert session not in encoded
    assert events[0]['event_id'] not in encoded
    assert exported['events'][0]['participant'] == learners[0]['participant']
    assert exported['events'][0]['participant'] == client.get('/admin/exports').json()['events'][0]['participant']


def test_permissions(client):
    for path in ('/admin/analytics', '/admin/analytics/videos/video-1', '/admin/analytics/learners', '/admin/exports', '/admin/data-policy', '/admin/data-policy/preview', '/admin/participants'):
        assert client.get(path).status_code == 403
    assert client.put('/admin/data-policy', json={'retention_days': 1,'enabled':True}).status_code == 403
    assert client.post('/admin/data-policy/purge').status_code == 403
    assert client.delete('/admin/participants/unknown').status_code == 403
    promote(client)
    settings = client.get('/admin/data-policy').json()
    assert settings == {'retention_days':90,'enabled':False}
    assert client.put('/admin/data-policy', json={'retention_days':0,'enabled':True}).status_code == 422
    assert client.get('/admin/analytics?days=0').status_code == 422


def test_purge_uses_received_time_and_preserves_recent_sessions(client):
    promote(client)
    old = now() - timedelta(days=10)
    user_id = client.get('/me').json()['id']
    with client.app.state.sessions() as db:
        db.add_all([LearningSession(id='old-session', user_id=user_id, resource_id='video-1', created_at=old), LearningSession(id='active-session',user_id=user_id,resource_id='video-1',created_at=old)])
        db.flush()
        for session, received in [('old-session',old),('active-session',now())]:
            db.add(Event(event_id=str(uuid4()),user_id=user_id,session_id=session,resource_id='video-1',sequence=1,event_type='play',position_seconds=0,payload={},occurred_at=old,received_at=received))
        db.add(IngestionRecord(user_id=user_id,received_at=old,accepted=1,duplicate=0,rejected=0))
        db.add(Feedback(user_id=user_id,resource_id='video-1',useful=True,favorite=True,updated_at=old))
        db.commit()
    assert client.put('/admin/data-policy',json={'retention_days':7,'enabled':False}).status_code == 200
    preview = client.get('/admin/data-policy/preview').json()['counts']
    assert preview['interaction_events'] == 1
    assert preview['learning_sessions'] == 1
    assert preview['feedback'] == 1
    assert client.get('/admin/analytics').json()['quality']['retained_events'] == 2
    # Disabled scheduling leaves eligible data intact.
    scheduled_purge(client.app.state.sessions)
    assert client.get('/admin/analytics').json()['quality']['retained_events'] == 2
    client.put('/admin/data-policy',json={'retention_days':7,'enabled':True})
    scheduled_purge(client.app.state.sessions)
    with client.app.state.sessions() as db:
        assert len(list(db.scalars(select(Event)))) == 1
        assert db.get(LearningSession, 'old-session') is None
        assert db.get(LearningSession, 'active-session') is not None
        assert not list(db.scalars(select(Feedback)))
    assert client.post('/admin/data-policy/purge').json()['counts']['interaction_events'] == 0


def test_participant_deletion_revokes_and_removes_data(client):
    promote(client)
    own_id = client.get('/me').json()['id']
    assert client.delete('/admin/participants/'+own_id).status_code == 403
    data = {'email':'delete@example.com','password':'long-delete-password'}
    participant = client.post('/admin/learners',json=data).json()
    admin_auth = client.headers['Authorization']
    token = client.post('/auth/login',json=data).json()['access_token']
    client.headers['Authorization'] = 'Bearer '+token
    session = client.post('/resources/video-1/sessions').json()['session_id']
    client.post('/events/batch',json={'events':[make_event(session)]})
    client.put('/resources/video-1/feedback',json={'favorite':True})
    client.headers['Authorization'] = admin_auth
    assert len(client.get('/admin/exports').json()['events']) == 1
    assert client.delete('/admin/participants/'+participant['id']).json()['deleted']
    assert client.get('/admin/exports').json()['events'] == []
    with client.app.state.sessions() as db:
        for model in (Event, Feedback, IngestionRecord, LearningSession, AuthSession):
            assert not list(db.scalars(select(model).where(model.user_id==participant['id'])))
        assert db.get(User,participant['id']) is None
    client.headers['Authorization'] = 'Bearer '+token
    assert client.get('/me').status_code == 401


def test_quality_sequence_and_clock_skew(client):
    promote(client)
    session = client.post('/resources/video-1/sessions').json()['session_id']
    old = (now()-timedelta(hours=1)).isoformat()
    client.post('/events/batch',json={'events':[make_event(session, occurred_at=old), make_event(session)]})
    result=client.get('/admin/analytics').json()['quality']
    assert result['duplicate_sequences'] == 1
    assert result['clock_skew_events'] == 1


def test_completion_threshold_resume_and_repeated_playback():
    from types import SimpleNamespace
    from app.analytics_metrics import learner_metrics
    events = [SimpleNamespace(event_type='heartbeat', payload={'from_seconds':0, 'to_seconds':60}), SimpleNamespace(event_type='heartbeat', payload={'from_seconds':60, 'to_seconds':108}), SimpleNamespace(event_type='seek', payload={'from_seconds':108, 'to_seconds':0, 'reason':'resume'})]
    result = learner_metrics(events, 120)
    assert result['coverage'] == .9
    assert result['completed'] is True
    assert result['backward_seeks'] == 0
    assert result['resume_seeks'] == 1
    assert result['replayed_seconds'] == 0
    assert learner_metrics(events, 121)['completed'] is False


def test_backward_seek_inside_one_segment_is_not_counted_as_skip():
    from types import SimpleNamespace
    from app.analytics_metrics import heatmap
    events = [SimpleNamespace(user_id='one', event_type='seek', payload={'from_seconds':17, 'to_seconds':12, 'reason':'user'}), SimpleNamespace(user_id='one', event_type='seek', payload={'from_seconds':0, 'to_seconds':20, 'reason':'resume'})]
    assert all(segment['skipped_learners'] == 0 for segment in heatmap(events, 20)['bins'])
