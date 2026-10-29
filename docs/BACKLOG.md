# Backlog et organisation

## Répartition indicative

| Ingénieur | Responsabilité principale |
|---|---|
| I1 | Frontend, catalogue et parcours apprenant |
| I2 | API, authentification, schéma et administration |
| I3 | Lecteur vidéo, accès aux fichiers et collecte navigateur |
| I4 | Ingestion, indicateurs, exports et qualité des données |
| I5 | Recommandations, protocole d’évaluation et tableau de bord |

Chaque lot est relu par un autre ingénieur. Convenez des schémas API et événements dès la première semaine ; utilisez des réponses simulées pour avancer sur le frontend sans attendre le backend.

## Tickets à créer dans GitHub

| ID | Priorité | Responsable | Travail et critères d’acceptation | Dépendances |
|---|---|---|---|---|
| MVP-01 | P0 | I2 | Initialiser frontend/backend, Compose, PostgreSQL, configuration exemple sans secrets et CI ; démarrage documenté | — |
| MVP-02 | P0 | I2 | Modèles et migrations, comptes invités et rôles ; accès refusé aux ressources non autorisées | 01 |
| MVP-03 | P0 | I2 | API cours/ressources, recherche, filtres, pagination et archivage ; données de démonstration | 02 |
| MVP-04 | P0 | I3 | Upload admin MP4/PDF, stockage privé et URLs temporaires ; contrôles taille/type et autorisation | 02 |
| MVP-05 | P0 | I1 | Connexion, profil, catalogue et pages détail ; états vide, chargement et erreur | 03 |
| MVP-06 | P0 | I3 | Lecteur HTML5, vitesse, seek et reprise ; reprise automatique distinguée des actions utilisateur | 04, 05 |
| MVP-07 | P0 | I3 | Instrumentation selon EVENTS.md, file bornée, lots et réessais ; lecture utilisable hors connexion temporaire | 06 |
| MVP-08 | P0 | I4 | POST /events/batch, validation, droits et déduplication ; rejouer un lot ne double pas les lignes | 02 |
| MVP-09 | P0 | I4 | Couverture, répétitions et progression ; exemple 0–30/90–120/100–120 validé | 07, 08 |
| MVP-10 | P0 | I1 | Favoris, utile/pas utile et reprise de lecture ; état conservé après reconnexion | 05, 09 |
| MVP-11 | P0 | I5 | Interface commune, populaire/aléatoire et similarité de contenu ; repli pour profil vide et ressources archivées exclues | 03 |
| MVP-12 | P0 | I1 + I5 | Section Pour vous, impressions visibles et clics attribués ; modèle/version/rang persistés | 05, 08, 11 |
| MVP-13 | P0 | I5 | Variante avec signaux vidéo et évaluation temporelle reproductible ; rapport comparatif et configuration sauvegardés | 09, 11, 12 |
| MVP-14 | P0 | I4 + I5 | Tableau de bord, carte des passages et export pseudonymisé ; permissions admin testées | 09, 12 |
| MVP-15 | P0 | Tous | Notice de collecte, rétention, suppression, contrôle des droits et parcours complet ; README d’exécution vérifié | 01–14 |
| MVP-16 | P1 | I5 | Quiz courts et rapprochement exploratoire avec signaux vidéo, sans inférence automatique de compréhension | 10 |
| MVP-17 | P1 | I5 | Filtrage collaboratif et affectation expérimentale stable si le volume le permet | 13 |

## Planning indicatif sur 4 semaines

1. Semaine 1 : fondations, contrats, authentification, catalogue, stockage et modèles de référence.
2. Semaine 2 : lecteur, instrumentation, ingestion, retours explicites et recommandations visibles.
3. Semaine 3 : indicateurs, variante enrichie, évaluation hors ligne, tableau de bord.
4. Semaine 4 : intégration, tests de fiabilité et d’accès, documentation et pilote.

Si le planning est trop serré, reporter les P1, la carte détaillée et les raffinements du tableau de bord. Conserver les contrôles d’accès, les événements fiables et les modèles de référence : ils conditionnent la validité de l’expérience.

## Vérifications importantes

- Ingestion : doublons, événements désordonnés, données invalides, reprise après coupure et lots partiellement rejetés.
- Vidéo : pause, buffering, seek clavier/barre/bouton, changement de vitesse, onglet masqué et reprise automatique.
- Indicateurs : intervalles qui se chevauchent, sauts, fin atteinte sans couverture complète et sessions multiples.
- Sécurité : isolation des comptes, routes admin, uploads, exports, expiration des URLs et absence de secrets dans le dépôt.
- Recommandations : nouveaux comptes, aucun candidat, contenu archivé, reproductibilité et absence de fuite temporelle.
- Parcours de démonstration : importer une vidéo, la consulter, retrouver les événements, reprendre la lecture et comparer deux modèles.

## Organisation du dépôt à l’implémentation

```text
frontend/                 # React et instrumentation du lecteur
backend/app/              # FastAPI, modèles, API et recommandations
backend/tests/            # Ingestion, droits, indicateurs et recommandations
experiments/              # Configurations et rapports sans données personnelles
scripts/                  # Seed, calcul des caractéristiques et évaluation
docs/                     # Architecture, événements et backlog
compose.yaml
.env.example
.github/workflows/ci.yml
```

Les tickets ci-dessus constituent un backlog proposé ; leur présence dans ce document ne signifie pas que les issues GitHub ont déjà été créées.
