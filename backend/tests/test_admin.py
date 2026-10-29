from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text

from test_api import client
from app.db import User
from app.migrate import migrate


def test_admin_import_permissions_and_archiving(client, monkeypatch):
    from app import admin, main
    with client.app.state.sessions() as db:
        db.scalar(select(User).where(User.email == 'demo@example.com')).role = 'admin'
        db.commit()
    stored = {}
    class Storage:
        def upload(self, file, key, content_type):
            stored[key] = (file.read(), content_type)
        def access_url(self, key):
            assert key in stored
            return 'https://private.example/' + key + '?signature=test'
    monkeypatch.setattr(admin, 'get_storage', Storage)
    monkeypatch.setattr(main, 'get_storage', Storage)
    course = client.post('/admin/courses', json={'title': 'Mon cours', 'description': 'Test'}).json()
    data = {'title': 'Mon PDF', 'topic': 'Recommandation', 'description': 'Test', 'level': 'Débutant', 'kind': 'file', 'duration': 0, 'course_id': course['id'], 'tags': ['test']}
    resource = client.post('/admin/resources', json=data).json()
    id_ = resource['id']
    assert id_ not in [r['id'] for r in client.get('/resources').json()]
    assert client.put(f'/admin/resources/{id_}/content', content=b'not a PDF', headers={'Content-Type':'application/pdf'}).status_code == 415
    assert client.put(f'/admin/resources/{id_}/content', content=b'%PDF-1.7\ncontent', headers={'Content-Type':'application/pdf'}).status_code == 200
    assert client.get(f'/resources/{id_}/access-url').json()['url'].startswith('https://private.example/')
    assert 'object_key' not in client.get('/resources').text
    assert client.put(f'/admin/resources/{id_}/content', content=b'%PDF-1.7', headers={'Content-Type':'application/pdf'}).status_code == 409
    learner = {'email':'student@example.com','password':'student-password-long'}
    assert client.post('/admin/learners', json=learner).status_code == 201
    assert client.post('/admin/learners', json=learner).status_code == 409
    auth = client.headers['Authorization']
    client.headers['Authorization'] = 'Bearer ' + client.post('/auth/login', json=learner).json()['access_token']
    assert client.get('/me').json()['role'] == 'learner'
    assert client.get('/admin/courses').status_code == 403
    assert client.post('/admin/resources', json=data).status_code == 403
    assert client.put(f'/admin/resources/{id_}/content', content=b'%PDF-1.7', headers={'Content-Type':'application/pdf'}).status_code == 403
    assert client.get(f'/resources/{id_}/access-url').status_code == 200
    client.headers['Authorization'] = auth
    assert client.put('/admin/courses/' + course['id'], json={**course, 'archived':True}).status_code == 200
    assert id_ not in [r['id'] for r in client.get('/resources').json()]
    assert id_ not in [r['id'] for r in client.get('/recommendations').json()['items']]
    assert client.get(f'/resources/{id_}/access-url').status_code == 404
    assert client.put('/admin/courses/' + course['id'], json=course).status_code == 200
    assert client.put(f'/admin/resources/{id_}', json={**data,'archived':True}).status_code == 200
    assert client.get(f'/resources/{id_}/access-url').status_code == 404


def test_legacy_migration_keeps_data(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0001')
        connection.execute(text("INSERT INTO users (id,email,password_hash,interests) VALUES ('legacy','old@example.com','original-hash','[]')"))
        connection.execute(text('DROP TABLE alembic_version'))
    migrate(engine)
    migrate(engine)
    with engine.connect() as connection:
        assert tuple(connection.execute(text("SELECT password_hash, role FROM users WHERE id='legacy'")).one()) == ('original-hash', 'learner')
        assert 'courses' in inspect(connection).get_table_names()
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0002'
