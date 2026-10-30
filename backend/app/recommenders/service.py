from time import perf_counter

from .base import Context, document
from .popular import Popular
from .registry import REGISTRY


def normalize_parameters(id_, supplied, limit):
    spec = REGISTRY[id_]['parameters']
    if set(supplied) - set(spec):
        raise ValueError('Paramètre non pris en charge pour cet algorithme')
    result = {}
    for key, rule in spec.items():
        value = supplied.get(key, rule['default'])
        if type(value) not in (int, float) or not rule['min'] <= value <= rule['max']:
            raise ValueError('Paramètre invalide : ' + key)
        if key == 'candidate_pool' and (type(value) is not int or value < limit):
            raise ValueError('Le nombre de candidats doit être entier et au moins égal à K')
        result[key] = value
    return result


def recommend(id_, resources, interests, popularity, limit=6, parameters=None):
    if id_ not in REGISTRY:
        raise ValueError('Algorithme inconnu')
    if len(resources) > 5000:
        raise ValueError('Le pilote est limité à 5000 ressources actives')
    parameters = normalize_parameters(id_, parameters or {}, limit)
    resources = sorted(resources, key=lambda r: r.id)
    context = Context(tuple(r.id for r in resources), tuple(document(r) for r in resources), ' '.join(interests), tuple(popularity.get(r.id, 0) for r in resources))
    start = perf_counter()
    ranking = REGISTRY[id_]['algorithm'].rank(context, limit, parameters) if resources else Popular().rank(context, limit, {})
    return {'algorithm': id_, 'effective_algorithm': ranking.effective_algorithm, 'fallback': bool(resources) and ranking.effective_algorithm != id_, 'version': REGISTRY[id_]['version'], 'parameters': parameters, 'profile_source': 'declared_interests', 'elapsed_ms': round((perf_counter() - start) * 1000, 2), 'reason': ranking.reason, 'metadata': ranking.metadata, 'ranked': [(resources[i], score) for i, score in zip(ranking.indices, ranking.scores)]}
