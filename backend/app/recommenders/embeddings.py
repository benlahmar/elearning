from .base import Ranking
from .popular import Popular
from .semantic import encoder, semantic_features


class Embeddings:
    def rank(self, context, limit, parameters):
        if not context.profile.strip():
            return Popular().rank(context, limit, parameters)
        scores, _ = semantic_features(context)
        order = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), context.ids[i]))[:limit]
        return Ranking(order, [float(scores[i]) for i in order], 'embeddings', 'Similarité sémantique locale Sentence Transformers', {'model': encoder.status()})
