import numpy as np


def select_mmr(ids, relevance, similarities, limit, diversity_lambda, candidate_pool):
    """MMR = lambda*relevance - (1-lambda)*max similarity to selected items."""
    remaining = sorted(range(len(ids)), key=lambda i: (-float(relevance[i]), ids[i]))[:candidate_pool]
    selected, mmr_scores = [], []
    while remaining and len(selected) < limit:
        redundancy = np.max(similarities(remaining, selected), axis=1) if selected else np.zeros(len(remaining))
        values = diversity_lambda * relevance[remaining] - (1 - diversity_lambda) * redundancy
        # remaining is relevance-sorted, then id-sorted: deterministic tie breaking.
        position = int(np.argmax(values))
        selected.append(remaining.pop(position))
        mmr_scores.append(float(values[position]))
    return selected, mmr_scores
