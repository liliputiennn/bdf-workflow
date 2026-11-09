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
| **D. Planificateur tiers déjà audité** (voir la section « Voie automatique publique » : Upload-Post recommandé, 16 à 24 $ par mois) | Aucune offre gratuite durable avec API **et** TikTok **et** publication publique | Oui pour les outils déjà audités, avec quelques limites (pas de sons tendance) | Un abonnement ; envoyer les vidéos à l'outil (à la main ou par leur propre API) | Faible : API officielle. Vérifie leurs conditions et le nombre de comptes inclus |
| **E. Outil libre auto-hébergé (par exemple Postiz)** | Le logiciel est gratuit | **Non** tant que **ta** propre application TikTok n'est pas auditée : il force le « privé » | Domaine HTTPS vérifié, vidéos accessibles publiquement en HTTPS, ta propre application | Même limite que B : aucun gain |
| **F. Robot qui pilote le site ou l'application TikTok (clics simulés, faux navigateur)** | – | – | – | **Interdit par les conditions de TikTok et par nos règles** : risque de bannissement du compte. **Ne pas faire.** |

## Voie automatique publique (recherche complémentaire, 2026-11-09)

Objectif : publier en **public**, sans notification sur ton téléphone, depuis notre programme. Seule façon légitime : un service dont **l'application TikTok est déjà auditée** (le blocage « tout est privé » vient de l'application, pas du compte). Les prix viennent des pages des services ; **tout est à revérifier sur la page de prix avant de payer** (ils changent, et plusieurs chiffres viennent de pages de concurrents, signalées « indicatif »).

