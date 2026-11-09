# Publication YouTube automatique : installation (à faire une seule fois)

Ce guide est pour **toi**, le propriétaire de la chaîne. Il y a quatre étapes et environ 20 minutes de clics.
Le code ne crée aucun compte et ne connaît aucun mot de passe : c'est toi qui te connectes dans ton navigateur,
et Google remet au programme un « jeton » qui permet d'envoyer des vidéos sur ta chaîne, rien d'autre.

> Tout se fait avec le compte Google **propriétaire de la chaîne YouTube** « Bureau des Faits ».
> Si la chaîne est un « compte de marque », choisis-la quand Google te demandera quelle chaîne autoriser (étape 4).

## 1. Créer le projet Google Cloud et activer l'API

1. Va sur <https://console.cloud.google.com/> (connecte-toi avec le compte de la chaîne, accepte les conditions si Google te les propose : c'est à toi de le faire).
2. En haut, clique sur le sélecteur de projet, puis **Nouveau projet**. Nom : `bureau-des-faits`. Clique **Créer** puis sélectionne ce projet.
3. Menu ☰ → **API et services** → **Bibliothèque**. Cherche **YouTube Data API v3**, ouvre-la, clique **Activer**.

## 2. Écran de consentement OAuth (le point qui casse tout si on l'oublie)

1. Menu ☰ → **API et services** → **Écran de consentement OAuth** (selon la version de la console : **Google Auth Platform** → **Branding / Audience**).
2. Type d'utilisateur : **Externe**. Nom de l'application : `Bureau des Faits`. E-mail d'assistance et e-mail du développeur : ton adresse. Enregistre.
3. Ajoute-toi comme **utilisateur test** (ton adresse Gmail) pour pouvoir te connecter la première fois.
4. **Très important : passe l'application de « Test » à « En production »** (bouton **Publier l'application** / *Publish app*, dans *Audience*).
   En mode « Test », Google **expire le jeton au bout de 7 jours** et la publication s'arrêterait toute seule au bout d'une semaine.
   En production, le jeton dure tant que tu ne le révoques pas. Pas besoin de faire valider l'application par Google pour ton usage personnel : tu verras simplement un écran « Google n'a pas validé cette application » à l'étape 4 (clique sur **Paramètres avancés** puis **Accéder à Bureau des Faits (non sécurisé)**, c'est ton propre programme).

## 3. Créer l'identifiant « Application de bureau » et le déposer

1. Menu ☰ → **API et services** → **Identifiants** (ou **Google Auth Platform** → **Clients**) → **Créer des identifiants** → **ID client OAuth**.
2. Type d'application : **Application de bureau**. Nom : `bureau-des-faits-pc`. Clique **Créer**.
3. Clique **Télécharger le fichier JSON**.
4. Renomme ce fichier en **`client_secret.json`** et mets-le ici (le dossier est ignoré par git, ne le partage jamais) :

   ```
   section3-motion/pixel-faits/autopilot/secrets/client_secret.json
   ```

## 4. Se connecter une fois

Dans un terminal, depuis `section3-motion/pixel-faits` :

```bash
python autopilot/publish/auth.py
```

