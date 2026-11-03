# Autopilote dans le cloud — architecture proposée (gratuite, PC éteint)

Choix de l'utilisateur (03/11/2026) : 100 % gratuit · dépôt GitHub **privé** · rédaction en **lot hebdomadaire** via l'abonnement Claude · tous les comptes gratuits acceptés, aucune API payante.
Comparatif chiffré et sources : notes de session `comparatif-hebergement-cloud.md`.

## Schéma

```
 [1× / semaine, ton abonnement Claude]  rédige 7 épisodes ──► git push (episodes-b/_brouillons)
                                                                   │
 GitHub Actions (privé, cron 02:30 UTC)  « fabrique »              ▼
   1. valider.py : brouillons → `ecrit`                      dépôt GitHub
   2. envoie texte + ref voix vers Kaggle  ──►  Kaggle Notebook GPU (T4/P100) : voice.py
   3. attend / relève le statut (kaggle kernels status)   ◄── voice.wav + timings.json
   4. rendu Remotion CPU (Short ou long 16:9 + découpe en Shorts), QA, miniature
   5. dépose les mp4 / miniatures sur Cloudflare R2 (10 Go gratuits), purge après publication
 GitHub Actions (cron 08:00 et 18:00 locale)  « publication »
   6. publish.py (YouTube, jeton en secret) ; tiktok/envoi.py (boîte de réception)
 À chaque étape : `npm run snapshot` → déploiement Firebase Hosting → la web app se met à jour
```

Le code existant (`run_daily.py`, `make_short.py`, `publish/`…) ne change presque pas : il tourne dans Actions au lieu de Windows. Seule `voice.py` a un jumeau Kaggle (`voix_kaggle.py`, à écrire en phase 2).

## Briques et pourquoi

