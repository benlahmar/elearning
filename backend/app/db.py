import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    interests: Mapped[list] = mapped_column(JSON, default=list)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Resource(Base):
    __tablename__ = 'resources'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    topic: Mapped[str] = mapped_column(String)
    level: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    duration: Mapped[float] = mapped_column(Float, default=0)
    url: Mapped[str] = mapped_column(String)
    tags: Mapped[list] = mapped_column(JSON, default=list)


class LearningSession(Base):
    __tablename__ = 'learning_sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey('resources.id'))


class Event(Base):
    __tablename__ = 'interaction_events'
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey('resources.id'), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('learning_sessions.id'))
    sequence: Mapped[int]
    event_type: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    position_seconds: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Feedback(Base):
    __tablename__ = 'feedback'
    __table_args__ = (UniqueConstraint('user_id', 'resource_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    resource_id: Mapped[str] = mapped_column(ForeignKey('resources.id'))
    useful: Mapped[bool | None]
    favorite: Mapped[bool] = mapped_column(default=False)


def database(url=None):
    url = url or os.getenv('DATABASE_URL', 'sqlite:///./learning.db')
    kwargs = {'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {}
    engine = create_engine(url, **kwargs)
    return engine, sessionmaker(engine, expire_on_commit=False)