Ton navigateur s'ouvre (sinon copie le lien affiché). Choisis le compte et la chaîne, accepte l'accès YouTube.
La page « Connexion réussie » s'affiche, et le fichier `autopilot/secrets/token.json` est créé.
Vérification (n'affiche aucun secret) :

```bash
python autopilot/publish/auth.py --statut
```

À partir de là, le jeton d'accès se renouvelle tout seul. Si un jour il est révoqué, le workflow écrit
`autopilot/state/youtube_auth.json` (`"etat": "a_refaire"`), **s'arrête de publier sans rien mettre en quarantaine**,
et il suffit de relancer `python autopilot/publish/auth.py`.

## 5. Tester sans rien publier

```bash
python autopilot/publish/publish.py <id-episode> --dry-run
python -m unittest discover -s autopilot/publish/tests
```

`--dry-run` vérifie tout sans internet : fichiers présents, miniature ≤ 2 Mo, titre ≤ 70 caractères, description, tags.

## 6. Demander l'audit pour que les vidéos puissent être publiques

**Ce que tu dois savoir.** L'historique officiel de l'API indique que les vidéos envoyées par un projet API **non audité**
créé après le 28 juillet 2020 sont **verrouillées en « privé »**. Tant que l'audit n'est pas accordé, le workflow envoie bien les vidéos
(elles apparaissent dans YouTube Studio en privé), le note dans `status.json` (`youtube.visibilite = "prive_force"`)
et dans `autopilot/state/youtube_audit.json`, mais **personne d'autre que toi ne peut les voir**.

1. Ouvre le formulaire officiel **YouTube API Services – Audit and Quota Extension Form** :
   <https://support.google.com/youtube/contact/yt_api_form>
2. Remplis-le pour le projet `bureau-des-faits` (numéro de projet visible dans la console Google Cloud). Décris l'usage honnêtement :
   « outil personnel qui envoie les vidéos de ma propre chaîne (un envoi par jour) ». Mentionne que tu es seul utilisateur et que l'outil n'utilise que
   `videos.insert`, `thumbnails.set` et des lectures.
3. L'équipe YouTube API Services te répond par e-mail (Google ne donne pas de délai précis). Réponds à leurs questions éventuelles.
4. Une fois l'audit accordé, lance :

   ```bash
   python autopilot/publish/rendre_public.py --dry-run     # voir ce qui sera fait
   python autopilot/publish/rendre_public.py               # passe en public les vidéos du workflow
   ```

   Par prudence, le script ne touche que les vidéos reliées à un épisode du workflow. L'option `--toutes` inclurait aussi
   tes autres vidéos privées. Chaque passage en public coûte 50 unités de quota.
   Si YouTube renvoie encore « privé », le script le dit : l'audit n'est pas encore pris en compte.

En attendant, tu peux aussi passer les vidéos en public à la main dans YouTube Studio.

## Réglages (`autopilot/publish/config.json`)

| Clé | Rôle | Valeur actuelle |
|---|---|---|
| `heures_shorts` | créneaux de mise en ligne des Shorts (heure locale) | `08:00`, `12:00`, `18:00`, `21:00` |
| `shorts_par_creneau` | Shorts par créneau (4 x 2 = **8 Shorts par jour**) | `2` |
| `ecart_creneau_minutes` | écart entre deux Shorts du même créneau (08:00 et 08:15) | `15` |
| `heure_long` | heure de mise en ligne d'un long | `17:00` |
| `jours_longs` | jours des longs (0 = lundi) : lundi, mercredi, vendredi | `[0, 2, 4]` |
| `heure_publication` | repli : heure unique si `heures_shorts` est vide | `18:00` |
| `fuseau` | fuseau de ces heures (`Europe/Paris`, `America/Los_Angeles`, `UTC`) | `Europe/Paris` |
| `categorie_id` | catégorie YouTube (27 = Éducation, 25 = Actualités, 26 = Conseils et style) | `27` |
| `max_envois_par_execution` | nombre de vidéos envoyées par lancement (2 lancements par jour) | `10` |
| `hashtags_cible` / `hashtags_max` | hashtags visés dans chaque description / maximum (au-delà de 15, YouTube les ignore tous) | `12` / `15` |
| `hashtags_chaine` | hashtags de la chaîne, utilisés pour compléter une description trop pauvre | voir `reglages.py` |
| `mots_cles_dans_description` | ajoute « Mots-clés : … » (tags du rédacteur) s'il manque | `true` |

**Planification** : un créneau = une heure précise, pas un jour. Chaque vidéo prend le premier créneau libre de son format (Shorts : tous les jours ; longs : les `jours_longs`), à plus de `marge_minimale_minutes` de maintenant. Les Shorts découpés dans un long passent d'abord, en alternant les longs d'origine ; la file n'enchaîne jamais deux titres de même forme ni deux gabarits visuels identiques (`publish.diversifier`).
**Quota** : 8 Shorts + 1 long par jour = au plus 9 envois (plafond 100 par jour) et 9 miniatures + 9 relectures = 459 unités sur 10 000. Le garde-fou de quota est inchangé : au premier refus de YouTube, tout est reporté au lendemain.
| `quota.*` | coûts et plafonds de quota (voir ci-dessous) | valeurs officielles |

Les vidéos sont envoyées en **privé** avec une date de mise en ligne programmée (`publishAt`) : YouTube les rend publiques à l'heure dite.
Chaque vidéo déclare « non conçue pour les enfants » et, selon `contenu_ia` dans `publication.json`, un contenu modifié ou synthétique.

## Quota : ce que dit la documentation officielle (vérifié le 2 novembre 2026)

- 10 000 unités par jour, remise à zéro à **minuit heure du Pacifique** (soit 9 h du matin à Paris, sauf une ou deux semaines par an où les changements d'heure ne coïncident pas).
- `thumbnails.set` : 50 unités ; `videos.list`, `channels.list`, `playlistItems.list` : 1 unité ; `videos.update` : 50 unités.
- **`videos.insert` a changé** : l'historique officiel indique ~1 600 unités jusqu'en 2025, ~100 unités depuis le 4 décembre 2025, puis, depuis le 1ᵉʳ juin 2026,
  **un compteur à part de 100 envois par jour, à 1 unité l'envoi**. Le programme applique ce dernier régime (`quota.cout_envoi_compteur = 1`, `quota.plafond_envois = 100`).
  Si Google revenait à un coût en unités, il suffirait de mettre par exemple `"cout_envoi_unites": 1600` dans la section `quota` de `config.json`.
- Un envoi + sa miniature + la relecture coûtent donc 51 unités et 1 envoi. Le registre est `autopilot/state/youtube_quota.json` ; si le plafond serait dépassé
  (ou si YouTube répond « quota dépassé »), l'épisode reste `pret` et repart le lendemain, sans quarantaine.

## En cas de souci

| Symptôme | Cause probable | Que faire |
|---|---|---|
| `autopilot/state/youtube_auth.json` indique `a_refaire` | jeton révoqué, ou application restée en mode « Test » > 7 jours | refaire l'étape 2.4 si besoin, puis `python autopilot/publish/auth.py` |
| Épisode en `programme` avec `visibilite = prive_force` | projet non audité | étape 6 |
| Épisode en quarantaine « YouTube refuse la vidéo » | titre/description/tags refusés | lire `status.json` → `raison`, corriger `publication.json`, remettre l'état à `pret` |
| `miniature = false` dans `status.json` | chaîne non autorisée à utiliser des miniatures personnalisées | vérifier la chaîne par téléphone dans YouTube Studio ; la vidéo est quand même en ligne |
| Envoi interrompu | coupure réseau | rien : la session d'envoi est mémorisée dans `episodes-b/<id>/youtube_upload.json` et reprise au prochain lancement |
