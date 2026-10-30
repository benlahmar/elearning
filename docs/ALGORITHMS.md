# Version 0.4 — algorithmes modulaires de recommandation

## Installer la version

Conserver `.env` et les volumes existants. Après la sauvegarde habituelle de la base :

```sh
git fetch origin
git switch feat/modular-content-recommenders
docker compose up --build -d
```

Aucune migration de base supplémentaire. Le port 8013, PostgreSQL 17, MinIO, les contenus et les interactions existantes sont conservés. La première construction de l’API installe aussi PyTorch CPU et Sentence Transformers : elle est plus volumineuse que les versions précédentes.

Se connecter comme administrateur puis ouvrir **Administration → Algorithmes**. Le menu classe les méthodes par familles. Les cinq variantes demandées sont dans **Basés sur le contenu**. Les familles **Collaboratifs**, **Filtres et règles** et **Hybrides** sont présentes mais explicitement vides. Les anciennes méthodes restent dans **Références**.

Chaque fiche contient l’explication, les étapes, la formule, les limites, le code exact lu depuis le serveur et un essai sur le catalogue actif. Les fichiers communs sont également consultables, pas seulement le petit module qui les appelle. Le code est en lecture seule ; aucune exécution de code fourni par l’administrateur.

## Les cinq variantes

| Identifiant API | Module propre | Fonctionnement |
|---|---|---|
| tfidf | tfidf.py | TF-IDF puis cosinus |
| tfidf_mmr | tfidf_mmr.py | Candidats TF-IDF puis sélection MMR |
| embeddings | embeddings.py | Sentence Transformers puis cosinus positif |
| embeddings_mmr | embeddings_mmr.py | Candidats sémantiques puis MMR |
| hybrid_content_mmr | hybrid_content_mmr.py | Fusion lexicale/sémantique puis MMR |

La cinquième méthode combine deux représentations du contenu ; elle reste dans la famille contenu. La famille Hybrides est réservée aux futures combinaisons entre contenu, collaboratif ou règles.

Les ressources sont représentées par titre (deux fois), thème, mots-clés et description. Le profil est le texte des intérêts déclarés. TF-IDF utilise les unigrammes/bigrammes, accents normalisés, une petite liste de mots fréquents français/anglais, TF sous-linéaire, normalisation L2 et au maximum 25 000 caractéristiques. Les PDF et les pistes audio ne sont pas extraits automatiquement. Les interactions vidéo ne pondèrent pas encore ces profils : cela restera une variante expérimentale distincte.

Un profil vide entraîne un repli explicite sur la popularité. TF-IDF utilise aussi ce repli si aucun mot exploitable du profil ne recoupe le vocabulaire. La réponse indique toujours la méthode demandée, la méthode effectivement utilisée, le repli éventuel, la version, les paramètres et le temps du classement. Un modèle sémantique non préparé avec un profil non vide donne une erreur 503 claire, sans substitution silencieuse par TF-IDF.

## Paramètres et essai

- K : de 1 à 20 résultats, limité au nombre réel de ressources actives.
- λ MMR : de 0 à 1, valeur initiale 0,7. Plus λ augmente, plus la pertinence est privilégiée. À λ=1, le classement de pertinence est conservé.
- candidate_pool : de 1 à 200, valeur initiale 50, au moins égal à K. MMR travaille dans ces meilleurs candidats pour borner le coût de la diversification.
- α lexical : de 0 à 1, valeur initiale 0,5. Pertinence et similarités entre contenus sont fusionnées avec le même poids. α=1 correspond au lexical ; α=0 au sémantique. La cinquième variante conserve son pipeline sémantique dans les deux cas.

Le profil et les paramètres saisis sur la fiche ne modifient pas un compte et ne sont pas enregistrés comme configuration globale. La section apprenant **Pour vous** permet de choisir les méthodes préparées et utilise leurs paramètres par défaut. TF-IDF est la méthode par défaut ; `content` et `popular` restent utilisables pour compatibilité.

Les scores affichés sont des pertinences, pas des probabilités. MMR détermine l’ordre final : une pertinence plus faible peut apparaître avant une autre si elle apporte de la diversité. Les scores MMR et les deux composantes de la fusion sont visibles dans les détails d’exécution. Ils ne sont pas directement comparables aux compteurs bruts de popularité.

## Préparer Sentence Transformers

Modèle initial : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, multilingue et exécuté sur CPU.

1. Ouvrir une fiche embeddings ou fusion.
2. Cliquer **Préparer le modèle**. Un travail de fond charge le cache local ou télécharge les fichiers du modèle.
3. Attendre l’état **Prêt**, puis lancer l’essai. La page suit l’avancement sans maintenir une longue requête de téléchargement.
4. Revenir à l’espace apprenant pour rafraîchir la liste des méthodes disponibles.