| Service | Offre gratuite utile ici ? | Publication publique directe | Envoi automatique depuis notre pipeline | Prix pour avoir l'API + TikTok |
|---|---|---|---|---|
| **Zernio** (ex-Late) | **Oui** : les **2 premiers comptes sociaux gratuits**, sans carte, publications illimitées, API complète (page de prix). TikTok compte parmi les 2 | Probable : les connexions récentes passent par l'**application « Business » du service, qui publie les vidéos en public seulement** (doc TikTok de Zernio). Le mot « audit » n'y figure pas : **non confirmé** | **Oui** : `POST /api/v1/media/presign` (dépôt), `POST /api/v1/posts` avec `publishNow`, suivi `GET /api/v1/posts/{id}` | **0 $** pour 2 comptes ; comptes 3 à 10 : 6 $/mois chacun, 11 à 100 : 3 $ chacun |
| **PostPeer** | 20 crédits gratuits (1 par post, donc environ 20 posts, pas renouvelés d'après leur page) | **Non sans ton propre audit** : leur propre article dit que la publication directe publique « requiert l'audit TikTok sur ton compte », sinon brouillon | API `POST /v1/posts` (vidéo par lien) | Au-delà : crédits payants (par exemple 33 $/mois pour 2 000). **Pas de moteur codé** : ni gratuit durable, ni public confirmé |
| **Upload-Post** | **Non** : l'offre gratuite (10 envois/mois, 2 profils) **exclut TikTok** (erreur 403) | **Oui** : « son application approuvée », `post_mode=DIRECT_POST`, `privacy_level=PUBLIC_TO_EVERYONE` par défaut (si le compte TikTok n'est pas privé) | **Oui, API complète** : `POST /api/upload` (fichier ou lien), légende, `async_upload`, suivi `GET /api/uploadposts/status` | **Basic : 24 $/mois (16 $/mois en annuel, 192 $/an)**, 5 profils, envois illimités ; plafond TikTok 15 par compte et par 24 h |
| **Blotato** | Non (essai 7 jours, API exclue de l'essai) | Oui d'après Blotato (application auditée) ; **non vérifié par une source indépendante** | Oui (API REST) | Starter environ **29 $/mois**, jusqu'à 20 comptes connectés, mais **3 comptes TikTok différents au plus par 24 h** (indicatif, pages Blotato/concurrents) |
| **Postiz (cloud)** | Non | **Pas vérifié** : la page de prix ne dit pas si l'application TikTok est auditée ; auto-hébergé = **privé** (ta propre application non auditée) | Oui, API publique et CLI sur tous les plans | Standard 29 $/mois (23 $/mois annuel), 5 canaux |
| **Publer** | Offre gratuite sans API | Oui (`PUBLIC_TO_EVERYONE` possible dans l'API) | API réservée aux plans **Business/Enterprise** (prix non vérifié) ; un seul compte TikTok par appel | Prix non vérifié (plan Business) |
| **Metricool** | Gratuit : 1 marque, 20 posts/mois, **sans API** | Publication automatique possible dans l'interface | API seulement sur plan **Advanced** (environ 43 € à 53 $/mois selon les sources) ; l'API de publication TikTok n'est pas confirmée | Environ 43–53 $/mois, plus cher et moins clair |
| **Buffer** | TikTok connectable même en gratuit (3 canaux, 10 posts programmés par canal) | Dans l'application Buffer | **Non utilisable** : « Video uploads are not supported via the public API » (feuille de route Buffer) ; TikTok par l'API seulement par lien, mal documenté | – |
| **Planificateur natif de TikTok Studio** | Oui, gratuit | Oui | **Non** : manuel, navigateur, comptes Créateur/Business, de 15 minutes à 10 jours à l'avance (pas d'API ; des sources parlent de 30 jours selon les comptes) | – |

### Recommandation (mise à jour) : Zernio gratuit d'abord, Upload-Post Basic en repli payant

1. **Essaie Zernio (0 $)** : 2 comptes gratuits, publications illimitées, API complète, vidéo déposée par notre programme. **Avertissement honnête** : aucune page de Zernio ne dit que son application TikTok est « auditée ». Sa doc dit seulement que les comptes connectés par l'application Business publient en public. **Le test est donc décisif** : connecte un seul compte, envoie une vidéo avec `"visibilite": "PUBLIC_TO_EVERYONE"` sur un compte de test, regarde si elle est visible publiquement (profil vu depuis un autre compte). Si elle reste privée ou en brouillon, passe au repli.
2. **Repli payant : Upload-Post Basic** (24 $/mois, 16 $ en annuel), détaillé ci-dessous. Il affirme aussi avoir sa propre application approuvée, sans confirmation indépendante : **fais le même test d'une vidéo.**
3. **Limite de la voie gratuite** : 2 comptes **sociaux** au total, tous réseaux confondus (un compte YouTube relié à Zernio en compte un). Pour d'autres chaînes TikTok : 6 $/mois par compte de 3 à 10. Pour 5 chaînes TikTok : 3 × 6 = 18 $/mois, donc Upload-Post Basic (24 $, 16 $ en annuel, 5 profils) devient aussi cher ou moins cher.
4. **Un article de PostPeer (concurrent) affirme que « toute API de la liste » retombe en brouillon sans ton propre audit.** C'est une affirmation de concurrent, contredite par les pages de Zernio et d'Upload-Post, mais elle justifie le test d'une vidéo avant de compter dessus.
5. **Confirmation TikTok** : l'API de Zernio exige deux drapeaux légaux à chaque publication (`content_preview_confirmed`, `express_consent_given`). Le programme ne les envoie que si **tu écris toi-même** `"consentement": true` dans le profil (tu as relu les vidéos et acceptes la politique d'usage de la musique de TikTok). Sans cela, rien ne part.

### Recommandation initiale : Upload-Post, forfait Basic

- **Coût mensuel exact : 24 $ par mois, ou 16 $ par mois si tu paies l'année (192 $).** Il n'existe pas de voie gratuite : toutes les offres gratuites trouvées excluent soit TikTok, soit l'API, soit la publication directe publique.
- Pourquoi lui : c'est le seul où la documentation publique confirme les quatre points ensemble : publication directe **publique**, application TikTok du service, **API de dépôt de vidéo + légende** avec suivi, et un prix fixe lisible sans plafond mensuel d'envois.
- 5 profils inclus : un profil par chaîne TikTok (5 chaînes). Au-delà : forfait Professional (50 $/mois ou 33 $ en annuel, 25 profils).
- **Limites** : 15 posts par compte et par 24 h (TikTok) ; vidéo de 3 à 600 s ; quand TikTok plafonne, la vidéo atterrit en brouillon dans la boîte (le service le signale, notre programme le note « boîte, à publier à la main »). Les sons tendance ne sont pas disponibles.
- **Ce que je n'ai pas pu vérifier** : que l'application du service est bien auditée par TikTok (c'est ce qu'il affirme, aucune source indépendante), le nombre exact de comptes TikTok par profil, et le prix courant (voir sa page de prix). **Teste avec un seul compte et une seule vidéo, un mois, avant de t'engager à l'année.**
- **Risque de conditions** : un service tiers n'est acceptable que s'il passe par l'API officielle de TikTok, ce qu'il affirme faire. Aucune astuce ni robot navigateur n'est utilisé de notre côté : nous envoyons seulement la vidéo à l'API du service.
- **Étiquette « généré par IA »** : le champ n'est pas documenté dans l'API du service ; vérifie dans son tableau de bord s'il existe un réglage pour l'étiquette TikTok « contenu généré par IA », sinon ajoute-la à la main sur les premières vidéos.

