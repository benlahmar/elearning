from pathlib import Path

from .embeddings import Embeddings
from .embeddings_mmr import EmbeddingsMMR
from .hybrid_content_mmr import HybridContentMMR
from .legacy import LegacyContent
from .popular import Popular
from .tfidf import Tfidf
from .tfidf_mmr import TfidfMMR
from .semantic import encoder

FAMILIES = [
    {'id': 'content', 'name': 'Basés sur le contenu', 'description': 'Comparer les intérêts aux métadonnées des ressources.'},
    {'id': 'collaborative', 'name': 'Collaboratifs', 'description': 'À implémenter : apprendre des interactions entre utilisateurs et ressources.'},
    {'id': 'filtering', 'name': 'Filtres et règles', 'description': 'À implémenter : sélectionner selon des contraintes pédagogiques.'},
    {'id': 'hybrid', 'name': 'Hybrides', 'description': 'À implémenter : combiner contenu, collaboratif ou règles.'},
    {'id': 'baselines', 'name': 'Références', 'description': 'Méthodes simples conservées pour comparaison.'},
]

MMR = {'lambda': {'default': .7, 'min': 0, 'max': 1, 'label': 'λ MMR', 'help': '1 privilégie la pertinence ; une valeur plus faible pénalise davantage la redondance.'}, 'candidate_pool': {'default': 50, 'min': 1, 'max': 200, 'label': 'Candidats MMR', 'help': 'MMR sélectionne dans les meilleurs candidats ; ce nombre doit être au moins égal à K.'}}


def entry(id_, name, algorithm, summary, steps, formula, limitations, parameters=None, semantic=False, family='content'):
    return {'id': id_, 'name': name, 'algorithm': algorithm, 'summary': summary, 'steps': steps, 'formula': formula, 'limitations': limitations, 'parameters': parameters or {}, 'semantic': semantic, 'family': family, 'version': '1.0.0'}


ENTRIES = [
    entry('tfidf', 'TF-IDF + cosinus', Tfidf(), 'Une référence lexicale pondérant les mots distinctifs du catalogue.', ['Construire un texte par ressource : titre (deux fois), thème, mots-clés, description.', 'Apprendre TF-IDF sur le catalogue actif : mots et bigrammes, normalisation L2.', 'Transformer les intérêts déclarés avec le même vocabulaire.', 'Trier par similarité cosinus, puis identifiant en cas d’égalité.'], 'score(u, i) = cosinus(TF-IDF(intérêts), TF-IDF(ressource))', ['Les synonymes sans mot commun restent difficiles.', 'Profil vide ou vocabulaire sans recouvrement : repli explicite sur la popularité.']),
    entry('tfidf_mmr', 'TF-IDF + MMR', TfidfMMR(), 'Diversifier les meilleurs résultats lexicaux.', ['Calculer les scores TF-IDF.', 'Retenir les meilleurs candidats.', 'Choisir progressivement le contenu qui combine pertinence et faible similarité avec les contenus déjà sélectionnés.'], 'MMR(i) = λ × pertinence(i) − (1 − λ) × max(similarité(i, sélection))', ['MMR est un réordonnancement, pas un encodeur.', 'Une diversité plus forte peut diminuer la pertinence.', 'λ = 1 reproduit le classement de pertinence.'], MMR),
    entry('embeddings', 'Sentence Transformers + cosinus', Embeddings(), 'Retrouver des ressources sémantiquement proches, même sans mots identiques.', ['Préparer le modèle multilingue sur le serveur.', 'Encoder et mettre en cache les textes des ressources.', 'Encoder localement les intérêts de l’utilisateur.', 'Classer par cosinus positif entre vecteurs normalisés.'], 'score(u, i) = max(0, cosinus(embedding(intérêts), embedding(ressource)))', ['Premier téléchargement et chargement plus coûteux.', 'Le modèle tronque les textes au nombre de tokens qu’il accepte.', 'Les recommandations dépendent de la qualité des métadonnées.'], semantic=True),
    entry('embeddings_mmr', 'Sentence Transformers + MMR', EmbeddingsMMR(), 'Associer proximité sémantique et diversité.', ['Calculer les scores sémantiques.', 'Retenir un ensemble de candidats.', 'Appliquer MMR avec la similarité sémantique entre ressources.'], 'MMR(i) = λ × cosinus(profil, i) − (1 − λ) × max(cosinus(i, sélection))', ['Même modèle et mêmes limites que la variante embeddings.', 'Une diversité sémantique ne garantit pas une progression pédagogique.'], MMR, semantic=True),
    entry('hybrid_content_mmr', 'TF-IDF + embeddings + MMR', HybridContentMMR(), 'Fusionner les représentations lexicales et sémantiques avant diversification.', ['Calculer les scores lexicaux et sémantiques entre 0 et 1.', 'Combiner les scores avec le poids α.', 'Combiner de la même façon les similarités entre contenus.', 'Appliquer MMR sur les meilleurs candidats de la fusion.'], 'pertinence = α × TF-IDF + (1 − α) × embeddings ; puis MMR', ['Cette hybridation reste basée sur le contenu : aucun filtrage collaboratif.', 'Les cosinus ne sont pas des probabilités calibrées.', 'Les poids doivent être évalués sur un jeu de validation.'], {**MMR, 'alpha': {'default': .5, 'min': 0, 'max': 1, 'label': 'α lexical', 'help': '1 = lexical uniquement ; 0 = sémantique uniquement. La variante utilise le modèle sémantique dans les deux cas.'}}, semantic=True),
    entry('popular', 'Popularité', Popular(), 'Nombre d’utilisateurs distincts ayant interagi.', ['Compter les utilisateurs distincts par ressource active.', 'Trier par ce nombre, puis identifiant.'], 'score(i) = nombre d’utilisateurs distincts', ['Non personnalisé ; les administrateurs de test sont compris.'], family='baselines'),
    entry('content', 'Similarité lexicale historique', LegacyContent(), 'Référence Jaccard conservée pour compatibilité avec les premières versions.', ['Comparer les ensembles de mots du profil et de chaque ressource.'], 'Jaccard(A, B) = |A ∩ B| / |A ∪ B|', ['Pas de pondération TF-IDF ni de compréhension sémantique.'], family='baselines'),
]
REGISTRY = {row['id']: row for row in ENTRIES}


def describe(row, include_source=False):
    result = {k: v for k, v in row.items() if k != 'algorithm'}
    state = encoder.status()
    result['available'] = not row['semantic'] or state['state'] == 'ready'
    result['model_status'] = state if row['semantic'] else None
    if include_source:
        own_file = row['algorithm'].__class__.__module__.rsplit('.', 1)[-1] + '.py'
        companions = ['base.py']
        if row['id'] in ('tfidf', 'tfidf_mmr', 'hybrid_content_mmr'):
            companions.append('text_features.py')
        if 'lambda' in row['parameters']:
            companions.append('mmr.py')
        if row['semantic']:
            companions.append('semantic.py')
        companions.append('popular.py')
        # Only files derived from this fixed registry are readable. No client paths.
        root = Path(__file__).resolve().parent
        result['sources'] = [{'path': 'app/recommenders/' + filename, 'content': (root / filename).read_text()} for filename in dict.fromkeys([own_file, *companions])]
    return result
