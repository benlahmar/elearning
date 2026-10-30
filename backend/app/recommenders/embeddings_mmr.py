from .base import Ranking
from .mmr import select_mmr
from .popular import Popular
from .semantic import encoder, semantic_features


class EmbeddingsMMR:
    def rank(self, context, limit, parameters):
        if not context.profile.strip():
            return Popular().rank(context, limit, parameters)
        scores, similarities = semantic_features(context)
        order, mmr_scores = select_mmr(context.ids, scores, similarities, limit, parameters['lambda'], parameters['candidate_pool'])
        return Ranking(order, [float(scores[i]) for i in order], 'embeddings_mmr', 'Embeddings Sentence Transformers puis diversification MMR', {'mmr_scores': mmr_scores, 'model': encoder.status()})
