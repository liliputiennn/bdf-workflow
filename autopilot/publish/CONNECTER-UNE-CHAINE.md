# Connecter une nouvelle chaîne YouTube

Tu as déjà un projet Google (`bureau-des-faits`) et le fichier `autopilot/secrets/client_secret.json` : ils servent pour **toutes** les chaînes.
Pour chaque nouvelle chaîne, il ne reste que trois choses : la créer, l'autoriser, l'activer. Rien de ce qui suit ne crée de compte ni ne demande de mot de passe à l'outil : Google te le demande lui-même, dans ton navigateur.

## 1. Créer la chaîne (à la main)

1. Dans YouTube, ouvre le menu de ton compte → **Changer de compte** → **Créer une chaîne** (une chaîne de « compte de marque » : elle a son propre nom et peut être gérée par le même compte Google).
2. Donne-lui son nom. Le nom provisoire du profil est dans `autopilot/chaines/<id>.json` (champ `nom`) : ajuste-le si tu veux.
3. **Vérifie la chaîne par téléphone** (YouTube Studio → Paramètres → Chaîne → Fonctionnalités) : sans cela, les miniatures personnalisées sont refusées et les vidéos de plus de 15 minutes aussi.

## 2. Connecter la chaîne

Dans un terminal, depuis `section3-motion/pixel-faits` (remplace `en` par l'identifiant du profil : `en`, `histoire`, `sommeil`, `langues`, `quiz`, `musique-enfants`) :

```bash
python autopilot/publish/connecter_chaine.py en
```

- Ton navigateur s'ouvre sur la page d'autorisation de Google. **Choisis le compte, puis la CHAÎNE que tu viens de créer** (pas la chaîne française), puis clique « Autoriser ». C'est l'étape où l'on se trompe le plus souvent.
- L'outil enregistre le jeton dans `autopilot/secrets/token-<id>.json` (dossier ignoré par git, jamais affiché), demande à YouTube le nom de la chaîne et te le montre : vérifie que c'est la bonne.
- Si la chaîne choisie est **déjà reliée à un autre profil**, l'outil refuse et supprime le jeton : recommence en choisissant la bonne chaîne.

Autres commandes utiles :

```bash
python autopilot/publish/connecter_chaine.py --liste          # chaînes et jetons (oui / non), sans rien de secret
python autopilot/publish/connecter_chaine.py en --verifier    # revérifier un jeton existant
python autopilot/publish/connecter_chaine.py en --refaire     # refaire la connexion (jeton expiré ou refusé)
```

## 3. Activer la chaîne (quand tu es prêt)

La connexion **n'active pas** la chaîne. Elle ne publie rien tant que, dans `autopilot/chaines/<id>.json`, tu n'as pas mis :

```json
"active": true
```

Avant de le faire, vérifie sur l'écran **Chaînes** de la web app que :

- le jeton est « connecté » ;
- il y a des épisodes prêts (le chantier du format ou de la traduction les fournit) ;
- pour une chaîne dans une autre langue que le français, `voix.dossier` pointe vers une voix de cette langue (sinon le profil est refusé : la chaîne parlerait français).

Le quota d'envoi (100 par jour) est partagé par toutes les chaînes : rien à configurer.

## Si quelque chose ne va pas

| Message | Que faire |
|---|---|
| « client_secret.json absent » | Le fichier du projet Google manque dans `autopilot/secrets/` (voir `INSTALLATION.md`). |
| « déjà liée au profil … » | Tu as validé la mauvaise chaîne dans la liste de Google : relance l'outil. |
| « jeton refusé » (plus tard, dans les alertes) | Le jeton a été révoqué ou a expiré : `connecter_chaine.py <id> --refaire`. Les autres chaînes continuent de publier. |
| Écran Chaînes : « jeton non connecté » | Il n'y a pas de fichier de jeton pour cette chaîne : refais l'étape 2. |

## Pour la publication dans le cloud

Le workflow GitHub `publication.yml` ne lit aujourd'hui qu'un seul secret de jeton (`YT_TOKEN`, la chaîne française). Pour publier une autre chaîne depuis le cloud, il faudra ajouter un secret par chaîne (par exemple `YT_TOKEN_EN`) et l'écrire dans `autopilot/secrets/token-en.json` à l'étape qui recopie déjà `YT_TOKEN`. Tant que ce n'est pas fait, une chaîne connectée sur ce PC ne publie que depuis ce PC.
