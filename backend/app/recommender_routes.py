from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from .db import Event, Resource
from .recommenders.base import ModelUnavailable
from .recommenders.registry import FAMILIES, REGISTRY, describe
from .recommenders.semantic import encoder
from .recommenders.service import recommend


class Preview(BaseModel):
    interests: list[str] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=6, ge=1, le=20)
    parameters: dict = Field(default_factory=dict)

    @field_validator('interests')
    @classmethod
    def valid_interests(cls, values):
        if any(len(v) > 80 or not v.strip() for v in values):
            raise ValueError('Centres d’intérêt invalides')
        return values


def install_recommenders(app, db_session, current_user, visible, public_resource):
    def admin(user=Depends(current_user)):
        if user.role != 'admin':
            raise HTTPException(403, 'Accès administrateur requis')
        return user

    def run(id_, interests, limit, parameters, db):
        if id_ not in REGISTRY:
            raise HTTPException(404, 'Algorithme inconnu')
        resources = list(db.scalars(select(Resource).where(*visible()).limit(5001)))
        counts = dict(db.execute(select(Event.resource_id, func.count(func.distinct(Event.user_id))).group_by(Event.resource_id)).all())
        try:
            result = recommend(id_, resources, interests, counts, limit, parameters)
        except ModelUnavailable as error:
            raise HTTPException(503, str(error))
        except ValueError as error:
            raise HTTPException(422, str(error))
        ranked = result.pop('ranked')
        result['items'] = [{**public_resource(r), 'score': score, 'reason': result['reason']} for r, score in ranked]
        return result

    @app.get('/algorithms')
    def available(user=Depends(current_user)):
        return {'families': FAMILIES, 'algorithms': [describe(row) for row in REGISTRY.values()]}

    @app.get('/recommendations')
    def recommendations(algorithm: str = 'tfidf', limit: int = Query(6, ge=1, le=20), user=Depends(current_user), db=Depends(db_session)):
        return run(algorithm, user.interests, limit, {}, db)

    @app.get('/admin/algorithms')
    def catalogue(user=Depends(admin)):
        return {'families': FAMILIES, 'algorithms': [describe(row) for row in REGISTRY.values()]}

    @app.get('/admin/algorithms/{id_}')
    def detail(id_: str, user=Depends(admin)):
        if id_ not in REGISTRY:
            raise HTTPException(404, 'Algorithme inconnu')
        return describe(REGISTRY[id_], include_source=True)

    @app.post('/admin/algorithms/{id_}/preview')
    def preview(id_: str, data: Preview, user=Depends(admin), db=Depends(db_session)):
        return run(id_, data.interests, data.limit, data.parameters, db)

    @app.post('/admin/semantic-model/prepare')
    def prepare(user=Depends(admin)):
        try:
            return encoder.prepare()
        except ModelUnavailable as error:
            raise HTTPException(503, str(error))

    @app.get('/admin/semantic-model')
    def model_status(user=Depends(admin)):
        return encoder.status()
