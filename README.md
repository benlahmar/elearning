# Learning Recsys Lab — proposition de MVP

Plateforme pédagogique de vidéos et de fichiers pour expérimenter des systèmes de recommandation. Équipe : 5 ingénieurs. Planning indicatif : 4 semaines, à ajuster selon la disponibilité de l’équipe.

**Statut : version 0.2 : administration et contenus privés.** Connexion de démonstration, catalogue, lecteur instrumenté, progression, favoris et premiers classements. Les sections ci-dessous décrivent la cible complète du MVP, pas uniquement ce qui est déjà implémenté.

## Lancer la version actuelle

```sh
cp .env.example .env
docker compose up --build
```

Ouvrir http://localhost:8013 et utiliser les identifiants définis dans `.env`. Consultez [le guide de développement](docs/DEVELOPMENT.md) pour le démarrage sans Docker, les tests et les limites de cette version. L’administration permet désormais d’importer vos MP4/PDF dans MinIO privé. Voir [la mise à jour depuis v0.1](docs/UPGRADE.md).

## Objectif

Permettre à un apprenant de consulter des ressources, reprendre une vidéo et recevoir des recommandations. Permettre à l’équipe d’étudier si les interactions vidéo améliorent les recommandations par rapport aux clics seuls.

## Périmètre de la première version

| Fonction | Critère de validation |
|---|---|
| Comptes apprenant et administrateur | Connexion, déconnexion et contrôle des permissions côté API ; inscription sur invitation pour le pilote |
| Profil | Centres d’intérêt et niveau modifiables ; solution de repli si profil vide |
| Catalogue | Recherche par titre, filtres thème/niveau/type, pagination |
| Administration | Créer et modifier des cours et ressources ; archiver une ressource sans casser l’historique |
| Ressources | Vidéos MP4 et fichiers PDF ; métadonnées, limites de taille, contrôle du type et accès autorisé |
| Lecture vidéo | Play/pause, déplacement, vitesse, reprise à la dernière position et progression |
| Interactions | Collecte fiable des événements, sans doublons lors des réessais |
| Retour explicite | Favori, utile/pas utile ; quelques quiz courts facultatifs pour explorer la compréhension |
| Recommandations | Liste « Pour vous », modèles interchangeables, impressions et clics attribuables |
| Analyse | Tableau de bord de couverture vidéo, passages revus, abandons et résultats des modèles |
| Données de recherche | Export pseudonymisé réservé à l’administrateur, sans adresse e-mail |

Hors périmètre : paiements, chat, certificats, application mobile native, transcodage adaptatif et entraînement en temps réel.

## Parcours principal

1. L’apprenant se connecte et renseigne ses intérêts.
2. Il consulte le catalogue ou les recommandations.
3. Il ouvre une vidéo ou télécharge un fichier.
4. Ses interactions sont enregistrées ; il peut reprendre sa vidéo plus tard.
5. Un traitement calcule les indicateurs et actualise les recommandations.
6. L’équipe compare les modèles sur les mêmes données et consulte les résultats.

## Stack et architecture

- Frontend : React, TypeScript, Vite et lecteur vidéo HTML5.
- Backend : FastAPI, SQLAlchemy et Alembic.
- Base : PostgreSQL pour les comptes, contenus, événements et expériences.
- Fichiers : stockage privé compatible S3 ; URLs temporaires après vérification des droits. MinIO possible en développement.
- Recommandation : Python, pandas et scikit-learn dans le même backend ; scripts de calcul hors requête HTTP.
- Développement : Docker Compose ; CI GitHub Actions pour lint, tests backend et compilation frontend.

Flux : navigateur → API FastAPI → PostgreSQL. Le navigateur lit les médias via une URL temporaire du stockage. Un script Python exploite les événements et publie les caractéristiques et versions des modèles. Aucun microservice nécessaire.

## Modèle de données proposé

