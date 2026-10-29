# Version 0.3 — analyse des interactions

## Mise à jour depuis la version 0.2

Conserver le même répertoire et projet Compose ainsi que le fichier `.env`. Sauvegarder la base avant mise à jour comme indiqué dans [UPGRADE.md](UPGRADE.md). Si des fichiers suivis ont été modifiés localement, conserver ces modifications avec `git stash push -m "Configuration locale"` avant de changer de branche, puis les examiner avant de les réappliquer.

```sh
git fetch origin
git switch feat/interaction-analytics
docker compose up --build -d
docker compose logs --tail=60 api
```

Aucune nouvelle variable obligatoire. Le port 8013 et PostgreSQL 17 restent configurables dans `.env`. Ne pas supprimer les volumes. La migration 0003 ajoute les diagnostics d’ingestion, la politique de conservation et les dates nécessaires à la rétention. Elle conserve les comptes et les événements existants.

Connectez-vous comme administrateur, ouvrez **Administration → Analyse des interactions**. Le compte apprenant n’a accès à aucune des routes d’analyse, export, politique ou suppression.

## Tableau de bord et définitions

Les périodes (1 à 3650 jours) utilisent la date de réception serveur `received_at`, pas l’horloge du navigateur. La couverture affichée est celle des interactions conservées sur la période, pas nécessairement celle de toute la vie du compte.

| Indicateur | Calcul |
|---|---|
| Ouvertures vidéo | Sessions créées dans la période, ou ayant un événement reçu dans cette période ; union sans doublon |
| Participants par vidéo | Utilisateurs distincts ayant une telle session ou un événement ; les ouvertures sans lecture comptent avec couverture zéro |
| Couverture individuelle | Union des intervalles heartbeat, bornée à la durée de la vidéo, divisée par cette durée |
| Couverture moyenne | Moyenne des couvertures individuelles des participants de la vidéo |
| Complétion | Proportion de ces participants dont la couverture est au moins 90 % |
| Secondes revues | Somme des portions parcourues, moins leur union distincte, par participant |
| Retours / avances | Déplacements arrière / avant ; les seeks marqués resume sont exclus |
| Participants actifs | Utilisateurs ayant au moins un événement conservé dans la période, administrateurs de test compris |

Les sessions antérieures à la migration n’ont pas de date d’ouverture connue : celle-ci reste nulle. Elles sont comptées lorsqu’un événement les rattache à la période, sans inventer une nouvelle ouverture au jour de la mise à jour. Les avis historiques reçoivent une date de migration comme point de départ conservateur pour leur rétention.

La carte des passages découpe la vidéo en segments de 10 secondes, élargis pour les longues vidéos afin de rester sous 300 segments. Chaque case indique un nombre de participants distincts ayant visionné, revu ou sauté une partie de ce segment. Les catégories peuvent se recouper : un segment sauté peut être regardé plus tard. Les passages revus sont un comportement observé, pas un diagnostic de compréhension.

La vue par participant regroupe les sessions et la couverture par ressource. Les identifiants y sont pseudonymisés ; l’historique est limité aux 200 derniers événements de la sélection, avec indication si tronqué.

## Qualité des données

Chaque lot d’ingestion valide produit des compteurs d’événements acceptés, doublons ignorés et rejets. Ces diagnostics commencent en 0.3 : les volumes des versions précédentes ne sont pas reconstitués. Les erreurs de requête HTTP (401/413/422) et les événements qui n’ont jamais atteint le serveur ne sont pas comptabilisés.

Les autres indicateurs signalent des séquences répétées dans une session et un écart supérieur à 5 minutes entre les horodatages client/serveur. Ils aident à examiner les données sans conclure automatiquement à une fraude ou à un défaut d’attention.

## Export de recherche

Le bouton **Exporter JSON** produit un fichier au format versionné : métadonnées de période, événements et métadonnées minimales des ressources (identifiant, type, durée, archivage). Il ne contient ni e-mail, ni mot de passe, ni identifiant brut d’utilisateur/session/événement, ni URL de média, ni champ libre de payload. Les positions, vitesses, visibilité et raisons contrôlées sont conservées.

Les pseudonymes HMAC-SHA256 sont stables au sein d’une installation. Leur clé aléatoire reste en base et n’est pas exposée par les API. Préserver la base pour garder la correspondance entre exports ; ces données sont pseudonymisées, pas anonymes. L’écran de gestion de suppression permet à l’administrateur d’identifier un compte par e-mail, séparément des vues et exports analytiques.

Un export est limité à 50 000 événements ; les vues d’analyse à 100 000. Au-delà, l’API refuse explicitement la requête et demande une période plus courte. Aucun fichier tronqué n’est téléchargé. L’export reflète les données au moment de la requête ; la purge ou de nouvelles interactions peuvent modifier les totaux entre deux téléchargements.

## Rétention et suppression

La politique commence avec une durée de 90 jours et une purge automatique **désactivée**. Enregistrer une durée de 1 à 3650 jours, prévisualiser les lignes éligibles, puis activer l’automatisation ou exécuter une purge immédiate après confirmation dans l’interface. Le traitement automatique vérifie la politique au démarrage puis toutes les heures ; le pilote utilise une seule instance API.

La purge utilise les dates serveur : événements, compteurs de lots et avis trop anciens sont supprimés. Les sessions d’apprentissage anciennes ou de date inconnue ne sont supprimées que si elles n’ont plus d’événement récent ; les sessions d’authentification expirées sont également nettoyées. Les comptes et profils ne sont pas supprimés par rétention. Les indicateurs sont recalculés sur les données restantes, sans agrégats historiques cachés.

La suppression d’un participant efface en transaction son compte/profil, ses événements, avis, diagnostics, sessions de lecture et sessions de connexion. Elle révoque ses accès et le retire des calculs et futurs exports. Les comptes administrateurs sont exclus de cette action. Pour supprimer le compte de démonstration configuré, vider d’abord DEMO_EMAIL et DEMO_PASSWORD dans `.env`, recréer l’API, puis supprimer le compte : sinon le bootstrap le recréerait au redémarrage.

Les exports téléchargés et les sauvegardes ne sont pas effacés à distance par la plateforme : leur conservation et leur suppression doivent être gérées séparément par le responsable du cours. Les contenus pédagogiques restent présents après suppression d’un participant.

## Vérifications

Les tests couvrent les parcours lire/sauter/revoir, les dénominateurs des indicateurs, le seuil de complétion, les pseudonymes et l’exclusion des champs libres, les droits, les diagnostics, la rétention fondée sur la réception serveur, et la suppression complète avec révocation. La migration de v0.1 jusqu’à 0003 conserve un compte, une session et un événement historiques.

La mise à jour d’une base PostgreSQL 17 de version 0.2 a également été vérifiée via Compose : calculs de couverture et répétition, export, droits d’accès, prévisualisation de purge et suppression du compte avec révocation. TypeScript et le build Vite sont contrôlés. Pas de validation visuelle automatisée dans un navigateur.
