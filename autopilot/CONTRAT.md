# Contrat commun du workflow YouTube Business (Bureau des Faits)

Tout vit dans `section3-motion/pixel-faits/`. Chaque brique lit et écrit **uniquement** ce qui est décrit ici.
Le workflow ne doit jamais s'arrêter : une brique qui échoue met l'épisode en `quarantaine` avec une raison, elle ne bloque pas les autres.

## Dossiers

| Chemin | Rôle |
|---|---|
| `episodes-b/<id>/` | un épisode, tout ce qu'il produit |
| `exports-b/<id>/<id>.mp4` et `qa.json` | vidéo finale 9:16 (Short) et son rapport qualité |
| `autopilot/state/` | états globaux : `claude_blocked.json`, `stock.json`, `gpu.lock`, `youtube_quota.json` |
| `autopilot/secrets/` | jetons OAuth YouTube. **Ignoré par git. Aucune brique ne lit ni n'affiche ce dossier sauf `autopilot/publish/`.** |
| `miniatures-manuelles/<id>.png` | miniature faite à la main : elle a priorité sur la miniature automatique |

## Fichiers d'un épisode (`episodes-b/<id>/`)

- `episode.json` : écrit par le rédacteur. Format : `src/infographie/types.ts` (`Episode`). Texte parlé dans `phrases` (nombres écrits en lettres).
- `faits.json` : `[{ "claim", "valeur", "phrase": <n° de phrase>, "sources": [url, url, ...], "check": [mots/nombres à retrouver dans la page], "verified": [urls vérifiées] }]`.
- `publication.json` : `{ "titre" (≤ 70 car.), "description", "tags": [..], "question_commentaires", "langue": "fr", "contenu_ia": true }`.
- `miniature.png` : 1280×720, ≤ 2 Mo (écrite par la brique miniatures).
- `voice.wav`, `timings.json`, `voice_report.json`, `cache/` : écrits par `autopilot/voice.py`.
- `status.json` : voir ci-dessous.

## `status.json`

```json
{ "etat": "ecrit", "maj": "2026-11-02T16:00:00", "raison": null, "tentatives": 0, "youtube": { "video_id": null, "url": null, "visibilite": null, "publie_a": null } }
```

États, dans l'ordre : `ecrit` → `voix` → `rendu` → `controle` → `pret` → `programme` → `publie`.
Hors parcours : `quarantaine` (raison obligatoire, l'épisode attend une relecture humaine).
Chaque brique **ne fait avancer que l'état qu'elle possède** :

| Brique | Passe de → à |
|---|---|
| rédacteur (`autopilot/writer/`) | (rien) → `ecrit` ou `quarantaine` |
| fabrique (`autopilot/make_short.py`) | `ecrit` → `controle` ou `quarantaine` (voix + rendu + `qa.json`) |
| miniatures (`autopilot/miniature.py`) | `controle` → `pret` ou `quarantaine` |
| publieur (`autopilot/publish/`) | `pret` → `programme` → `publie`, ou `quarantaine` |
| orchestrateur (`autopilot/run_daily.py`) | appelle les briques dans l'ordre ; ne modifie jamais le contenu d'un épisode |

Écriture de `status.json` : fichier temporaire puis renommage (atomique). Verrou par épisode : `episodes-b/<id>/.lock` (créé en mode exclusif, supprimé en fin de travail, périmé après 3 h).

## Règles pour toutes les briques

1. **GPU unique** (RTX 3050, 4 Go) : un seul travail de voix à la fois. Prendre `autopilot/state/gpu.lock` avant d'appeler `autopilot/voice.py`. Ne jamais lancer la voix pendant les tests : utiliser `--sans-voix` ou les caches existants.
2. **Disque** : C: est presque plein (moins de 5 Go libres). Garder les sorties petites, ne rien télécharger de volumineux, ne jamais supprimer un fichier qui n'est pas le vôtre.
3. **Rien de secret dans le code ni dans les journaux** : pas de jeton, pas de clé, pas d'adresse e-mail.
4. **Contrôle qualité** : un épisode douteux va en `quarantaine`, jamais en publication.
5. **Honnêteté des données** : les graphiques sont à l'échelle exacte ; tout chiffre prononcé a un fait avec au moins 2 sources, dont une vérifiée.
6. Messages et documentation en français ; code et noms de variables dans le style existant du dépôt.
7. Python : celui du PATH (3.14, bibliothèque standard seulement) pour les scripts d'orchestration. Le Python du venv `C:\VoiceStudio\tts-direct\venv\Scripts\python.exe` n'est utilisé que par `autopilot/voice.py`.
8. Rien n'est commité par les briques : le propriétaire commitera lui-même. Ne basculez pas de branche.

## Libération du disque après publication (règle pour tout le projet)
Quand un épisode passe à `publie` (identifiant YouTube connu), `common.set_status` appelle `common.liberer_disque` : elle supprime les gros fichiers regénérables (`exports-b/<id>/*.mp4|wav`, `episodes-b/<id>/*.wav`, `cache/` de voix) et garde textes, faits, publication, statut, `qa.json`, miniatures ; elle note `nettoyage.json`. Exceptions : un Short attend d'être envoyé à TikTok si le jeton TikTok existe ; un long attend que tous ses Shorts aient leur propre voix. `run_daily.py` repasse sur tous les épisodes publiés à la fin de chaque commande (`common.liberer_tout_publie`). Tests : `autopilot/tests/test_liberer_disque.py`.
