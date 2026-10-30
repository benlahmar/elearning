from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

STOP_WORDS = 'a au aux avec ce ces dans de des du elle en et eux il ils je la le les leur lui ma mais me mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous the and of to in for is are with'.split()


@lru_cache(maxsize=2)
def lexical_index(documents):
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), strip_accents='unicode', lowercase=True, stop_words=STOP_WORDS, max_features=25000, sublinear_tf=True, norm='l2')
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError as error:
        if 'empty vocabulary' in str(error):
            return None, None
        raise
    return vectorizer, matrix


def lexical_features(context):
    vectorizer, matrix = lexical_index(context.documents)
    if vectorizer is None:
        return np.zeros(len(context.ids)), lambda candidates, selected: np.zeros((len(candidates), len(selected)))
    profile = vectorizer.transform([context.profile])
    scores = (matrix @ profile.T).toarray().ravel()
    def similarities(candidates, selected):
        return (matrix[candidates] @ matrix[selected].T).toarray()
    return scores, similarities