| Brique | Choix | Pourquoi / limite connue |
|---|---|---|
| Orchestrateur, file | GitHub Actions privé, état = fichiers JSON dans le dépôt (`status.json`, `stock.json`) | quota Free 12 $/mois ≈ 2000 min Linux 2 cœurs. **Risque n°1 : durée du rendu CPU d'un long** (inconnue sur 2 cœurs) |
| Voix | Kaggle GPU (~30 h/sem. ou plus, 9-12 h/session) | notre besoin : ~1 h par long (mesuré localement sur RTX 3050) ≈ 7 h/sem. Pas de planificateur natif → déclenché par l'Action. CGU : automatisation non explicitement permise ni interdite |
| Secours GPU | Modal (30 $/mois offerts ≈ 50 h de T4) | si Kaggle refuse ; compte à créer plus tard seulement si besoin |
| Vidéos | Cloudflare R2 (10 Go gratuits, sortie gratuite) | Firebase Spark n'a ni Cloud Storage ni Functions ; les artefacts GitHub Free sont limités à 500 Mo |
| Web app | Console existante (React/Vite) + onglet **Autopilote** ; Firebase Hosting (Spark, déjà là) | lit `live/snapshot.json` (déployé à chaque étape). Phase 2 : Realtime Database (100 connexions, 1 Go) pour du vrai temps réel |
| Rédaction | session Claude hebdomadaire → `git push` | 0 € ; en option, routine Claude planifiée en cloud (PC éteint, consomme l'abonnement, limites non vérifiées) |

## Risques à lever en phase 1 (avant de tout migrer)
1. **Durée du rendu Remotion sur un runner 2 cœurs** : mesurer un Short et un long. Si > ~45 min par long, repli : rendre sur Kaggle (CPU 4 cœurs, gratuit, hors quota GPU ⚠️ non vérifié) ou rendre le dépôt public (minutes illimitées, code lisible).
2. **Jeton YouTube** : projet OAuth en mode « Test » ⇒ le jeton de rafraîchissement expire en 7 jours (règle Google, ⚠️ de mémoire). Il faut passer l'écran de consentement en « En production » (application non vérifiée, un seul utilisateur) pour qu'il tienne.
3. **Kaggle** : quota réel affiché dans le compte, délai de mise en file, accès internet (installation des paquets) à confirmer sur un premier essai.
4. **Confidentialité** : le snapshot contient titres, raisons de quarantaine, alertes (aucun secret). Il est servi sur une adresse publique → `noindex` ; protection par connexion Google en phase 2.

## Phases
- **P0 (fait)** : onglet Autopilote en local, données réelles, relancer/écarter, `npm run snapshot`.
- **P1** : dépôt privé + workflow `fabrique` en `--dry-run` + mesure des durées.
- **P2** : `voix_kaggle.py`, jeux de données privés (modèles, voix de référence), un épisode de bout en bout.
- **P3** : R2, publication depuis Actions, snapshot déployé à chaque étape.
- **P4** : on éteint les tâches Windows (`desinstaller_taches.ps1`).

## À faire et payer par l'utilisateur (aucun paiement attendu)
| # | Quoi | Où | Coût |
|---|---|---|---|
| 1 | Compte GitHub (si absent) + créer un dépôt **privé** `bureau-des-faits` | github.com | 0 € |
| 2 | Compte Kaggle, **vérification du téléphone**, puis générer un jeton API (Settings → API) | kaggle.com | 0 € |
| 3 | Compte Cloudflare, activer R2, créer un bucket + clé d'accès | dash.cloudflare.com | 0 € sous 10 Go (carte bancaire souvent demandée) |
| 4 | Jeton de déploiement Firebase (`firebase login:ci` ou compte de service) | ton terminal | 0 € |
| 5 | Écran de consentement YouTube → « En production » ; garder `client_secret.json` et `token.json` pour les mettre en secrets | console.cloud.google.com | 0 € |
| 6 | Saisir les secrets dans GitHub → Settings → Secrets (je ne les vois jamais) : `KAGGLE_API_TOKEN`, `R2_*`, `FIREBASE_TOKEN`, `YT_CLIENT_SECRET`, `YT_TOKEN`, `TIKTOK_*` | github.com | 0 € |
| 7 | Une fois : téléverser les modèles (`C:\VoiceStudio\qwen3-tts-0.6b-*`, `whisper-small`) et `voix/ref.wav` comme **Datasets Kaggle privés** | kaggle.com | 0 € |
| 8 | Pousser le code (`git push`) quand je te le demande | ton PC | 0 € |

## Lancer le prototype toi-même
```powershell
cd "C:\Users\ESSAI\motion design + davinci\section3-motion\pixel-faits"
npm run console          # http://127.0.0.1:5180 → onglet « Autopilote » (direct, boutons actifs)
npm run snapshot         # écrit dist-console/live/snapshot.json (version cloud)
```
Mise en ligne d'un instantané lecture seule (à lancer par toi, le classifieur a refusé `npm run deploy`) :
```powershell
$env:VITE_SNAPSHOT_URL = "/live/snapshot.json"
npm run build:web        # vide dist-console, donc le snapshot vient APRÈS
npm run snapshot
firebase deploy --only hosting --project bureau-des-faits
Remove-Item Env:VITE_SNAPSHOT_URL
```
Les miniatures/vidéos ne sont pas incluses en ligne tant que R2 n'existe pas (`VITE_MEDIA_BASE`).

## Phase 1 — état (mesure du rendu, sans publier)
Préparé : `exporter_depot.ps1` (dépôt local propre `C:\Users\ESSAI\bdf-cloud`, 310 fichiers, contrôle anti-secrets, rien d'envoyé) et `github/workflows/mesure.yml` (rend un Short sur un runner et affiche cœurs, durée, estimation d'un long et coût mensuel).
À faire par toi : `cd C:\Users\ESSAI\bdf-cloud` → `gh auth login` → `gh repo create bureau-des-faits --private --source . --push` → sur github.com : Actions → Mesure → Run workflow → copier le « Summary ».
Constats pour la suite (phases 2-3) : l'état du workflow (`autopilot/state/`, `status.json` selon `.gitignore`) n'est pas dans Git ⇒ prévoir une branche `etat` ou le cache Actions ; la voix de référence (`autopilot/voix/ref.wav`) reste hors dépôt ⇒ dataset Kaggle privé ; musique et SFX sont retéléchargés par `tools/fetch-audio.sh` à chaque run (Pixabay, non redistribuable).
Référence locale : un Short rend en ≈ 80 s avec 4 cœurs ; un runner gratuit en a 2 (non vérifié), d'où la mesure.

### Résultat de la mesure (03/11/2026, run Actions n° 41657125679, dépôt privé liliputiennn/bureau-des-faits)
- Runner gratuit : **2 cœurs** (confirmé ; `--concurrency=4` plantait → `BDF_CONCURRENCY` ajouté à `make_short.py`).
- Installation (apt, npm ci, Chrome, audio) : **80 s**. Rendu d'un Short de 995 images (≈ 33 s) : **238 s** (≈ 4 images/s), contre ≈ 80 s sur le PC.
- Estimation d'un long de 9 min (≈ 16 200 images en 16:9, **à mesurer**) : ≈ 65 min, + 10 Shorts × 4 min = ≈ 40 min ⇒ **≈ 1 h 45 par long**.
- Quota privé gratuit ≈ 2000 min/mois ⇒ ≈ **19 longs/mois au maximum** (1 long tous les 1,5 jour), moins si on ajoute des Shorts seuls (≈ 6 min chacun).
- Pistes : (a) dépôt **public** (minutes illimitées, code et scripts lisibles) ; (b) rendu sur Modal (≈ 0,2-0,3 $ par long sur les 30 $ offerts, partagés avec la voix ≈ 18 $/mois) ; (c) rendu sur Kaggle CPU (4 cœurs, ⚠️ non vérifié).

## Phase 2 — voix sur Kaggle (code prêt, à tester)
Fichiers : `kaggle/lancer_voix.py` (remplace `voice.py` : pousse un kernel, attend, récupère voice.wav + timings.json), `kaggle/kernel_template.py` (script exécuté sur Kaggle ; embarque voice.py et le texte), `kaggle/preparer_datasets.ps1` (envoi unique des modèles : Qwen3-TTS 2,3 Go, Whisper 0,45 Go, voix de référence, en jeux privés). `voice.py` accepte maintenant des variables `BDF_*` pour changer les chemins.
À faire par toi, dans l'ordre : (1) compte Kaggle + téléphone vérifié ; (2) jeton API (Settings > API) ; (3) `pip install kaggle` ; (4) définir `$env:KAGGLE_USERNAME` et `$env:KAGGLE_API_TOKEN` ; (5) `powershell -File autopilot/cloud/kaggle/preparer_datasets.ps1` ; (6) test : `python autopilot/cloud/kaggle/lancer_voix.py episodes-b/appli-gratuite-argent`.
Points à confirmer au premier essai : accélérateur choisi par Kaggle (P100 ou T4) et `bfloat16` accepté (sinon `BDF_DTYPE=float16`), `ffmpeg` présent, accès internet du kernel.
