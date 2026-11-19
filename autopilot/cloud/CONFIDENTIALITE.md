# Règles de confidentialité — « Bureau des Faits » / La Débrouille

*Dernière mise à jour : 19 novembre 2026*

« Bureau des Faits » (aussi appelé « La Débrouille ») est un **outil personnel d'automatisation**. Il n'est pas proposé au public : il n'a qu'un seul utilisateur, son propriétaire, qui l'utilise pour publier ses propres vidéos sur ses propres chaînes.

## Ce que l'outil demande à Google

L'outil demande l'accès à l'**API YouTube** du compte de son propriétaire, uniquement pour **envoyer et programmer les vidéos du propriétaire sur sa propre chaîne YouTube** (miniature, titre, description, date de publication).

## Les données utilisées

- L'outil ne lit, ne collecte et ne conserve **aucune donnée personnelle d'autres personnes** (pas de spectateurs, pas de commentaires, pas d'abonnés).
- Le seul élément sensible est le **jeton d'accès** du compte du propriétaire. Il est conservé dans les *secrets chiffrés* de GitHub Actions et n'est jamais écrit dans les journaux ni dans le code.
- Les vidéos publiées sont créées par le propriétaire ; elles ne contiennent aucune donnée issue de l'API YouTube.

## Partage des données

Aucune donnée obtenue via les API Google n'est vendue, transmise, partagée ni utilisée à d'autres fins que la publication décrite ci-dessus. L'utilisation des informations reçues des API Google respecte la
[politique de Google sur les données utilisateur des services d'API](https://developers.google.com/terms/api-services-user-data-policy), y compris ses exigences d'utilisation limitée.

## Retirer l'accès

Le propriétaire peut à tout moment retirer l'accès de l'outil à son compte sur <https://myaccount.google.com/permissions>. Le jeton devient alors inutilisable.

## Contact

Pour toute question : ouvrir un ticket (« issue ») sur ce dépôt GitHub.
