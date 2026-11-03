# Envoi automatique vers TikTok : installation (à faire une seule fois)

Ce que fait le workflow : après chaque Short prêt, il l'envoie **dans la boîte de réception de ton compte TikTok**. TikTok t'envoie une notification ; tu ouvres l'application, tu colles la légende et tu touches **Publier** (environ 30 secondes par vidéo). Rien n'est publié sans toi.

## Pourquoi pas une publication 100 % automatique

D'après la documentation de TikTok (vérifiée le 2026-11-03) : la publication directe (`video.publish`) exige que ton application soit **approuvée puis auditée** ; tant qu'elle ne l'est pas, tout ce qui est publié par l'API reste **privé**. L'envoi dans la boîte de réception (`video.upload`) n'a pas cette limite de visibilité, parce que c'est toi qui publies. Les outils tiers déjà audités sont payants. Si un jour tu veux le 100 % automatique, il faudra demander l'audit à TikTok depuis le portail développeur.

Limite à connaître : **5 envois en attente au plus par 24 heures**. Le workflow en envoie 4 au plus.

## État au 2026-11-03 (déjà fait dans ton Chrome)

Application **Bureau des Faits** créée (propriétaire : individuel) sur developers.tiktok.com, avec un **bac à sable** `bdf-sandbox` : pas de revue TikTok nécessaire pour un usage personnel. Produits Login Kit et Content Posting API ajoutés, portées `user.info.basic` et `video.upload` actives, plateforme Desktop avec la redirection `http://127.0.0.1:*/callback/`, icône et description en place. Le **Client key** du bac à sable est dans `autopilot/secrets/tiktok_client.json`.

Il reste, dans cet ordre :
1. **Déployer le site** (les pages de confidentialité et de conditions sont écrites dans `app/static/` et déjà indiquées à TikTok) : `npm run deploy` dans `section3-motion/pixel-faits`.
2. **Ajouter ton compte TikTok comme utilisateur cible** : portail TikTok, bac à sable, « Sandbox settings » puis « Target Users » puis « Add account », et connecte-toi à TikTok dans la fenêtre qui s'ouvre.
3. **Client secret** : dans la page de l'application (bac à sable), clique l'œil à côté de « Client secret », copie-le et colle-le dans `autopilot/secrets/tiktok_client.json` à la place de `""`.
4. `python autopilot/tiktok/auth.py`, puis `python autopilot/tiktok/auth.py --statut`.

Les étapes ci-dessous décrivent la méthode générale ; avec le bac à sable, les étapes 2, 3 et 6 du guide sont déjà faites.

## Ce que tu dois faire (je ne peux pas le faire à ta place : compte, conditions et connexion sont à toi)

1. Va sur <https://developers.tiktok.com/>, connecte-toi avec le compte TikTok de la chaîne et crée un compte développeur si on te le demande.
2. **Manage apps → Connect an app** (ou « Create app »). Nom : `Bureau des Faits`. Description : « Envoie mes vidéos dans ma boîte de réception TikTok pour les publier moi-même. » Catégorie : au choix.
3. Dans l'application, ajoute les produits **Login Kit** et **Content Posting API**.
4. Dans **Login Kit**, enregistre cette adresse de redirection (le port `*` signifie « n'importe lequel ») :
   `http://127.0.0.1:*/callback/`
5. Dans **Content Posting API**, demande la portée **`video.upload`** (pas `video.publish`).
6. TikTok peut demander une vidéo de démonstration ou une revue de l'application avant d'activer ces produits : c'est leur règle, pas celle du workflow. Soumets l'application et attends l'accord.
7. Dans la page de l'application, copie le **Client key** et le **Client secret**. Crée le fichier suivant (le dossier est ignoré par git, ne le partage jamais) :

   `section3-motion/pixel-faits/autopilot/secrets/tiktok_client.json`

   ```json
   { "client_key": "COLLE_ICI_LE_CLIENT_KEY", "client_secret": "COLLE_ICI_LE_CLIENT_SECRET" }
   ```
8. Si ton application est encore en mode « sandbox », ajoute ton compte TikTok comme **utilisateur cible** (Target users) dans le portail.
9. Connexion, une seule fois, dans un terminal depuis `section3-motion/pixel-faits` :

   ```bash
   python autopilot/tiktok/auth.py
   ```

   Ton navigateur s'ouvre ; autorise l'accès (« envoyer des vidéos dans ta boîte de réception »). Vérification, sans rien afficher de secret :

   ```bash
   python autopilot/tiktok/auth.py --statut
   ```

   Le jeton d'accès (2 h) se renouvelle tout seul. Le jeton de renouvellement vit **180 jours** : il change à chaque renouvellement, donc tant que le workflow tourne il reste valide. Si le workflow reste éteint plus de 180 jours, relance `auth.py`.

## Utilisation

```bash
python autopilot/tiktok/envoi.py --dry-run     # montre ce qui partirait, sans rien envoyer
python autopilot/tiktok/envoi.py               # envoie (4 au plus par 24 h) et met à jour les statuts
python autopilot/tiktok/envoi.py --paquet      # prépare seulement exports-tiktok/<id>/ (vidéo + légende) à déposer à la main
python autopilot/run_daily.py tiktok           # idem, avec une notification Windows quand des vidéos t'attendent
```

Un Short est éligible quand il est prêt (état `pret`, `programme` ou `publie`), qu'il n'est pas un long et que son rapport qualité dit « publiable ». La légende (titre + hashtags) est écrite dans `autopilot/state/tiktok.json` et dans `exports-tiktok/<id>/legende.txt`.

**Sans jeton** (avant l'installation, ou connexion à refaire), le programme prépare quand même les paquets dans `exports-tiktok/` et sort avec le code 3 : tu peux déposer les vidéos à la main en attendant.

## Dans l'application TikTok

- Touche la notification (ou la boîte de réception) pour ouvrir le brouillon.
- Colle la légende (`legende.txt`) et coche **« Contenu généré par IA »** : la voix est une voix de synthèse.
- Touche **Publier**.
- Un envoi non publié est supprimé par TikTok au bout de 24 heures (source tierce : à confirmer).

## Planifier l'envoi (avec ton accord)

Pas encore installé : une tâche Windows `BDF-TikTok` (par exemple à 08:30 et 18:30, `python autopilot/run_daily.py tiktok`). Dis-moi quand tu veux que je l'ajoute avec `installer_taches.ps1`.
