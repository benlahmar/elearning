import hashlib
import math
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .db import AuthSession, Course, Event, Feedback, LearningSession, Resource, User, database, now
from .metrics import coverage
from .seed import seed
from .migrate import migrate
from .admin import install_admin
from .storage import get_storage

passwords = PasswordHash.recommended()
dummy_hash = passwords.hash('invalid-password-placeholder')


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class Profile(BaseModel):
    interests: list[str] = Field(max_length=12)

    @field_validator('interests')
    @classmethod
    def clean(cls, values):
        if any(not v.strip() or len(v) > 80 for v in values):
            raise ValueError('Centres d’intérêt invalides')
        return list(dict.fromkeys(v.strip() for v in values))


class InputEvent(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    schema_version: Literal[1] = 1
    event_id: uuid.UUID
    session_id: uuid.UUID
    sequence: int = Field(ge=1)
    resource_id: str = Field(max_length=100)
    event_type: Literal['play', 'playing', 'pause', 'seek', 'rate_change', 'heartbeat', 'waiting', 'visibility_change', 'ended', 'resource_download']
    occurred_at: datetime
    position_seconds: float = Field(ge=0)
    payload: dict = Field(default_factory=dict)

    @field_validator('occurred_at')
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError('Fuseau horaire requis')
        return value


class Batch(BaseModel):
    events: list[InputEvent] = Field(min_length=1, max_length=100)


class FeedbackInput(BaseModel):
    useful: bool | None = None
    favorite: bool = False


def public_resource(r):
    return {key: getattr(r, key) for key in ['id', 'title', 'description', 'topic', 'level', 'kind', 'duration', 'url', 'tags', 'course_id', 'archived']}


def create_app(database_url=None):
    engine, sessions = database(database_url)

    @asynccontextmanager
    async def lifespan(app):
        migrate(engine)
        with sessions() as db:
            seed(db)
        yield
        engine.dispose()

    app = FastAPI(title='Learning Recsys Lab', lifespan=lifespan)
    app.state.sessions = sessions

    @app.middleware('http')
    async def body_limit(request, call_next):
        if request.method in ('POST', 'PUT', 'PATCH') and not (request.method == 'PUT' and request.url.path.endswith('/content')):
            # Read a bounded stream, including requests without Content-Length.
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 262144:
                    from starlette.responses import JSONResponse
                    return JSONResponse({'detail': 'Requête trop volumineuse'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        return await call_next(request)

    def db_session():
        with sessions() as db:
            yield db

    def current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)), db=Depends(db_session)):
        if not credentials:
            raise HTTPException(401, 'Connexion requise')
        auth = db.get(AuthSession, hashlib.sha256(credentials.credentials.encode()).hexdigest())
        if not auth or auth.expires_at.replace(tzinfo=timezone.utc) <= now():
            raise HTTPException(401, 'Session expirée')
        user = db.get(User, auth.user_id)
        if not user:
            raise HTTPException(401, 'Compte indisponible')
        return user

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/auth/login')
    def login(data: Login, db=Depends(db_session)):
        user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
        valid = passwords.verify(data.password, user.password_hash if user else dummy_hash)
        if not user or not valid:
            raise HTTPException(401, 'Identifiants incorrects')
        token = secrets.token_urlsafe(32)
        db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=now() + timedelta(hours=8)))
        db.commit()
        return {'access_token': token, 'token_type': 'bearer'}

    @app.post('/auth/logout', status_code=204)
    def logout(credentials=Depends(HTTPBearer()), user=Depends(current_user), db=Depends(db_session)):
        auth = db.get(AuthSession, hashlib.sha256(credentials.credentials.encode()).hexdigest())
        if auth:
            db.delete(auth)
            db.commit()

    @app.get('/me')
    def me(user=Depends(current_user)):
        return {'id': user.id, 'email': user.email, 'interests': user.interests, 'role': user.role}

    @app.patch('/me/profile')
    def profile(data: Profile, user=Depends(current_user), db=Depends(db_session)):
        user.interests = data.interests
        db.commit()
        return {'interests': user.interests}

    def visible():
        return (Resource.archived.is_(False), (Resource.url != '') | Resource.object_key.is_not(None), Resource.course_id.is_(None) | Resource.course_id.in_(select(Course.id).where(Course.archived.is_(False))))

    @app.get('/courses')
    def courses(user=Depends(current_user), db=Depends(db_session)):
        return [{'id': c.id, 'title': c.title, 'description': c.description} for c in db.scalars(select(Course).where(Course.archived.is_(False)).order_by(Course.title))]

    @app.get('/resources')
    def resources(q: str = '', topic: str = '', kind: str = '', course_id: str = '', offset: int = 0, limit: int = 20, user=Depends(current_user), db=Depends(db_session)):
        query = select(Resource).where(*visible())
        if q:
            query = query.where(Resource.title.ilike('%' + q[:100] + '%'))
        if topic:
            query = query.where(Resource.topic == topic)
        if course_id:
            query = query.where(Resource.course_id == course_id)
        if kind:
            query = query.where(Resource.kind == kind)
        return [public_resource(r) for r in db.scalars(query.order_by(Resource.id).offset(max(0, offset)).limit(min(100, max(1, limit))))]

    def resource_or_404(db, id_):
        resource = db.get(Resource, id_)
        if not resource or resource.archived or (not resource.url and not resource.object_key) or (resource.course_id and db.get(Course, resource.course_id).archived):
            raise HTTPException(404, 'Ressource introuvable')
        return resource

    @app.get('/resources/{id_}/access-url')
    def access_url(id_: str, user=Depends(current_user), db=Depends(db_session)):
        resource = resource_or_404(db, id_)
        return {'url': get_storage().access_url(resource.object_key) if resource.object_key else resource.url, 'expires_in': 300 if resource.object_key else None}

    @app.post('/resources/{id_}/sessions')
    def start_session(id_: str, user=Depends(current_user), db=Depends(db_session)):
        resource_or_404(db, id_)
        session = LearningSession(id=str(uuid.uuid4()), user_id=user.id, resource_id=id_)
        db.add(session)
        db.commit()
        return {'session_id': session.id}

    @app.get('/resources/{id_}/progress')
    def progress(id_: str, user=Depends(current_user), db=Depends(db_session)):
        resource = resource_or_404(db, id_)
        events = list(db.scalars(select(Event).where(Event.user_id == user.id, Event.resource_id == id_).order_by(Event.occurred_at, Event.sequence)))
        intervals = [(e.payload['from_seconds'], e.payload['to_seconds']) for e in events if e.event_type == 'heartbeat']
        return {**coverage(intervals, resource.duration), 'position_seconds': events[-1].position_seconds if events else 0, 'event_count': len(events)}

    @app.post('/events/batch')
    def ingest(data: Batch, user=Depends(current_user), db=Depends(db_session)):
        results = []
        for event in data.events:
            id_ = str(event.event_id)
            session = db.get(LearningSession, str(event.session_id))
            resource = db.get(Resource, event.resource_id)
            if not session or session.user_id != user.id or session.resource_id != event.resource_id or not resource:
                results.append({'event_id': id_, 'status': 'rejected', 'reason': 'Session ou ressource inaccessible'})
                continue
            if db.get(Event, id_):
                results.append({'event_id': id_, 'status': 'duplicate'})
                continue
            error = None
            if event.position_seconds > resource.duration + 2:
                error = 'Position hors limites'
            p = event.payload
            if event.event_type in ('heartbeat', 'seek'):
                a, b = p.get('from_seconds'), p.get('to_seconds')
                if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > resource.duration + 2 for v in (a, b)):
                    error = 'Intervalle invalide'
                elif event.event_type == 'heartbeat' and (b < a or b - a > 60):
                    error = 'Intervalle de lecture invalide'
            if event.event_type == 'rate_change' and any(type(p.get(k)) not in (int, float) or not math.isfinite(p[k]) or not 0.25 <= p[k] <= 4 for k in ('from_rate', 'to_rate')):
                error = 'Vitesse invalide'
            if error:
                results.append({'event_id': id_, 'status': 'rejected', 'reason': error})
                continue
            try:
                with db.begin_nested():
                    db.add(Event(event_id=id_, user_id=user.id, resource_id=event.resource_id, session_id=str(event.session_id), sequence=event.sequence, event_type=event.event_type, occurred_at=event.occurred_at, position_seconds=event.position_seconds, payload=p))
                    db.flush()
                status = 'accepted'
            except IntegrityError:
                status = 'duplicate'
            results.append({'event_id': id_, 'status': status})
        db.commit()
        return {'results': results}

    @app.put('/resources/{id_}/feedback')
    def feedback(id_: str, data: FeedbackInput, user=Depends(current_user), db=Depends(db_session)):
        resource_or_404(db, id_)
        row = db.scalar(select(Feedback).where(Feedback.user_id == user.id, Feedback.resource_id == id_))
        if not row:
            row = Feedback(user_id=user.id, resource_id=id_)
            db.add(row)
        row.useful, row.favorite = data.useful, data.favorite
        db.commit()
        return data.model_dump()

    @app.get('/resources/{id_}/feedback')
    def get_feedback(id_: str, user=Depends(current_user), db=Depends(db_session)):
        resource_or_404(db, id_)
        row = db.scalar(select(Feedback).where(Feedback.user_id == user.id, Feedback.resource_id == id_))
        return {'useful': row.useful if row else None, 'favorite': row.favorite if row else False}

    @app.get('/recommendations')
    def recommendations(algorithm: Literal['popular', 'content'] = 'content', user=Depends(current_user), db=Depends(db_session)):
        resources = list(db.scalars(select(Resource).where(*visible())))
        # Count distinct learners, not raw play/pause frequency.
        popularity = dict(db.execute(select(Event.resource_id, func.count(func.distinct(Event.user_id))).group_by(Event.resource_id)).all())
        interests = set(re.findall(r'\w+', ' '.join(user.interests).lower()))
        def score(resource):
            words = set(re.findall(r'\w+', ' '.join([resource.title, resource.topic, *resource.tags]).lower()))
            return len(interests & words) / max(1, len(interests | words)) if algorithm == 'content' and interests else popularity.get(resource.id, 0)
        ranked = sorted(resources, key=lambda r: (-score(r), r.id))[:6]
        return {'algorithm': algorithm, 'version': '1', 'items': [{**public_resource(r), 'reason': 'Selon vos intérêts' if algorithm == 'content' and interests else 'À découvrir dans le catalogue'} for r in ranked]}

    install_admin(app, db_session, current_user)
    return app


app = create_app()
