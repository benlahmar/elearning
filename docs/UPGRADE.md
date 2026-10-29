# Mise à jour vers la version 0.2

## Préserver la base existante

Sauvegarder avant mise à jour :

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > sauvegarde.sql
```

Ne pas supprimer le volume PostgreSQL et ne pas utiliser `docker compose down -v` pour cette mise à jour. Garder le même répertoire/projet Compose pour retrouver les volumes existants.

Cette version utilise PostgreSQL 17 par défaut, conformément au pilote. Si le volume a été créé par PostgreSQL 16, conserver `POSTGRES_IMAGE=postgres:16-alpine` dans `.env` : le passage de 16 à 17 exige une migration PostgreSQL séparée par dump/restauration ou pg_upgrade. Alembic fait évoluer les tables, pas le format du volume PostgreSQL.

## Compléter .env

Conserver les variables existantes et ajouter :

```dotenv
WEB_PORT=8013
POSTGRES_IMAGE=postgres:17-alpine
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=choisir-un-mot-de-passe-long
S3_ACCESS_KEY=learning-local-admin
S3_SECRET_KEY=choisir-un-secret-stockage-long
S3_PUBLIC_ENDPOINT=http://localhost:9010
```

ADMIN_EMAIL crée le compte administrateur s’il n’existe pas, ou attribue explicitement le rôle administrateur au compte existant correspondant. Le mot de passe d’un compte existant reste inchangé. Le compte DEMO_EMAIL reste apprenant, sauf si vous le désignez aussi comme administrateur.

## Démarrer

Si vous avez modifié compose.yaml localement, conservez une copie de ces modifications avant de changer de branche. Reportez le port et la version PostgreSQL dans les variables ci-dessus ; le nouveau Compose les lit directement.

```sh
git fetch origin
git switch feat/admin-private-content
docker compose up --build -d
docker compose logs --tail=60 api
```

La migration reconnaît les six tables de v0.1, les marque comme révision initiale puis ajoute rôles, cours, archivage et clés de stockage. Elle ne supprime pas les comptes, sessions, événements ou avis. Un schéma inconnu non versionné bloque le démarrage avec un message explicite ; ne pas forcer un stamp sans analyse.

Ouvrir http://localhost:8013, se connecter avec ADMIN_EMAIL puis choisir Administration. Créer un cours, importer une vidéo ou un PDF et vérifier sa lecture avec un compte apprenant. Les fichiers sont conservés dans le volume minio_data, à sauvegarder avec la base.