La préparation nécessite un accès Internet à Hugging Face si le modèle n’est pas déjà en cache. Les intérêts et textes des ressources sont encodés localement et ne sont pas envoyés à Hugging Face. Le téléchargement des poids est distinct du calcul des recommandations. Le cache des fichiers du modèle est conservé dans le volume `model_cache`. Après redémarrage de l’API, cliquer de nouveau Préparer pour charger le modèle en mémoire ; les fichiers déjà présents sont réutilisés.

Les index TF-IDF et embeddings du catalogue sont conservés en mémoire, avec au plus deux versions de chaque index. La clé inclut les textes des ressources : une modification des métadonnées invalide automatiquement l’index correspondant. Aucun profil utilisateur n’est mis en cache. Un redémarrage reconstruit les index, sans modifier les données d’apprentissage.

Variables facultatives dans `.env` :

```dotenv
INSTALL_SEMANTIC=true
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_REVISION=e8f8c211226b894fcb81acc59f3b34ba3efd5f42
```

La version par défaut est figée au commit e8f8c211226b894fcb81acc59f3b34ba3efd5f42. La fiche et les résultats indiquent la révision effectivement chargée lorsque Transformers la fournit. Pour reproduire une expérience, fixer EMBEDDING_REVISION à ce commit plutôt qu’à `main`, puis recréer l’API. Choisir un autre modèle compatible nécessite une révision correspondant à ce modèle ; cette configuration reste côté serveur, pas dans un champ modifiable par un apprenant. Le chargement de code distant est désactivé.

Si les ressources de la machine ne permettent pas PyTorch, définir INSTALL_SEMANTIC=false et reconstruire l’API. Les deux variantes TF-IDF et les références restent disponibles ; les fiches sémantiques indiquent leurs dépendances manquantes. Prévoir plusieurs gigaoctets libres pour la construction initiale, les dépendances et le modèle.

Hors Docker, installer d’abord les dépendances du backend puis :

```sh
pip install torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r backend/requirements-semantic.txt
```

Avec un environnement de développement lancé depuis backend, adapter le chemin à `requirements-semantic.txt`. Configurer HF_HOME vers un dossier accessible en écriture au processus pour conserver les modèles.

## Architecture et ajout d’une méthode

```text
app/recommenders/
  base.py                 # Context, Ranking et protocole commun
  registry.py             # Familles, métadonnées pédagogiques et modules enregistrés
  service.py              # Validation, appel commun, version et repli déclaré
  tfidf.py
  tfidf_mmr.py
  embeddings.py
  embeddings_mmr.py
  hybrid_content_mmr.py
  mmr.py                  # Sélection MMR partagée
  text_features.py        # TF-IDF et cache
  semantic.py             # Cycle de vie du modèle, encodeur et cache
  popular.py, legacy.py   # Références
app/recommender_routes.py  # API apprenant et administration
```

Pour ajouter une méthode : créer une classe avec `rank(context, limit, parameters) -> Ranking`, l’enregistrer dans registry.py avec sa famille/explication/paramètres, et ajouter un test de comportement. La fiche et son code apparaissent alors automatiquement sans ajouter de route spécifique. Les filtres d’autorisation et de publication restent centralisés avant l’appel aux algorithmes.

## API et vérification

- GET /algorithms : méthodes accessibles aux utilisateurs connectés, sans sources.
- GET /recommendations?algorithm=tfidf : classement de l’utilisateur connecté.
- GET /admin/algorithms et GET /admin/algorithms/{id} : catalogue et fiche avec sources, administrateur uniquement.
- POST /admin/algorithms/{id}/preview : profil de test et paramètres validés.
- POST /admin/semantic-model/prepare et GET /admin/semantic-model : préparation et état, administrateur uniquement.

Les tests vérifient les cinq chemins de classement, le vocabulaire absent, les profils/candidats vides, l’invalidation après modification des textes, la diversification MMR, les extrêmes des poids, les permissions et l’exclusion des archives/brouillons. Les tests unitaires sémantiques utilisent un encodeur contrôlé, sans télécharger de modèle. Une vérification d’intégration avec le vrai modèle est distincte de ces tests et nécessite les dépendances sémantiques et son cache.

Une vérification CPU a également été effectuée avec le vrai modèle à la révision figée : embeddings, embeddings + MMR et fusion + MMR ont retrouvé un contenu sur un gâteau pour le profil « recettes de cuisine », sans recouvrement lexical exploitable par TF-IDF. C’est une vérification de fonctionnement sur un petit exemple, pas une mesure générale de qualité.

Limites : pilote borné à 5000 ressources actives ; ce lot n’ajoute pas encore d’évaluation hors ligne ou d’A/B testing. Les temps affichés concernent le classement et l’encodage éventuel, pas toute la latence HTTP. La qualité pédagogique doit être évaluée sur des données adaptées, pas déduite d’un score cosinus seul.
