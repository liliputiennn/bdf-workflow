# TikTok : comment publier vraiment les Shorts (état au 2026-11-09)

Note de recherche, faite dans la documentation officielle de TikTok (developers.tiktok.com) et sur les pages des outils tiers. Rien n'est contourné : tout ce qui suit passe par l'API officielle ou par toi.

## Ce que dit TikTok

| Sujet | Règle (source : documentation « Content Posting API » et « Content Sharing Guidelines ») |
|---|---|
| **Publication directe** (`video.publish`, point d'entrée `/v2/post/publish/video/init/`) | La vidéo apparaît directement sur le profil. **Application non auditée : tout est forcé en « privé » (visibilité `SELF_ONLY`)**, au plus 5 comptes qui publient par 24 h, et le compte doit lui-même être privé au moment de publier. |
| **Envoi dans la boîte de réception** (`video.upload`, `/v2/post/publish/inbox/video/init/`) | La vidéo arrive en brouillon ; TikTok notifie ; **c'est toi qui touches « Publier »** (30 s par vidéo). La page ne parle pas des limites de visibilité de l'audit pour ce mode. En pratique : environ 5 envois en attente par 24 h et par compte (constaté et déjà géré par le programme : on en envoie 4). |
| **Audit** | Un formulaire sur la page « Content Posting API » du portail. Il vérifie le respect des conditions de TikTok. Réponse en « quelques jours à deux semaines » selon des guides tiers (pas de délai officiel). Une fois passé : toutes les visibilités sont possibles. |
| **Limites même après audit** | Plafond de créateurs actifs par 24 h fixé selon ta demande d'audit ; environ 15 publications par jour et par créateur (toutes applications confondues). |
| **Obligations d'interface** | L'application doit montrer le pseudo du créateur, laisser **choisir manuellement** la visibilité et les interactions (rien de pré-coché), afficher la mention sur l'usage de la musique, montrer un aperçu, ne pas ajouter de filigrane promotionnel. |
| **Ce que TikTok refuse à l'audit** | « Un outil pour envoyer du contenu sur des comptes que **toi ou ton équipe gérez** n'est pas acceptable », les applications limitées à un usage interne ou de test, et les applications qui recopient du contenu d'autres plateformes. L'application doit viser un large public. |

## Le point à comprendre

Notre programme est un outil **personnel** qui publie sur **tes** comptes. Selon les règles ci-dessus, **TikTok risque de refuser l'audit** pour ce type d'application (usage interne). Ce n'est pas une certitude (tu peux déposer la demande et voir), mais il ne faut pas bâtir le projet dessus. Le mode « publication directe » est donc codé, mais **éteint** : il ne s'allume que si tu écris toi-même `"audit_confirme": true` dans le profil de la chaîne, après avoir reçu l'accord écrit de TikTok.

## Comparaison honnête

| Option | Gratuit ? | Publie vraiment en public, sans toi ? | Ce que ça demande | Risque |
|---|---|---|---|---|
| **A. Boîte de réception (ce que fait le programme, par défaut)** | Oui | **Non** : tu touches « Publier » (30 s par vidéo, 4 par jour et par compte au plus) | Application développeur (bac à sable suffisant), un jeton par compte (`auth.py --chaine <id>`) | Aucun : usage prévu par TikTok |
| **B. Publication directe avec notre application, avant audit** | Oui | **Non** : tout reste **privé** | Portée `video.publish` | Aucun, mais inutile pour atteindre le public |
| **C. Publication directe avec notre application, après audit** | Oui | Oui, si l'audit est accordé | Audit TikTok (voir ci-dessus), interface d'application conforme (choix manuel de la visibilité…) : l'outil automatique actuel **ne respecte pas** ces obligations d'interface | Audit probablement refusé pour un outil à usage personnel ; ne jamais publier en public sans accord |
| **D. Planificateur tiers déjà audité** (Buffer, et d'autres) | Essai gratuit seulement (Buffer : 14 jours ; d'autres : 7 jours puis environ 8 $ par mois). **Aucun planificateur durablement gratuit avec publication automatique trouvé** | Oui pour les outils déjà audités, avec quelques limites (pas de sons tendance) | Un abonnement ; envoyer les vidéos à l'outil (à la main ou par leur propre API) | Faible : API officielle. Vérifie leurs conditions et le nombre de comptes inclus |
| **E. Outil libre auto-hébergé (par exemple Postiz)** | Le logiciel est gratuit | **Non** tant que **ta** propre application TikTok n'est pas auditée : il force le « privé » | Domaine HTTPS vérifié, vidéos accessibles publiquement en HTTPS, ta propre application | Même limite que B : aucun gain |
| **F. Robot qui pilote le site ou l'application TikTok (clics simulés, faux navigateur)** | – | – | – | **Interdit par les conditions de TikTok et par nos règles** : risque de bannissement du compte. **Ne pas faire.** |

## Ce qui est possible aujourd'hui

- Envoyer automatiquement les Shorts de **chaque chaîne que tu choisis** dans la boîte de réception de **son propre** compte TikTok (un jeton par compte). Toi : un toucher sur « Publier ».
- Préparer, pour les chaînes dont le jeton manque ou est expiré, un **paquet de secours** (vidéo + légende) à déposer à la main.

## Ce qui demande une démarche de ta part

1. Un compte TikTok par chaîne concernée (à créer **toi-même** ; je ne crée aucun compte).
2. Une application développeur TikTok (celle du bac à sable convient pour la boîte de réception) et la connexion de chaque compte (`CONNECTER-TIKTOK.md`).
3. Si tu veux tenter la publication directe : demander l'audit, **puis** écrire toi-même `audit_confirme`. Prévoir un refus possible.
4. Si tu veux une publication sans toucher à ton téléphone **dès maintenant** : payer un planificateur audité (option D), à comparer à 30 secondes de ton temps par vidéo.

## Ce qui est impossible (sans risque pour tes comptes)

- Publier en **public** automatiquement, gratuitement, avec une application non auditée : TikTok force le privé.
- Contourner l'audit, la vérification humaine, les CAPTCHA ou la détection de robots.
- Un compte TikTok créé ou connecté par le programme à ta place (mot de passe jamais demandé ni stocké).

## Cas particulier à surveiller

Les chaînes **Sommeil** et **Musique pour enfants** visent des enfants : TikTok et YouTube y appliquent des règles plus strictes. Leur champ `tiktok` reste éteint tant que tu ne l'as pas allumé toi-même, et il vaut mieux relire les premières vidéos avant.

## Sources consultées (2026-11-09)

- Content Sharing Guidelines : <https://developers.tiktok.com/doc/content-sharing-guidelines>
- Direct Post (référence) : <https://developers.tiktok.com/doc/content-posting-api-reference-direct-post>
- Envoi vers la boîte de réception (Upload) : <https://developers.tiktok.com/doc/content-posting-api-get-started-upload-content>
- Postiz (auto-hébergé, limites avant audit) : <https://docs.postiz.com/providers/tiktok.md>
- Buffer : <https://buffer.com/TikTok>
- Comparatifs de planificateurs (indicatifs, pages commerciales) : <https://contentstudio.io/blog/tiktok-schedulers>
