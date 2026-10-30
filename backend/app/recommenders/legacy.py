import re

from .base import Ranking
from .popular import Popular


class LegacyContent:
    def rank(self, context, limit, parameters):
        profile = set(re.findall(r'\w+', context.profile.lower()))
        if not profile:
            return Popular().rank(context, limit, parameters)
        tokens = [set(re.findall(r'\w+', text.lower())) for text in context.documents]
        scores = [len(profile & words) / max(1, len(profile | words)) for words in tokens]
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], context.ids[i]))[:limit]
        return Ranking(order, [scores[i] for i in order], 'content', 'Similarité lexicale de référence (Jaccard)')
