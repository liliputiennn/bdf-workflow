# Secrets GitHub : un jeton YouTube par chaîne

Le workflow **Publication** écrit, à chaque passage, les jetons dans `autopilot/secrets/` (supprimé en fin de passage), à partir des secrets du dépôt.
Rien n'est créé ni activé par le code : tu crées les secrets toi-même (GitHub → dépôt → Settings → Secrets and variables → Actions → *New repository secret*).

## Noms à créer

| Chaîne (profil) | Nom du secret | Fichier reconstitué |
|---|---|---|
| fr (Bureau des Faits) | `YT_TOKEN` (déjà là) | `token.json` |
| en | `YT_TOKEN_EN` | `token-en.json` |
| histoire | `YT_TOKEN_HISTOIRE` | `token-histoire.json` |
| sommeil | `YT_TOKEN_SOMMEIL` | `token-sommeil.json` |
| langues | `YT_TOKEN_LANGUES` | `token-langues.json` |
| quiz | `YT_TOKEN_QUIZ` | `token-quiz.json` |
| musique-enfants | `YT_TOKEN_MUSIQUE_ENFANTS` | `token-musique-enfants.json` |
| meditation | `YT_TOKEN_MEDITATION` | `token-meditation.json` |
| histoires-enfants | `YT_TOKEN_HISTOIRES_ENFANTS` | `token-histoires-enfants.json` |
| finance-perso | `YT_TOKEN_FINANCE_PERSO` | `token-finance-perso.json` |
| asmr | `YT_TOKEN_ASMR` | `token-asmr.json` |

Règle : `YT_TOKEN_` + identifiant du profil en majuscules, le « - » devenant « _ ». Le fichier est le `jeton_fichier` du profil (`autopilot/chaines/<id>.json`).
Le secret `YT_CLIENT_SECRET` (le même client OAuth pour toutes les chaînes) existe déjà et ne change pas.

## Valeur de chaque secret

Le **contenu complet** du fichier `autopilot/secrets/token-<id>.json` de ton PC, créé par `python autopilot/publish/connecter_chaine.py <id>` (voir `autopilot/publish/CONNECTER-UNE-CHAINE.md`) :
ouvre-le dans un éditeur, copie tout, colle dans le secret. Ne le mets nulle part ailleurs (pas de chat, pas de fichier du dépôt).
Il doit être un JSON avec un `refresh_token` ; sinon le workflow l'ignore (avertissement sans afficher la valeur).

## Comportement

- Un secret absent = la chaîne est ignorée à la publication (aucune erreur). Une chaîne n'est de toute façon publiée que si son profil a `"active": true`.
- `python autopilot/cloud/jetons_chaines.py --liste` (en local) montre, chaîne par chaîne, le nom du secret attendu et si la variable est présente ; il n'affiche jamais de valeur.
- Nouveau profil de chaîne : ajouter UNE ligne `YT_TOKEN_<ID>: ${{ secrets.YT_TOKEN_<ID> }}` dans l'étape « Identifiants » de `publication.yml` (GitHub n'a pas de joker pour les secrets). Un test (`test_cloud_formats.py`) échoue tant que la ligne manque.
- Le jeton d'accès se rafraîchit à chaque passage depuis le `refresh_token` ; si Google le révoque (code de sortie 3, « Connexion YouTube à refaire »), refaire `connecter_chaine.py <id> --refaire` puis remplacer le secret.
- Après changement des workflows, relancer `sync_depot.ps1` (toi) pour les envoyer au dépôt cloud ; les fichiers de profil et de formats (`autopilot/chaines/`, `autopilot/formats/`) doivent être suivis par Git pour être synchronisés.

## TikTok en public : le secret `ZERNIO_API_KEY`

La chaîne `fr` publie ses Shorts sur TikTok **en public** par Zernio (compte @la.debrouilleofficiel ; `tiktok.moteur: "planificateur"` dans `autopilot/chaines/fr.json`, `consentement` accordé par toi). Le workflow **Publication** a besoin d'un seul secret, que tu crées toi-même :

| Nom du secret | Valeur | Fichier reconstitué (supprimé en fin de passage) |
|---|---|---|
| `ZERNIO_API_KEY` | la clé d'API Zernio, **seule** (pas de JSON) — la même que dans `autopilot/secrets/zernio.json` sur ton PC, champ `api_key` | `autopilot/secrets/zernio.json` |

GitHub → dépôt `liliputiennn/bdf-workflow` → Settings → Secrets and variables → Actions → *New repository secret*.
Sans ce secret, l'étape « Envoi TikTok » est sautée (le journal dit « clé Zernio ABSENTE ») : rien n'est envoyé, rien ne casse.
`TIKTOK_CLIENT` / `TIKTOK_TOKEN` ne servent plus que pour une chaîne en mode « boîte de réception ».

**Vidéos déjà gérées à la main** : `autopilot/tiktok/exclus.json` (suivi par Git) liste les vidéos à ne jamais renvoyer (les « 10-business-…-s2 / s3 / s4 / s10 »). À chaque passage, `etat_cloud.py restore` les fusionne dans l'état TikTok restauré ; elles sont donc ignorées même si l'état du cloud ne les connaît pas. Pour exclure une autre vidéo, ajoute-la dans ce fichier.
Les Shorts s2 et s3 sont déjà programmés chez Zernio pour le 11/11 (12:00 et 18:00, Paris).
