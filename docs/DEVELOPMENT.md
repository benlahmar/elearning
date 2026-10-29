# Démarrer la version 0.1

## Avec Docker Compose

Prérequis : Docker avec Compose, Git et ports locaux disponibles.

```sh
git clone https://github.com/benlahmar/elearning.git
cd elearning
cp .env.example .env
# Modifiez les mots de passe dans .env avant de partager l’environnement.
docker compose up --build
```

Ouvrir http://localhost:8080. Utiliser DEMO_EMAIL et DEMO_PASSWORD de `.env` pour se connecter. Le compte est créé uniquement s’il n’existe pas déjà. Modifier la variable ne modifie pas le mot de passe d’un compte existant. Le volume PostgreSQL conserve les utilisateurs et les événements après redémarrage.

Ce démarrage vise un pilote local. Le port web est lié à 127.0.0.1 ; ni PostgreSQL ni l’API ne sont exposés sur l’hôte.

## Sans Docker

Backend (Python 3.12) :

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
export DEMO_EMAIL=demo@example.com
export DEMO_PASSWORD=change-this-demo-password
cd backend
uvicorn app.main:app --reload --host 127.0.0.1
```

SQLite est utilisé uniquement comme solution locale par défaut. Pour PostgreSQL, définir DATABASE_URL au format `postgresql+psycopg://user:password@host:5432/database`. Encoder les caractères spéciaux du mot de passe dans cette URL.

Dans un deuxième terminal (Node 22+) :

```sh
cd frontend
npm ci
npm run dev
```

Ouvrir l’URL affichée par Vite. Le proxy `/api` évite les configurations CORS divergentes. Documentation API : http://127.0.0.1:8000/docs.

## Vérifications

```sh
cd backend
../.venv/bin/python -m pytest -q
cd ../frontend
npm test
npm run build
```

Les tests API utilisent une base SQLite temporaire et couvrent déduplication, contrôle des sessions, validation, déconnexion et calcul de couverture. Vérifier aussi le démarrage PostgreSQL via Compose avant déploiement.

Vérifications effectuées pour cette tranche : 5 tests API, 3 tests d’intervalles navigateur, compilation TypeScript et build Vite ; construction des deux images et démarrage Compose ; contrôle HTTP à travers Nginx avec connexion, catalogue, création de session, ingestion, déduplication et couverture sur PostgreSQL. Pas encore de vérification visuelle ni de test de lecture vidéo automatisé dans un navigateur.

Scénario manuel : connexion → ouvrir une vidéo → lire → pause → saut en avant → retour arrière → vérifier la couverture → fermer/réouvrir pour reprendre → modifier les intérêts → comparer les deux méthodes de recommandation → se déconnecter.

## Ce qui fonctionne

- Compte de démonstration avec mot de passe Argon2, sessions serveur expirant après 8 heures et déconnexion révoquant le jeton.
- Catalogue avec recherche et filtre de format ; profil avec intérêts.
- Lecture, vitesse, reprise, événements de lecture/pause/seek/attente/visibilité/fin.
- File mémoire bornée à 500 événements, lots, réessais et identifiants stables ; déduplication serveur.
- Intervalles continus de lecture et couverture calculée par union ; les sauts n’ajoutent pas de couverture.
- Favoris, utile/pas utile et deux classements : popularité par nombre d’apprenants distincts et similarité lexicale des intérêts/tags.
- PostgreSQL persistant avec Compose ; SQLite pour les tests et le développement rapide.

## Limites de cette première tranche

- Le compte du pilote est provisionné au démarrage : pas encore d’interface d’administration, d’invitations ou de gestion des rôles.
- Les fichiers sont des liens publics de démonstration, pas des uploads privés S3. Les films Blender démontrent le lecteur ; leurs titres pédagogiques décrivent les exercices d’instrumentation, pas le contenu des films. Les ressources externes dépendent de leur hébergeur. Aucun contenu vidéo original n’est redistribué dans le dépôt.
- Schéma créé au démarrage pour cette version initiale : ajouter Alembic avant toute évolution du schéma sur des données existantes.
- L’authentification utilise un jeton Bearer conservé uniquement en mémoire navigateur ; un rechargement demande de se reconnecter. Le cookie HttpOnly prévu dans le cahier des charges viendra avec la consolidation de l’authentification et de CSRF. Utiliser HTTPS pour tout environnement partagé ; ajouter protection anti-bruteforce et gestion des comptes avant exposition publique.
- La file mémoire ne survit pas à la fermeture de l’onglet ; l’envoi final est sans garantie. Une panne prolongée peut produire des pertes, signalées dans le lecteur. L’onglet masqué ne prouve pas l’absence d’attention.
- L’API valide les événements, mais ne certifie pas leur authenticité physique : un client modifié peut fabriquer des interactions.
- Pas encore de journalisation des impressions/clics de recommandation, d’affectation A/B, de modèle enrichi, d’export, de tableau de bord ou de traitement de rétention/suppression. Les recommandations actuelles servent à tester le parcours, pas à annoncer un gain mesuré.
- Cette version ne doit pas collecter de données d’une cohorte réelle avant la mise en place de sa politique de données et des contrôles d’accès prévus au backlog.

## Suite proposée

1. Migrations Alembic, invitations et rôles administrateur/apprenant.
2. Uploads privés MP4/PDF et accès temporaire S3.
3. Impressions/clics attribués, file persistante et diagnostics de collecte.
4. Tableau de bord, export pseudonymisé, rétention/suppression.
5. Modèles enrichis et protocole d’évaluation reproductible.
