import asyncio
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select
from starlette.concurrency import run_in_threadpool

from .db import AuthSession, DataPolicy, Event, Feedback, IngestionRecord, LearningSession, now


def policy(db):
    row = db.get(DataPolicy, 1)
    if row is None:
        row = DataPolicy(id=1, retention_days=90, enabled=False, pseudonym_key=secrets.token_hex(32))
        db.add(row)
        db.flush()
    return row


def pseudonym(key, kind, id_):
    digest = hmac.new(key.encode(), f'{kind}:{id_}'.encode(), hashlib.sha256).hexdigest()
    return kind + '_' + digest[:24]


def purge(db, days, execute=False):
    cutoff = now() - timedelta(days=days)
    conditions = [
        (Event, Event.received_at < cutoff),
        (IngestionRecord, IngestionRecord.received_at < cutoff),
        (Feedback, Feedback.updated_at < cutoff),
        (LearningSession, ((LearningSession.created_at < cutoff) | LearningSession.created_at.is_(None)) & ~LearningSession.id.in_(select(Event.session_id).where(Event.received_at >= cutoff))),
        (AuthSession, AuthSession.expires_at < now()),
    ]
    counts = {}
    for model, condition in conditions:
        counts[model.__tablename__] = db.scalar(select(func.count()).select_from(model).where(condition))
        if execute:
            db.execute(delete(model).where(condition))
    return {'cutoff': cutoff.isoformat(), 'counts': counts}


def scheduled_purge(sessions):
    with sessions() as db:
        settings = policy(db)
        if settings.enabled:
            purge(db, settings.retention_days, execute=True)
        db.commit()


async def retention_loop(sessions):
    while True:
        try:
            await run_in_threadpool(scheduled_purge, sessions)
        except Exception:
            logging.getLogger(__name__).exception('Échec de la purge périodique')
        await asyncio.sleep(3600)
