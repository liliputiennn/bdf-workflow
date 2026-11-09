# Connecter TikTok à tes chaînes (pas à pas)

Résultat : chaque chaîne que tu choisis envoie ses Shorts dans la boîte de réception de **son** compte TikTok. Tu reçois une notification, tu touches **Publier**. Lis d'abord `OPTIONS-PUBLICATION.md` si tu veux savoir pourquoi ce n'est pas 100 % automatique (TikTok l'interdit aux applications non auditées).

Rien n'est publié, aucun compte n'est créé et aucun mot de passe n'est demandé par le programme. Les clés restent dans `autopilot/secrets/` (ignoré par git, ne le partage jamais).

## Étape 1 : un compte TikTok par chaîne (toi)

Crée toi-même un compte TikTok pour chaque chaîne qui doit envoyer sur TikTok (par exemple `quiz`). Une seule vérification : le nom, la photo et la description montrent clairement la chaîne.

## Étape 2 : l'application développeur (une seule pour toutes les chaînes)

Si tu as déjà suivi `INSTALLATION.md` (application **Bureau des Faits**, bac à sable), garde-la : elle sert pour toutes les chaînes. Sinon, fais les étapes 1 à 7 de `INSTALLATION.md` (portée **`video.upload`**).

Dans le portail TikTok, bac à sable, **Target Users** : ajoute **chaque compte TikTok** de tes chaînes (un par un). Vérifie dans le portail le nombre de comptes de test autorisé ; s'il est trop bas pour tes chaînes, connecte seulement les chaînes les plus utiles.

## Étape 3 : connecter chaque compte (une fois, puis tous les 6 mois)

Dans un terminal, depuis `section3-motion/pixel-faits` :

```bash
python autopilot/tiktok/auth.py --chaine fr
```

```bash
python autopilot/tiktok/auth.py --chaine quiz
```

Chaque commande ouvre ton navigateur. **Connecte-toi au compte TikTok de cette chaîne** (pas un autre) et autorise l'accès. Si le navigateur est déjà connecté au mauvais compte, déconnecte-le dans TikTok avant.

Le jeton est enregistré dans `autopilot/secrets/` : `tiktok_token.json` pour la chaîne `fr`, `tiktok_token-quiz.json` pour `quiz`, etc. Pour vérifier (rien de secret n'est affiché) :

```bash
python autopilot/tiktok/auth.py --chaine quiz --statut
```

Le jeton se renouvelle seul ; il expire au bout de 180 jours sans usage. Le programme te prévient quand une chaîne est à reconnecter.

## Étape 4 : dire quelles chaînes envoient (le champ `tiktok` du profil)

Ouvre le profil de la chaîne, `autopilot/chaines/<id>.json`, et règle le champ `tiktok` :

| Ce que tu veux | Valeur |
|---|---|
| Chaîne par défaut seulement (comportement d'avant) | ne rien écrire |
| Cette chaîne envoie sur TikTok | `"tiktok": true` |
| Cette chaîne n'envoie pas | `"tiktok": false` |
| Réglages fins | `"tiktok": { "actif": true, "hashtags": ["#quiz", "#culture"], "max_par_24h": 3 }` |

Réglages possibles dans l'objet : `actif`, `hashtags` (ajoutés à la légende), `max_par_24h` (au plus 5 en boîte de réception), `jeton_fichier` (nom du fichier de jeton), `ia` (étiquette « contenu IA », vrai par défaut). Le validateur de profils refuse les valeurs invalides.

Les Shorts des nouveaux formats (quiz, langues, sommeil, musique, histoire) partent comme les autres dès que leur profil dit `"tiktok": true`, qu'ils sont prêts et que leur rapport qualité dit « publiable ».

À tester sans rien envoyer :

```bash
python autopilot/tiktok/envoi.py --dry-run
```

En marche normale, la commande du jour s'en charge : `python autopilot/run_daily.py tiktok`.

## Étape 5 (facultative et incertaine) : demander l'audit pour la publication directe

À ne faire que si tu veux tenter le 100 % automatique, en sachant que TikTok écrit qu'il refuse les outils destinés aux comptes de leur propriétaire (voir `OPTIONS-PUBLICATION.md`) :

1. Portail développeur, ton application, page **Content Posting API** : demande la portée `video.publish` et remplis le formulaire d'audit. Décris honnêtement l'usage.
2. Attends la réponse de TikTok. Rien ne change dans le programme avant.
3. **Seulement si TikTok accepte**, écris dans le profil de la chaîne :
   `"tiktok": { "actif": true, "mode": "direct", "audit_confirme": true }`
   puis reconnecte le compte avec la portée de publication :

```bash
python autopilot/tiktok/auth.py --chaine quiz --direct
```

Sans `"audit_confirme": true`, le mode `direct` est ignoré et on reste sur la boîte de réception. Si le compte ne propose que « privé », la vidéo est publiée en privé et rien d'autre n'est tenté.

## Si ça ne marche pas

- Code retour 3 / « à reconnecter » : relance l'étape 3 pour la chaîne citée. En attendant, un **paquet de secours** (vidéo + légende) est prêt dans `exports-tiktok/<épisode>/` : dépose-le à la main dans TikTok et coche « Contenu généré par IA ».
- « 403 spam_risk_too_many_pending_share » : trop de vidéos en attente dans la boîte de réception ; publie ou supprime les brouillons dans TikTok.
- Un autre compte reçoit les vidéos : tu t'es connecté au mauvais compte à l'étape 3 ; refais-la en te déconnectant d'abord.
