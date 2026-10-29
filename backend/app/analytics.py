import math
import os
from collections import defaultdict
from datetime import timedelta

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from .analytics_metrics import heatmap, learner_metrics, quality, video_summary
from .data_policy import policy, pseudonym, purge
from .db import AuthSession, Event, Feedback, IngestionRecord, LearningSession, Resource, User, now


class PolicyInput(BaseModel):
    retention_days: int = Field(ge=1, le=3650)
    enabled: bool


def install_analytics(app, db_session, current_user):
    def admin(user=Depends(current_user)):
        if user.role != 'admin':
            raise HTTPException(403, 'Accès administrateur requis')
        return user

    def event_window(db, days, maximum=100000):
        end = now()
        start = end - timedelta(days=days)
        events = list(db.scalars(select(Event).where(Event.received_at >= start, Event.received_at <= end).order_by(Event.received_at, Event.event_id).limit(maximum + 1)))
        if len(events) > maximum:
            raise HTTPException(413, f'Plus de {maximum} événements : choisissez une période plus courte')
        return start, end, events

    @app.get('/admin/analytics')
    def overview(days: int = Query(30, ge=1, le=3650), user=Depends(admin), db=Depends(db_session)):
        start, end, events = event_window(db, days)
        sessions = list(db.scalars(select(LearningSession).where(LearningSession.created_at >= start, LearningSession.created_at <= end)))
        receipts = list(db.scalars(select(IngestionRecord).where(IngestionRecord.received_at >= start, IngestionRecord.received_at <= end)))
        by_resource, sessions_by_resource = defaultdict(list), defaultdict(list)
        for e in events:
            by_resource[e.resource_id].append(e)
        for session in sessions:
            sessions_by_resource[session.resource_id].append(session)
        resources = list(db.scalars(select(Resource).where(Resource.kind == 'video').order_by(Resource.title)))
        return {'from': start.isoformat(), 'to': end.isoformat(), 'videos': [video_summary(r, by_resource[r.id], sessions_by_resource[r.id]) for r in resources], 'quality': quality(events, receipts), 'definitions': {'completion_threshold': .9, 'time_basis': 'received_at', 'receipt_scope': 'Lots valides reçus depuis la version 0.3 ; erreurs HTTP 401/413/422 exclues'}}

    @app.get('/admin/analytics/videos/{id_}')
    def video(id_: str, days: int = Query(30, ge=1, le=3650), user=Depends(admin), db=Depends(db_session)):
        resource = db.get(Resource, id_)
        if not resource or resource.kind != 'video':
            raise HTTPException(404, 'Vidéo introuvable')
        # Restrict before loading, so a busy unrelated resource cannot block this view.
        start, end = now() - timedelta(days=days), now()
        events = list(db.scalars(select(Event).where(Event.resource_id == id_, Event.received_at >= start, Event.received_at <= end).order_by(Event.received_at, Event.event_id).limit(100001)))
        if len(events) > 100000:
            raise HTTPException(413, 'Choisissez une période plus courte')
        return {'resource_id': id_, 'title': resource.title, **heatmap(events, resource.duration)}

    @app.get('/admin/analytics/learners')
    def learners(days: int = Query(30, ge=1, le=3650), user=Depends(admin), db=Depends(db_session)):
        start, end, events = event_window(db, days)
        grouped = defaultdict(list)
        for event in events:
            grouped[event.user_id].append(event)
        key = policy(db).pseudonym_key
        db.commit()
        return [{'participant': pseudonym(key, 'participant', id_), 'events': len(rows), 'sessions': len({e.session_id for e in rows}), 'resources': len({e.resource_id for e in rows}), 'last_activity': max(e.received_at for e in rows).isoformat()} for id_, rows in sorted(grouped.items())]

    @app.get('/admin/analytics/learners/{participant}')
    def learner_detail(participant: str, days: int = Query(30, ge=1, le=3650), user=Depends(admin), db=Depends(db_session)):
        start, end, events = event_window(db, days)
        key = policy(db).pseudonym_key
        db.commit()
        selected = [e for e in events if pseudonym(key, 'participant', e.user_id) == participant]
        if not selected:
            raise HTTPException(404, 'Participant sans activité sur cette période')
        grouped = defaultdict(list)
        for event in selected:
            grouped[event.resource_id].append(event)
        resources = {r.id: r for r in db.scalars(select(Resource).where(Resource.id.in_(grouped)))}
        return {'participant': participant, 'resources': [{'resource_id': id_, 'title': resources[id_].title, 'kind': resources[id_].kind, **learner_metrics(rows, resources[id_].duration), 'sessions': len({e.session_id for e in rows}), 'last_activity': max(e.received_at for e in rows).isoformat()} for id_, rows in grouped.items()], 'history': [{'type': e.event_type, 'resource_id': e.resource_id, 'position_seconds': e.position_seconds, 'received_at': e.received_at.isoformat()} for e in selected[-200:]], 'history_truncated': len(selected) > 200}

    @app.get('/admin/exports')
    def export(days: int = Query(30, ge=1, le=3650), user=Depends(admin), db=Depends(db_session)):
        start, end, events = event_window(db, days, maximum=50000)
        key = policy(db).pseudonym_key
        resources = list(db.scalars(select(Resource).where(Resource.id.in_({e.resource_id for e in events}))))
        def safe_payload(payload):
            clean = {k: v for k, v in payload.items() if k in ('from_seconds', 'to_seconds', 'from_rate', 'to_rate') and type(v) in (int, float) and math.isfinite(v)}
            if type(payload.get('visible')) is bool:
                clean['visible'] = payload['visible']
            if payload.get('reason') in ('user', 'resume'):
                clean['reason'] = payload['reason']
            return clean
        data = {'schema_version': 1, 'from': start.isoformat(), 'to': end.isoformat(), 'time_basis': 'received_at', 'pseudonymization': 'HMAC-SHA256, key held in database; pseudonymized, not anonymous', 'events': [{'event': pseudonym(key, 'event', e.event_id), 'participant': pseudonym(key, 'participant', e.user_id), 'session': pseudonym(key, 'session', e.session_id), 'resource_id': e.resource_id, 'sequence': e.sequence, 'event_type': e.event_type, 'occurred_at': e.occurred_at.isoformat(), 'received_at': e.received_at.isoformat(), 'position_seconds': e.position_seconds, 'payload': safe_payload(e.payload)} for e in events], 'resources': [{'resource_id': r.id, 'kind': r.kind, 'duration': r.duration, 'archived': r.archived} for r in resources]}
        db.commit()
        return data

    @app.get('/admin/data-policy')
    def get_policy(user=Depends(admin), db=Depends(db_session)):
        row = policy(db)
        result = {'retention_days': row.retention_days, 'enabled': row.enabled}
        db.commit()
        return result

    @app.put('/admin/data-policy')
    def update_policy(data: PolicyInput, user=Depends(admin), db=Depends(db_session)):
        row = policy(db)
        row.retention_days, row.enabled = data.retention_days, data.enabled
        db.commit()
        return data.model_dump()

    @app.get('/admin/data-policy/preview')
    def preview(user=Depends(admin), db=Depends(db_session)):
        row = policy(db)
        result = purge(db, row.retention_days)
        db.commit()
        return result

    @app.post('/admin/data-policy/purge')
    def purge_now(user=Depends(admin), db=Depends(db_session)):
        row = policy(db)
        result = purge(db, row.retention_days, execute=True)
        db.commit()
        return result

    @app.get('/admin/participants')
    def participants(user=Depends(admin), db=Depends(db_session)):
        key = policy(db).pseudonym_key
        rows = list(db.scalars(select(User).where(User.role == 'learner').order_by(User.email)))
        result = [{'id': row.id, 'email': row.email, 'participant': pseudonym(key, 'participant', row.id), 'bootstrap': row.email == os.getenv('DEMO_EMAIL', '').lower()} for row in rows]
        db.commit()
        return result

    @app.delete('/admin/participants/{id_}')
    def delete_participant(id_: str, user=Depends(admin), db=Depends(db_session)):
        row = db.get(User, id_)
        if not row:
            raise HTTPException(404, 'Compte introuvable')
        if row.role != 'learner':
            raise HTTPException(403, 'La suppression des administrateurs est exclue de cette action')
        if row.email == os.getenv('DEMO_EMAIL', '').lower():
            raise HTTPException(409, 'Retirez DEMO_EMAIL et DEMO_PASSWORD de la configuration avant de supprimer le compte de démonstration, pour éviter sa recréation')
        for model in (Event, Feedback, IngestionRecord, LearningSession, AuthSession):
            db.execute(delete(model).where(model.user_id == id_))
        db.delete(row)
        db.commit()
        return {'deleted': True}
