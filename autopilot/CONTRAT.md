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

## Plusieurs chaînes (moteur à profils, 8 nov. 2026)

Conception : `docs/superpowers/specs/2026-11-08-moteur-chaines-design.md`. Un profil par chaîne : `autopilot/chaines/<id>.json` (lu par `autopilot/chaines.py`) ; sans dossier de profils, seule la chaîne `fr` existe, comme avant.

- **Appartenance** : `episodes-b/<id>/status.json` porte `chaine_id`. Sans ce champ, l'épisode est de la chaîne par défaut (`fr`) : aucun épisode existant n'est à migrer (`python autopilot/chaines.py migrer` ajoute le champ, rien d'autre). Un Short découpé d'un long garde la chaîne de son long. Toutes les chaînes partagent `episodes-b/` et `exports-b/` : les identifiants sont uniques (les sujets des autres chaînes sont préfixés `<chaine>-`).
- **États** : inchangés (tableau plus haut). Chaque brique ne traite que les épisodes des chaînes **actives** (`active: true` et profil valide) ; une chaîne inactive est ignorée par toutes.
- **Quota** : un seul registre `state/youtube_quota.json` pour toutes les chaînes (même projet Google) ; `par_chaine` en donne le détail.
- **Isolation** : l'échec d'un épisode ou d'une chaîne (jeton refusé, erreur imprévue) n'arrête pas les autres ; un quota épuisé arrête tout.
- **Secrets** : un jeton par chaîne (`jeton_fichier` du profil, dans `autopilot/secrets/`). Seul `autopilot/publish/` l'ouvre ; il écrit `state/jetons.json` (booléens) que les autres briques et la web app lisent. Connexion d'une chaîne : `autopilot/publish/CONNECTER-UNE-CHAINE.md`.
- **Rédacteur** : `stock.py besoin --chaine <id>` puis `valider.py <id> --chaine <id>` (sans `--chaine` : chaîne par défaut).
- **TikTok** : seulement la chaîne par défaut (un seul compte), sauf `"tiktok": true` dans le profil.

## Multilingue (chantier 2, 9 nov. 2026)

Conception : `docs/superpowers/specs/2026-11-08-multilingue-design.md`. Une chaîne dont le profil a une `source` (ex. `en` ← `fr`, mode `traduction`) reprend les épisodes de sa source **adaptés** (jamais copiés) : `autopilot/traduction/`.

- **Épisode adapté** : `episodes-b/<cible>-<id source>/`, `status.json` avec `chaine_id` de la cible, `traduction.json` (`source`, `moteur` = `claude` ou `marian`, `a_relire`, `acceptee`), `episode.json` avec `langue`. Même nombre de phrases, mêmes scènes, mêmes chiffres, mêmes faits et sources que la source (`traduction/parite.py`) ; texte parlé sans chiffre (mots-nombres), dans la langue cible.
- **Demandes** : `episodes-b/_traductions/<id>/demande.json` (créées par `traduire.py besoin`, consommées à l'acceptation ou à la quarantaine). Claude (rédacteur planifié) écrit le brouillon puis `valider.py <id> --chaine <cible>` ; si Claude est bloqué (`state/claude_blocked.json`) ou muet depuis `source.attente_claude_heures`, le repli gratuit (MarianMT, Apache-2.0) prend les Shorts.
- **Préparation sans publication** : `preparation: true` dans le profil = l'orchestrateur fabrique voix, rendu et miniature (stock), mais seul `active: true` autorise la publication. **Aucune brique n'écrit `active`.**
- **Décalage** : l'adaptation n'est publiable que `source.decalage_heures` (48 h) après la publication de sa source (`traduction/decalage.py`, appelé par le publieur).
- **Voix** : `voix/<langue>/voix.json` (voix intégrée Qwen3-TTS CustomVoice, Apache-2.0) ou `ref.wav` + `ref.txt` (clonage, prioritaire). L'orchestrateur transmet `BDF_LANGUE`, `BDF_LOCUTEUR`, `BDF_STYLE`, `BDF_VITESSE` ; `voice.py` en déduit la langue de synthèse et de Whisper. Sans ces variables : français inchangé.
- **État** : `autopilot/state/traduction.json` (file, adaptés par état, voix, moteur de repli) lu par la web app. Commande : `python autopilot/run_daily.py traduire` (appelée aussi au début de `fabriquer`).
