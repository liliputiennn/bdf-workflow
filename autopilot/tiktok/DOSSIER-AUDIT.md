# Dossier pour demander l'audit TikTok (à déposer par TOI, honnêtement)

Rien n'a été déposé en ton nom et rien ne le sera : le formulaire engage ta responsabilité et celle de ton compte développeur. Ce dossier te donne la matière. **Écris dans le formulaire ce qui est vrai, rien d'autre** : une demande qui décrit un autre produit que celui qui existe est refusée, et elle peut faire fermer ton compte développeur.

Sources : conditions et guides de TikTok (<https://developers.tiktok.com/doc/content-sharing-guidelines>, <https://developers.tiktok.com/doc/content-posting-api-get-started>, formulaire d'audit : <https://developers.tiktok.com/application/content-posting-api>). La page de démarrage ne publie pas le délai ni les critères exacts de l'audit : relis le formulaire lui-même avant de répondre.

## 1. Évaluation franche de tes chances

**Faibles, et je ne peux pas les chiffrer.** Raisons :

1. TikTok écrit (guides cités dans `OPTIONS-PUBLICATION.md`) qu'un outil servant à envoyer du contenu sur des comptes que **toi ou ton équipe** gérez n'est pas acceptable, et que les applications à usage interne ou de test sont refusées. Notre outil est exactement cela : ton programme, tes comptes.
2. Il publie sans qu'un humain choisisse la visibilité ni confirme chaque vidéo, ce qui est l'inverse de l'interface exigée (voir §4).
3. Les contenus sont générés (voix de synthèse, images dessinées par le code) : ce n'est pas interdit, mais l'étiquette « généré par IA » est obligatoire et le contenu répétitif en série est mal vu.

Ce qui joue pour toi : des conditions respectées à la lettre, des vidéos originales, un site public avec politique de confidentialité, une démonstration honnête. Si l'audit est refusé, **rien n'est perdu** : la boîte de réception et la voie Upload-Post (section « Voie automatique publique » de `OPTIONS-PUBLICATION.md`) fonctionnent sans audit. Je recommande d'utiliser Upload-Post dès maintenant et de ne tenter l'audit que si tu veux, un jour, publier avec ta propre application.

**Même avec l'audit accordé, la publication 100 % automatique et muette reste hors règles** : l'interface exigée oblige à montrer un choix manuel de la visibilité et une confirmation de l'utilisateur à chaque publication. L'audit ne remplace donc pas Upload-Post pour l'automatisation : il donne une application avec laquelle un humain publie lui-même, en public, depuis une page web à nous.

## 2. Description de l'application (à adapter, sans exagérer)

- **Nom** : Bureau des Faits (à changer si tu en choisis un autre ; il doit correspondre à ce que l'utilisateur voit).
- **Qui l'utilise** : une application web où un créateur de contenu connecte son compte TikTok, relit une vidéo courte et la publie. *Cela n'est vrai que si l'interface du §4 est construite. Si l'outil reste réservé à toi, écris « outil personnel du créateur » et attends-toi au refus.*
- **Finalité** : permettre au créateur de publier sur son compte les Shorts qu'il a produits (aucune copie de contenu d'autres plateformes, aucun contenu d'autrui).
- **Produits demandés** : Login Kit (connexion), Content Posting API avec « Direct Post ».
- **Portées** : `user.info.basic` (pseudo affiché), `video.publish`. Ne demande pas `video.upload` si cette application ne s'en sert pas.
- **Origine du contenu** : vidéos créées par le créateur, voix de synthèse et images produites par ordinateur, étiquetées « contenu généré par IA ».
- **Ce que l'application ne fait pas** : ne publie rien sans action de l'utilisateur, ne contourne aucune limite, ne collecte rien au-delà du pseudo et du jeton, aucun filigrane promotionnel.

## 3. Pièces à préparer (toi)

- Site public en HTTPS (domaine vérifié) avec : page d'accueil expliquant le produit, **politique de confidentialité**, **conditions d'utilisation**, adresse de contact.
- URL de redirection OAuth enregistrée dans le portail ; icône 1024×1024 ; nom de l'application identique partout.
- **Vidéo de démonstration** (2 à 4 minutes, écran enregistré, sans coupure) montrant dans l'ordre :
  1. la page d'accueil et le bouton « Se connecter avec TikTok » ;
  2. l'écran d'autorisation TikTok et le retour dans l'application (pseudo et photo du compte visibles) ;
  3. le choix d'une vidéo et son **aperçu** ;
  4. la légende modifiable, **la liste de visibilité vide par défaut** et les cases commentaires / duo / collage non cochées par défaut ;
  5. l'interrupteur « contenu commercial » (désactivé par défaut) et, s'il est activé, les mentions obligatoires ;
  6. la déclaration d'usage de la musique (« En publiant, tu acceptes la Politique d'usage de la musique de TikTok ») ;
  7. le clic de l'utilisateur sur « Publier », puis l'état de traitement et la vidéo sur le profil (tant que l'audit n'est pas passé elle est privée : dis-le à voix haute).
- Captures fixes de chaque écran ci-dessus.
- Un compte de démonstration seulement si le formulaire en demande un : crée un compte dédié, **ne donne jamais ton vrai mot de passe**.

## 4. Ce qu'il faut changer dans NOTRE application avant de déposer

Aujourd'hui `envoi.py` publie seul : il fixe la visibilité (réglage `visibilite`, public par défaut), ne montre pas le pseudo, ne demande aucun consentement. Pour respecter l'interface obligatoire de TikTok il faut **construire une page web** (elle n'existe pas encore) avec :

| Obligation TikTok | À construire |
|---|---|
| Afficher le pseudo du créateur | Appeler `user.info.basic`, afficher pseudo + photo avant tout envoi |
| Interroger les possibilités du compte | Appeler `creator_info/query` à chaque publication (déjà codé dans `client.py`), n'afficher que les visibilités permises |
| Choix **manuel** de la visibilité, **sans valeur par défaut** | Liste vide au départ ; bouton « Publier » inactif tant que rien n'est choisi |
| Commentaires, duo, collage : cases **non cochées** par défaut | Trois cases décochées, grisées si le compte les interdit |
| Divulgation de contenu commercial | Interrupteur désactivé par défaut + mentions « marque / contenu de marque » |
| Mention d'usage de la musique | Texte obligatoire avant le bouton |
| Aperçu de la vidéo et de la légende | Lecteur vidéo + légende modifiable |
| Consentement explicite à chaque publication | Un clic humain sur « Publier » ; pas de file automatique |
| Pas de filigrane promotionnel | Déjà respecté |
| Étiquette « généré par IA » | Case cochée par défaut pour nos vidéos |
| Statut après envoi | Afficher l'état renvoyé par `status/fetch` |

Travail estimé : une petite application web hébergée en HTTPS (quelques jours de développement) et une session de test pour la vidéo de démonstration. Ce travail est **inutile** si tu choisis Upload-Post. Je ne l'ai pas commencé ; dis-moi si tu veux que je le construise.

## 5. Délais et limites après l'audit

- Délai : pas de chiffre officiel trouvé ; des guides tiers parlent de quelques jours à deux semaines, avec des allers-retours possibles si la démonstration est incomplète.
- Après accord : toutes les visibilités possibles ; environ 15 publications par jour et par créateur ; plafond de créateurs actifs par 24 h fixé selon ta demande.
- Avant accord : tout reste privé (`SELF_ONLY`) et le compte doit être privé au moment de publier.
- Quand (et seulement quand) tu auras l'accord écrit de TikTok, tu écriras toi-même `"audit_confirme": true` dans `autopilot/chaines/<id>.json` ; je ne l'écris jamais.
