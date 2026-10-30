from .base import Ranking
from .mmr import select_mmr
from .popular import Popular
from .semantic import encoder, semantic_features
from .text_features import lexical_features


class HybridContentMMR:
    def rank(self, context, limit, parameters):
        if not context.profile.strip():
            return Popular().rank(context, limit, parameters)
        lexical, lexical_sim = lexical_features(context)
        semantic, semantic_sim = semantic_features(context)
        alpha = parameters['alpha']
        relevance = alpha * lexical + (1 - alpha) * semantic
        def similarities(candidates, selected):
            return alpha * lexical_sim(candidates, selected) + (1 - alpha) * semantic_sim(candidates, selected)
        order, mmr_scores = select_mmr(context.ids, relevance, similarities, limit, parameters['lambda'], parameters['candidate_pool'])
        return Ranking(order, [float(relevance[i]) for i in order], 'hybrid_content_mmr', 'Fusion lexicale et sémantique, puis MMR', {'mmr_scores': mmr_scores, 'lexical_scores': [float(lexical[i]) for i in order], 'semantic_scores': [float(semantic[i]) for i in order], 'model': encoder.status()})