### Autres outils examinés (offre gratuite + API + TikTok ?)

| Outil | Verdict |
|---|---|
| **Ayrshare** | Pas d'offre gratuite d'après les comparatifs (forfait Premium environ 99 $/mois) : écarté |
| **Post for Me** | « Pas d'offre gratuite » d'après un comparatif de concurrent : non retenu |
| **Outstand, Post Bridge** | Aucune page officielle vérifiée dans mes recherches : **non évalués**, rien n'est affirmé |
| **Publora** | Offre gratuite annoncée à 15 posts/mois (page de listing, non vérifiée), jamais confirmée côté TikTok : non codé |
| **PM3K** | API gratuite annoncée (10 posts/jour, clé valable 7 jours), service inconnu, aucune garantie d'audit : écarté par prudence |

### Brancher le moteur (déjà codé : `planificateur.py`, services `zernio` et `upload-post`)

1. Crée toi-même un compte Upload-Post, choisis le forfait Basic, connecte le compte TikTok de la chaîne dans son tableau de bord (profil nommé comme tu veux, par exemple `quiz`).
2. Crée un fichier `autopilot/secrets/upload_post.json` contenant `{"api_key": "TA_CLE"}` (clé visible dans le tableau de bord ; ne la partage jamais ; le dossier `secrets` est ignoré par git).
Pour **Zernio** : compte sur zernio.com (toi), connecte le TikTok de la chaîne (profil puis lien d'autorisation), repère l'identifiant du compte (`GET /api/v1/accounts`, champ `_id`), crée `autopilot/secrets/zernio.json` avec `{"api_key": "sk_..."}`, puis dans le profil :

```json
"tiktok": {"actif": true, "moteur": "planificateur", "visibilite": "PUBLIC_TO_EVERYONE", "max_par_24h": 3,
           "planificateur": {"service": "zernio", "compte": "ID_DU_COMPTE", "consentement": true}}
```

Pour **Upload-Post** :
3. Dans `autopilot/chaines/<id>.json` :

```json
"tiktok": {"actif": true, "moteur": "planificateur", "planificateur": {"profil": "quiz"}, "max_par_24h": 3}
```

Sans `moteur` (défaut) tout reste comme avant : boîte de réception, aucune publication sans toi. Pour essayer sans risque, mets `"visibilite": "SELF_ONLY"` : la vidéo est publiée en privé et tu la rends publique toi-même après contrôle.
4. `python autopilot/tiktok/envoi.py --dry-run` montre ce qui partirait ; sans `--dry-run`, il envoie. Sans clé, le programme prépare le paquet de secours (vidéo + légende) et sort avec le code 3.

Sources Zernio / PostPeer : <https://zernio.com/pricing>, <https://docs.zernio.com/platforms/tiktok>, <https://docs.zernio.com/guides/media-uploads>, <https://docs.zernio.com/quickstart>, <https://zernio.com/tiktok-api>, <https://www.postpeer.dev/social-media-posting-api/tiktok>, <https://www.postpeer.dev/pricing>, <https://www.postpeer.dev/blog/best-tiktok-posting-api>.

Autres sources consultées pour cette section : <https://docs.upload-post.com/guides/post-to-tiktok-api/>, <https://docs.upload-post.com/resources/pricing-and-limits>, <https://docs.upload-post.com/api/upload-status>, <https://help.blotato.com/platforms/tiktok/faqs>, <https://postiz.com/pricing>, <https://docs.postiz.com/public-api/providers/tiktok.md>, <https://publer.com/docs/posting/create-posts/content-types/platform-specific-formats/tiktok-video-and-multi-photo-posts.md>, <https://help.metricool.com/plans-add-ons-and-api-access-explained-xux1u>, <https://developers.buffer.com/roadmap>, <https://developers.tiktok.com/doc/content-posting-api-get-started>.

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