| Table | Rôle |
|---|---|
| users, profiles | Identité, rôle, intérêts et niveau ; séparation de l’identité et des identifiants analytiques |
| courses, resources | Organisation, type, description, thème, niveau, tags, durée, clé de stockage, statut |
| learning_sessions | Sessions de consultation, utilisateur, ressource et dates |
| interaction_events | Événements bruts versionnés, positions, horodatages et identifiants uniques |
| resource_progress | Dernière position et couverture des portions visionnées par utilisateur/ressource |
| feedback | Favoris et appréciations explicites |
| recommendation_requests, recommendation_items | Modèle/version, candidats présentés, rang, contexte et impression visible |
| experiment_assignments | Affectation stable utilisateur/expérience, lorsque la comparaison en ligne est activée |
| feature_snapshots, evaluation_runs | Caractéristiques calculées, date de coupure, paramètres et résultats reproductibles |

Pour le MVP, conserver les événements dans PostgreSQL avec index sur utilisateur/date et ressource/date ; dédupliquer par event_id. Mesurer le volume avant de prévoir du partitionnement.

## API proposée

| Méthode et route | Usage |
|---|---|
| POST /auth/login, POST /auth/logout | Session via cookie HttpOnly, Secure en production ; protection CSRF des mutations |
| GET /me, PATCH /me/profile | Profil de l’utilisateur connecté |
| GET /courses, GET /resources | Catalogue filtré et paginé |
| GET /resources/{id} | Détail et progression |
| GET /resources/{id}/access-url | Accès temporaire au fichier après autorisation |
| POST /admin/resources | Création et métadonnées ; routes complémentaires de modification/archivage |
| POST /admin/uploads | Upload contrôlé par l’administrateur |
| POST /events/batch | Lot d’événements validés et dédupliqués |
| PUT /resources/{id}/feedback | Avis de l’apprenant |
| GET /recommendations | Liste ordonnée avec request_id, modèle/version et identifiant par élément |
| GET /admin/analytics | Indicateurs agrégés |
| GET /admin/exports | Export pseudonymisé et borné dans le temps |

## Algorithmes et expérimentation

Interface commune : `recommend(user_id, limit, context) -> ranked_items`. Le serveur choisit le modèle ; l’apprenant ne peut pas imposer une variante arbitraire.

1. Référence aléatoire avec graine enregistrée et référence de popularité.
2. Similarité de contenu : TF-IDF sur titre/description/tags, intérêts déclarés et historique.
3. Variante enrichie par couverture vidéo, répétitions et retours explicites, avec pondérations documentées et versionnées.
4. Filtrage collaboratif ou hybride en extension si les interactions sont assez nombreuses.

Comparer les variantes avec et sans signaux vidéo en gardant les mêmes candidats, dates de coupure et règles d’exclusion. Prévoir un repli populaire/par intérêts pour les nouveaux utilisateurs et des contenus récents pour les nouvelles ressources. Éviter de surpondérer mécaniquement le nombre de pauses ou de retours arrière.

Évaluation hors ligne : découpage temporel entraînement/validation/test ; toutes les caractéristiques de popularité et d’engagement sont calculées avant la coupure. Définir à l’avance un résultat pertinent (par exemple retour « utile » ou consultation substantielle), puis mesurer Precision@K, Recall@K, NDCG@K, couverture du catalogue et diversité. Consigner les limites liées aux contenus jamais exposés.

Évaluation en ligne exploratoire : clics / impressions visibles, complétions par ouverture et retours utiles. Affectation stable et attribution par request_id. Avec peu d’apprenants, présenter des résultats descriptifs, sans affirmer une supériorité statistique. Les données synthétiques servent à tester les traitements, pas à prouver la qualité pédagogique.

## Conditions de réussite du pilote

- Un apprenant peut suivre le parcours complet avec des médias de test autorisés.
- Deux modèles au minimum sont comparables avec une configuration reproductible.
- Les événements vidéo sont persistés, dédupliqués et correctement attribués.
- La couverture ne confond pas portions sautées, répétitions et temps de lecture.
- Un apprenant ne peut lire ni les événements ni les fichiers privés d’un autre compte.
- Les exports et journaux ne contiennent pas de secrets ni d’identité directement reconnaissable.

Voir [le contrat de collecte](docs/EVENTS.md) et [le backlog](docs/BACKLOG.md).
