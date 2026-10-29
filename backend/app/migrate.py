from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect


def migrate(engine):
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        tables = set(inspect(connection).get_table_names())
        if tables and 'alembic_version' not in tables:
            # Only adopt the known v0.1 schema. Never stamp an arbitrary partial database.
            expected = {
                'users': {'id', 'email', 'password_hash', 'interests'},
                'resources': {'id', 'title', 'description', 'topic', 'level', 'kind', 'duration', 'url', 'tags'},
                'auth_sessions': {'token_hash', 'user_id', 'expires_at'},
                'learning_sessions': {'id', 'user_id', 'resource_id'},
                'interaction_events': {'event_id', 'user_id', 'resource_id', 'session_id', 'sequence', 'event_type', 'occurred_at', 'received_at', 'position_seconds', 'payload'},
                'feedback': {'id', 'user_id', 'resource_id', 'useful', 'favorite'},
            }
            if tables != set(expected) or any({c['name'] for c in inspect(connection).get_columns(t)} != columns for t, columns in expected.items()):
                raise RuntimeError('Schéma non versionné inconnu : migration manuelle requise ; aucune donnée supprimée')
            command.stamp(config, '0001')
        command.upgrade(config, 'head')


if __name__ == '__main__':
    from .db import database
    engine, _ = database()
    migrate(engine)
