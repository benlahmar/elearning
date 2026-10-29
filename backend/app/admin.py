import tempfile
import uuid

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from .db import Course, Resource, User
from .storage import get_storage


class CourseInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=5000)
    archived: bool = False


class ResourceInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=5000)
    topic: str = Field(min_length=1, max_length=100)
    level: str = Field(min_length=1, max_length=100)
    kind: str = Field(pattern='^(video|file)$')
    duration: float = Field(ge=0, le=86400)
    tags: list[str] = Field(default_factory=list, max_length=20)
    course_id: str
    archived: bool = False


class LearnerInput(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12, max_length=256)


def install_admin(app, db_session, current_user):
    def admin(user=Depends(current_user)):
        if user.role != 'admin':
            raise HTTPException(403, 'Accès administrateur requis')
        return user

    def course(db, id_):
        row = db.get(Course, id_)
        if not row:
            raise HTTPException(404, 'Cours introuvable')
        return row

    def resource(db, id_):
        row = db.get(Resource, id_)
        if not row:
            raise HTTPException(404, 'Ressource introuvable')
        return row

    def course_json(row):
        return {k: getattr(row, k) for k in ('id', 'title', 'description', 'archived')}

    def resource_json(row):
        return {**{k: getattr(row, k) for k in ('id', 'title', 'description', 'topic', 'level', 'kind', 'duration', 'tags', 'course_id', 'archived')}, 'ready': bool(row.url or row.object_key)}

    @app.get('/admin/courses')
    def courses(user=Depends(admin), db=Depends(db_session)):
        return [course_json(c) for c in db.scalars(select(Course).order_by(Course.title))]

    @app.post('/admin/courses', status_code=201)
    def create_course(data: CourseInput, user=Depends(admin), db=Depends(db_session)):
        row = Course(id=str(uuid.uuid4()), **data.model_dump())
        db.add(row)
        db.commit()
        return course_json(row)

    @app.put('/admin/courses/{id_}')
    def update_course(id_: str, data: CourseInput, user=Depends(admin), db=Depends(db_session)):
        row = course(db, id_)
        for k, v in data.model_dump().items():
            setattr(row, k, v)
        db.commit()
        return course_json(row)

    @app.post('/admin/learners', status_code=201)
    def create_learner(data: LearnerInput, user=Depends(admin), db=Depends(db_session)):
        from .main import passwords
        from sqlalchemy.exc import IntegrityError
        row = User(id=str(uuid.uuid4()), email=data.email.lower(), password_hash=passwords.hash(data.password), interests=[], role='learner')
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Ce compte existe déjà')
        return {'id': row.id, 'email': row.email, 'role': row.role}

    @app.get('/admin/resources')
    def resources(user=Depends(admin), db=Depends(db_session)):
        return [resource_json(r) for r in db.scalars(select(Resource).order_by(Resource.title))]

    def validate_resource(data, db):
        c = course(db, data.course_id)
        if c.archived and not data.archived:
            raise HTTPException(422, 'Choisissez un cours actif')
        if data.kind == 'video' and data.duration <= 0:
            raise HTTPException(422, 'La durée vidéo est obligatoire')
        if any(len(tag) > 80 for tag in data.tags):
            raise HTTPException(422, 'Mot-clé trop long')

    @app.post('/admin/resources', status_code=201)
    def create_resource(data: ResourceInput, user=Depends(admin), db=Depends(db_session)):
        validate_resource(data, db)
        row = Resource(id=str(uuid.uuid4()), url='', **data.model_dump())
        db.add(row)
        db.commit()
        return resource_json(row)

    @app.put('/admin/resources/{id_}')
    def update_resource(id_: str, data: ResourceInput, user=Depends(admin), db=Depends(db_session)):
        row = resource(db, id_)
        validate_resource(data, db)
        if (row.object_key or row.url) and (row.kind != data.kind or row.duration != data.duration):
            raise HTTPException(409, 'Type et durée immuables après import pour préserver la progression')
        for k, v in data.model_dump().items():
            setattr(row, k, v)
        db.commit()
        return resource_json(row)

    @app.put('/admin/resources/{id_}/content')
    async def upload(id_: str, request: Request, user=Depends(admin), db=Depends(db_session)):
        row = resource(db, id_)
        if row.object_key or row.url:
            raise HTTPException(409, 'Contenu déjà importé ; créez une nouvelle ressource pour le remplacer')
        expected = 'video/mp4' if row.kind == 'video' else 'application/pdf'
        if request.headers.get('content-type', '').split(';')[0] != expected:
            raise HTTPException(415, 'Importer un MP4 ou PDF correspondant au type choisi')
        maximum = 200 * 1024 * 1024
        size = 0
        # Streaming to a temporary file: no 200 MB allocation in API memory.
        with tempfile.TemporaryFile() as file:
            async for chunk in request.stream():
                size += len(chunk)
                if size > maximum:
                    raise HTTPException(413, 'Fichier limité à 200 Mo')
                await run_in_threadpool(file.write, chunk)
            file.seek(0)
            header = file.read(32)
            if (row.kind == 'file' and not header.startswith(b'%PDF-')) or (row.kind == 'video' and header[4:8] != b'ftyp'):
                raise HTTPException(415, 'Signature de fichier invalide')
            file.seek(0)
            key = f'resources/{row.id}/{uuid.uuid4()}'
            try:
                await run_in_threadpool(get_storage().upload, file, key, expected)
            except Exception as error:
                import logging
                logging.getLogger(__name__).error('Stockage indisponible : %s', type(error).__name__)
                raise HTTPException(503, 'Stockage indisponible ; réessayez cet import')
        row.object_key = key
        db.commit()
        return resource_json(row)
