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

Ouvrir http://localhost:8013. Utiliser DEMO_EMAIL et DEMO_PASSWORD de `.env` pour se connecter. Le compte est créé uniquement s’il n’existe pas déjà. Modifier la variable ne modifie pas le mot de passe d’un compte existant. Le volume PostgreSQL conserve les utilisateurs et les événements après redémarrage.

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

Vérifications effectuées pour cette tranche : 7 tests API, 3 tests d’intervalles navigateur, compilation TypeScript et build Vite ; construction des deux images et démarrage Compose ; contrôle HTTP à travers Nginx avec connexion, catalogue, création de session, ingestion, déduplication et couverture sur PostgreSQL. Pas encore de vérification visuelle ni de test de lecture vidéo automatisé dans un navigateur.

Scénario manuel : connexion → ouvrir une vidéo → lire → pause → saut en avant → retour arrière → vérifier la couverture → fermer/réouvrir pour reprendre → modifier les intérêts → comparer les deux méthodes de recommandation → se déconnecter.

## Version 0.2 : administration et contenus privés

- Connexion administrateur via ADMIN_EMAIL et ADMIN_PASSWORD (12 caractères minimum), puis bouton Administration dans la barre latérale.
- Création/modification/archivage des cours et ressources ; les archives conservent les événements existants.
- Import de MP4/PDF limité à 200 Mo, en flux, avec contrôle du type et de la signature de fichier. La durée du MP4 est lue dans le navigateur et reste une métadonnée fournie par l’administrateur ; ce contrôle ne remplace pas un transcodage ou une analyse antivirus.
- Création de comptes apprenants avec mot de passe initial ; seuls les administrateurs accèdent aux routes /admin.
- MinIO (construit depuis son dépôt officiel, version RELEASE.2025-09-07T16-13-09Z, commit 07c3a429bfed433e49018cb0f78a52145d4bedeb, licence AGPL-3.0 : https://github.com/minio/minio) conserve les fichiers dans un bucket privé. L’API délivre une URL signée pour 5 minutes après authentification et vérification de l’archivage. Une URL déjà délivrée reste valable jusqu’à son expiration. Le lecteur tente de renouveler une URL signée devenue invalide en conservant la position.
- Les URLs de médias ne sont pas conservées en base ; seuls les identifiants d’objets le sont. Les médias de démonstration historiques restent des liens publics.
- Migrations Alembic exécutées au démarrage d’une instance API. La base v0.1 connue est reprise automatiquement, sans réinitialisation. Voir [la mise à jour](UPGRADE.md).

Configuration locale : WEB_PORT=8013, POSTGRES_IMAGE=postgres:17-alpine, S3_PUBLIC_ENDPOINT=http://localhost:9010. Ne pas utiliser minio:9000 comme endpoint public : ce nom appartient au réseau Docker, pas au navigateur. Le port 9010 est lié à la boucle locale ; adapter l’adresse et l’exposition réseau pour un accès depuis une autre machine.

Sans Docker, définir aussi ADMIN_EMAIL/ADMIN_PASSWORD et les variables S3 de .env.example dans le terminal du backend. S3_ENDPOINT désigne le serveur accessible à l’API ; S3_PUBLIC_ENDPOINT celui accessible au navigateur. Pour lancer uniquement les migrations : `python -m app.migrate` depuis backend.

Scénario de validation : connexion admin → créer un cours → choisir MP4/PDF → enregistrer et importer → créer un compte apprenant → connexion apprenant → ouvrir la ressource → reprendre la lecture → connexion admin → archiver le cours → vérifier sa disparition du catalogue et des recommandations.

## Limites restantes

- Pas encore d’invitation par e-mail ni de changement/réinitialisation du mot de passe. Le compte admin de bootstrap est explicitement désigné par ADMIN_EMAIL ; ses identifiants existants ne sont pas remplacés au redémarrage.
- Les administrateurs gèrent tous les contenus du pilote, les apprenants ont accès à tous les cours actifs. Pas encore d’inscription à des cours particuliers.
- Un fichier publié ne se remplace pas : créer une nouvelle ressource permet de préserver la signification des événements historiques.
- La file d’événements navigateur reste en mémoire ; fermeture d’onglet et coupure prolongée peuvent perdre des événements.
- Les jetons d’authentification restent en mémoire ; rechargement = reconnexion. HTTPS, protection anti-bruteforce, gestion des comptes et politique de données restent nécessaires pour une exposition publique.
- Pas encore de suivi d’impressions/clics de recommandation, de tableau de bord, de traitement de rétention/suppression ni d’évaluation expérimentale.
- Les vidéos sont servies telles quelles : utiliser un MP4 compatible avec le navigateur. Pas encore de transcodage, de sous-titres importables ou de reprise automatique d’un upload interrompu.

## Vérifications

Les tests couvrent l’ancien parcours, les permissions admin/apprenant, le cycle d’import/archivage et la reprise d’une base v0.1 avec conservation des données. Le stockage est simulé dans les tests unitaires ; un contrôle Compose séparé vérifie PostgreSQL 17 et MinIO. Aucune validation visuelle automatisée dans un navigateur.

La première construction MinIO compile les sources Go et peut prendre plusieurs minutes ; les constructions suivantes utilisent le cache Docker.
