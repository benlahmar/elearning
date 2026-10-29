import os
import uuid

from sqlalchemy import select
from pwdlib import PasswordHash

from .db import Resource, User

RESOURCES = [
    ('video-1', 'Observer une vidéo, comprendre les signaux', 'Vidéo de démonstration : utilisez lecture, pause et retours arrière pour explorer la collecte.', 'Analyse des interactions', 'Débutant', 'video', 596.5, 'https://storage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', ['interactions', 'vidéo', 'engagement']),
    ('video-2', 'Expérimenter les parcours de lecture', 'Deuxième média de démonstration pour comparer les sessions et les recommandations.', 'Expérimentation', 'Débutant', 'video', 653.8, 'https://storage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4', ['expérience', 'vidéo', 'parcours']),
    ('file-1', 'Introduction aux systèmes de recommandation', 'Article de référence sur le filtrage collaboratif. Document public en anglais.', 'Recommandation', 'Intermédiaire', 'file', 0, 'https://files.grouplens.org/papers/GroupLens-1994.pdf', ['recommandation', 'collaboratif', 'évaluation']),
]


def seed(db):
    email, password = os.getenv('DEMO_EMAIL'), os.getenv('DEMO_PASSWORD')
    if email and password and not db.scalar(select(User).where(User.email == email.lower())):
        if len(password) < 12:
            raise ValueError('DEMO_PASSWORD doit contenir au moins 12 caractères')
        db.add(User(id=str(uuid.uuid4()), email=email.lower(), password_hash=PasswordHash.recommended().hash(password), interests=[]))
    for id_, title, description, topic, level, kind, duration, url, tags in RESOURCES:
        if not db.get(Resource, id_):
            db.add(Resource(id=id_, title=title, description=description, topic=topic, level=level, kind=kind, duration=duration, url=url, tags=tags))
    db.commit()

    admin_email, admin_password = os.getenv('ADMIN_EMAIL'), os.getenv('ADMIN_PASSWORD')
    if admin_email and admin_password:
        if len(admin_password) < 12:
            raise ValueError('ADMIN_PASSWORD doit contenir au moins 12 caractères')
        admin = db.scalar(select(User).where(User.email == admin_email.lower()))
        if not admin:
            admin = User(id=str(uuid.uuid4()), email=admin_email.lower(), password_hash=PasswordHash.recommended().hash(admin_password), interests=[], role='admin')
            db.add(admin)
        admin.role = 'admin'
        db.commit()
