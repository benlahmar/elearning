from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Context:
    ids: tuple[str, ...]
    documents: tuple[str, ...]
    profile: str
    popularity: tuple[int, ...]


@dataclass
class Ranking:
    indices: list[int]
    scores: list[float]
    effective_algorithm: str
    reason: str
    metadata: dict = field(default_factory=dict)


class Algorithm(Protocol):
    def rank(self, context: Context, limit: int, parameters: dict) -> Ranking: ...


class ModelUnavailable(RuntimeError):
    pass


def document(resource):
    """Only teaching metadata; never a media URL or participant identity."""
    return ' '.join([resource.title, resource.title, resource.topic, ' '.join(resource.tags), resource.description])
