# Autopilote « Bureau des Faits » — orchestrateur quotidien

Chaîne qui fabrique et publie des vidéos Business sans intervention. Contrat entre les briques : [CONTRAT.md](CONTRAT.md).
Tout se lance depuis `section3-motion/pixel-faits/` (Python du PATH, bibliothèque standard seulement).

## La chaîne

```
 02:02 tâche Claude `bdf-redaction` (application Claude, pas Windows)
                         rédacteur → _brouillons/ → writer/valider.py   (rien) ──► ecrit | quarantaine
 03:00 BDF-Fabrique      run_daily.py fabriquer           ecrit ──voix──rendu──► controle | quarantaine
                         run_daily.py finaliser           controle ──miniature──► pret | quarantaine
 08:00 BDF-Publication   run_daily.py publier             pret ──► programme ──► publie | quarantaine
 18:00 BDF-Publication   (idem, rattrape le matin)
```

Chaque brique ne fait avancer que l'état qu'elle possède ; l'orchestrateur ne modifie jamais le contenu d'un épisode.
Un épisode douteux va en `quarantaine` (avec une raison) et attend une relecture humaine : il ne bloque jamais les autres.

## Commandes

| Commande | Rôle |
|---|---|
| `python autopilot/run_daily.py etat` | Tableau du stock : épisodes par état, jours de stock (1 vidéo/jour), quarantaines et raisons, disque, jeton YouTube. Options : `--json`, `--taches` (tâches planifiées), `--alertes` (envoie aussi les notifications) |
| `python autopilot/run_daily.py fabriquer` | Prend les épisodes `ecrit` (et `voix`/`rendu` restés à moitié) un par un sous `gpu.lock`, appelle `make_short.py <id>`. Options : `--id`, `--max N`, `--sans-voix`, `--dry-run`, `--attente-gpu S`, `--budget-min M` (180), `--timeout-min M` (90) |
| `python autopilot/run_daily.py finaliser` | `controle` → `pret` : miniature manuelle `miniatures-manuelles/<id>.png` (1280×720, ≤ 2 Mo, prioritaire) sinon `miniature.py <id>` ; sinon l'épisode attend |
| `python autopilot/run_daily.py publier` | Appelle `publish/publish.py --en-attente` s'il y a des épisodes `pret`/`programme` |

Toutes acceptent `--dry-run` (rien n'est écrit ni lancé). Elles sont idempotentes : relancer ne refait que ce qui reste.

### Règles d'exécution

- **Code retour 2 d'une brique** = quarantaine déjà posée par elle (sinon l'orchestrateur la pose, avec la raison de `qa.json`).
- **Échec inattendu** (plantage, délai dépassé) : trace dans `episodes-b/<id>/trace-<brique>.log`, nouvel essai, et à la 2ᵉ défaillance : quarantaine avec la dernière ligne d'erreur. Le compteur est `tentatives` dans `status.json` (remis à 0 au succès).
- **Reprise après plantage** : un verrou dont le processus n'existe plus est repris tout de suite (sinon après 3 h). Les statuts sont écrits de façon atomique.
- **GPU occupé** (`state/gpu.lock`) : on attend `--attente-gpu` secondes (120), puis les épisodes restants sont reportés au prochain passage.
- **Une seule instance** par sous-commande (`state/run_<cmd>.lock`). Pendant un passage, Windows ne se met pas en veille (demande par processus, aucun réglage système modifié).
- Les briques lancées par l'orchestrateur reçoivent `BDF_LOCK_PARENT=1` : l'orchestrateur tient déjà `episodes-b/<id>/.lock`, elles ne doivent pas le reprendre.

## Alertes

Notification Windows (toast PowerShell) + ligne dans `autopilot/state/ALERTES.txt` (toujours écrite ; repli sur `msg`) quand :
stock < 3 jours · rédacteur silencieux (`state/redaction.json`, `dernier_passage` de plus de 36 h) · un épisode entre en quarantaine (une fois par épisode) · `state/youtube_auth.json` n'est pas `{"etat": "ok"}` (jeton YouTube à renouveler) · disque C: < 3 Go libres (le rendu est alors sauté).
Même alerte au plus une fois par 24 h (`state/alertes.json`). `state/stock.json` est remis à jour à chaque exécution.

## Où regarder quand ça ne va pas

1. `python autopilot/run_daily.py etat` — vue d'ensemble et raisons des quarantaines.
2. `autopilot/state/ALERTES.txt` — historique des alertes.
3. `autopilot/logs/run_daily-AAAAMMJJ-<commande>.log` — journal horodaté du jour (20 fichiers conservés au plus).
4. `episodes-b/<id>/status.json` (état, raison) et `trace-*.log` ; `exports-b/<id>/qa.json` (contrôle qualité).
5. Tâches : `schtasks /query /tn BDF-Fabrique /v /fo list` (champ « Dernier résultat » : 0 = ok).

Sortir un épisode de quarantaine : corriger la cause, puis remettre `etat` à `ecrit` (ou `controle`/`pret` selon l'étape à refaire) dans son `status.json`, `raison` à `null`, `tentatives` à 0.
Jeton YouTube : renouveler l'autorisation (voir `publish/`), le publieur réécrit alors `youtube_auth.json` avec `"etat": "ok"`.
Disque : libérer de la place (> 3 Go) ; le lendemain la fabrique reprend toute seule.

## Tâches planifiées (Windows)

```
powershell -ExecutionPolicy Bypass -File autopilot\installer_taches.ps1 [-DryRun]
powershell -ExecutionPolicy Bypass -File autopilot\desinstaller_taches.ps1
```

`BDF-Fabrique` (03:00 : `fabriquer` puis `finaliser`) et `BDF-Publication` (08:00 et 18:00) : réveil de l'ordinateur, rattrapage si une exécution a été manquée, une seule instance, durée maximale (6 h / 1 h), exécution seulement session ouverte (aucun mot de passe stocké), sur secteur ou batterie. Le script n'installe que les tâches dont la commande existe.

**Le rédacteur n'est pas une tâche Windows** : il tourne dans la tâche planifiée de l'application Claude `bdf-redaction` (tous les jours à 02:02), car le `claude` en ligne de commande n'est pas connecté sur cette machine. Pour suspendre ou relancer le rédacteur, utiliser la liste des tâches planifiées de l'application Claude. L'orchestrateur ne l'appelle jamais ; il surveille seulement `state/redaction.json`. Coup d'œil à la main : `python autopilot/writer/stock.py etat`.

Arrêter / relancer à la main :

```
schtasks /end /tn BDF-Fabrique          # arrête un passage en cours
schtasks /change /tn BDF-Fabrique /disable   # suspend (et /enable pour reprendre)
schtasks /run /tn BDF-Publication       # lance maintenant
```

**À vérifier par le propriétaire** (rien de tout cela n'est modifié par les scripts) :
- mise en veille désactivée sur secteur (Paramètres › Système › Alimentation) et minuteries de réveil autorisées ;
- session Windows ouverte — verrouillée, c'est bon ; déconnectée, les tâches attendent la prochaine connexion ;
- C: avec plus de 3 Go libres.

## Tests

```
cd autopilot
python -m unittest -v
```

Dossier temporaire via `BDF_ROOT` (épisodes, exports, état) ; fausses briques ; aucune voix, aucun GPU, aucune vraie notification (`BDF_NOTIF_DESACTIVEE=1`, `BDF_DISQUE_LIBRE_GO` simule le disque, `BDF_PAUSE_S` règle la pause entre deux essais).
