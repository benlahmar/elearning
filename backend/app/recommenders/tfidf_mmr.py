from .base import Ranking
from .mmr import select_mmr
from .popular import Popular
from .text_features import lexical_features


class TfidfMMR:
    def rank(self, context, limit, parameters):
        scores, similarities = lexical_features(context)
        if not context.profile.strip() or max(scores, default=0) <= 0:
            return Popular().rank(context, limit, parameters)
        order, mmr_scores = select_mmr(context.ids, scores, similarities, limit, parameters['lambda'], parameters['candidate_pool'])
        return Ranking(order, [float(scores[i]) for i in order], 'tfidf_mmr', 'TF-IDF puis diversification MMR', {'mmr_scores': mmr_scores})
