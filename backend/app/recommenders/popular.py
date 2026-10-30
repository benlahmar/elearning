from .base import Ranking


class Popular:
    def rank(self, context, limit, parameters):
        indices = sorted(range(len(context.ids)), key=lambda i: (-context.popularity[i], context.ids[i]))[:limit]
        return Ranking(indices, [float(context.popularity[i]) for i in indices], 'popular', 'Popularité : nombre d’utilisateurs distincts ayant interagi')
