# Contrat des interactions vidéo — v1

## Événements

| Type | Déclencheur et données spécifiques |
|---|---|
| play | Intention de démarrer/reprendre, position |
| playing | Lecture réellement démarrée/reprise après chargement |
| pause | Pause observée, position ; ne pas la qualifier automatiquement de volontaire |
| seek | Déplacement terminé, from_seconds et to_seconds ; arrière si arrivée < départ |
| rate_change | Ancienne et nouvelle vitesse |
| heartbeat | Toutes les 10 à 15 secondes pendant la lecture ; intervalle joué et position |
| waiting | Attente de données du lecteur |
| visibility_change | Onglet visible/masqué ; ce signal ne prouve pas l’attention |
| ended | Fin atteinte ; ne prouve pas que toute la vidéo a été regardée |
| recommendation_impression | Élément effectivement visible, request_id et item_id |
| recommendation_click | Élément cliqué, request_id et item_id |
| resource_download | Demande d’accès au fichier ; ne prouve pas une lecture ni un téléchargement complet |

Un changement de position automatique lors de la reprise est marqué `reason: resume`. Un seek capturé via seeking/seeked conserve la dernière position stable avant le déplacement. Les intervalles joués sont interrompus lors d’un seek, d’une pause, d’une attente ou d’un changement de vitesse.

## Enveloppe d’un événement

```json
{
  "schema_version": 1,
  "event_id": "a5bd9901-dcd6-43e0-b418-75063ac810ce",
  "session_id": "5d31eb7d-7921-44ae-a9b6-4480ad0cc892",
  "sequence": 12,
  "resource_id": "resource-42",
  "event_type": "seek",
  "occurred_at": "2026-10-29T14:30:00Z",
  "position_seconds": 95,
  "payload": {
    "from_seconds": 125,
    "to_seconds": 95,
    "reason": "user"
  }
}
```

L’API déduit l’utilisateur depuis la session authentifiée, ajoute received_at et vérifie que la ressource et la session sont autorisées. Elle ne fait pas confiance à un user_id transmis par le navigateur. Utiliser une session de lecture distincte par onglet/ressource pour éviter de mélanger les séquences.

Validation : types d’événements autorisés, dates ISO, valeurs finies et non négatives, positions bornées à la durée connue avec une tolérance documentée, limites de taille et de fréquence. Les champs requis varient par type. Les événements clients restent des observations non fiables, insuffisantes pour certifier une présence ou une réussite.

## Livraison

- Envoyer un lot toutes les 10–15 secondes ou à 20 événements ; maximum serveur proposé : 100 événements et 256 Ko par lot.
- Garder une file locale bornée, réessayer avec délai croissant et conserver le même event_id.
- Le serveur distingue événements acceptés, déjà reçus et rejetés avec motif ; les doublons sont traités comme livrés.
- À pagehide, tenter un envoi avec keepalive ou sendBeacon selon la configuration d’authentification/CSRF ; aucune garantie de livraison à la fermeture.
- Utiliser sequence et une horloge monotone locale pour les intervalles ; conserver les horodatages client et serveur pour diagnostiquer les écarts.
- La collecte ne bloque jamais la lecture. Exposer les pertes estimées et erreurs d’ingestion dans les diagnostics.

## Indicateurs dérivés

- Couverture : longueur de l’union des intervalles réellement joués / durée de la vidéo ; bornée à 100 %.
- Répétition : chevauchement des intervalles joués, en distinguant retour manuel et reprise automatique.
- Temps de lecture : temps actif corrigé des attentes et pauses ; conserver séparément la durée du média parcouru et la durée murale.
- Complétion : seuil configurable de couverture, par exemple 90 %, documenté dans chaque expérience.
- Abandon : consultation sans reprise pendant une fenêtre définie, par exemple 7 jours ; exclure les sessions trop récentes de cette mesure.
- Carte de consultation : agrégats par segments de 10 secondes, en évitant qu’un utilisateur très actif domine toute la carte.

Exemple de validation : lecture de 0 à 30 s, saut à 90 s, lecture jusqu’à 120 s, retour à 100 s puis lecture jusqu’à 120 s. Couverture : 60 s distinctes, répétition : 20 s. La portion 30–90 s reste non visionnée.

## Protection des données

Informer les participants des événements collectés et de leur finalité. Séparer identité et identifiant analytique ; restreindre les exports au rôle administrateur. Proposition de rétention : événements bruts 90 jours, configurable avant le pilote ; supprimer ensuite les données ou conserver uniquement des agrégats effectivement anonymisés. Prévoir suppression des données d’un participant, des exports gérés et des caractéristiques dérivées, ainsi qu’une politique pour les sauvegardes.

Les pauses, répétitions et sauts ne permettent pas seuls de conclure à une difficulté ou à une bonne compréhension. Les quiz et retours explicites apportent des observations complémentaires.
