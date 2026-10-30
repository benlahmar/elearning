from .base import Ranking
from .popular import Popular
from .text_features import lexical_features


class Tfidf:
    def rank(self, context, limit, parameters):
        scores, _ = lexical_features(context)
        if not context.profile.strip() or max(scores, default=0) <= 0:
            return Popular().rank(context, limit, parameters)
        order = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), context.ids[i]))[:limit]
        return Ranking(order, [float(scores[i]) for i in order], 'tfidf', 'Similarité cosinus TF-IDF avec les intérêts déclarés')
