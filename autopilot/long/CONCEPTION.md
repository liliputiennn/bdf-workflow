# Format long + Shorts dérivés (« un long qui donne des Shorts »)

Complète `autopilot/CONTRAT.md`. Rien du moteur 9:16 (`src/infographie/`) ni de `make_short.py` n'est changé dans son comportement.

## 1. Fichier `episodes-b/<id>/episode-long.json`

```json
{ "id": "...", "titre": "...", "theme": "papier-vert", "chaine": "Bureau des Faits", "pause_chapitre_s": 2.0,
  "chapitres": [
    { "titre": "Le piège de la marge",
      "carte": true,
      "phrases": ["…", "…"],
      "scenes": [ { "type": "chiffre", "phrase": 1, "params": {} } ],
      "short": { "debut_phrase": 3, "fin_phrase": 9, "accroche": "Costco ne gagne rien sur tes courses." } } ] }
```

- Les **scènes** sont les mêmes types et paramètres que `src/infographie/types.ts` (dix types, mêmes icônes).
- Numéros de `phrase` (scènes et `short`) **relatifs au chapitre** (1 = première phrase du chapitre). La 1ʳᵉ scène d'un chapitre commence à sa phrase 1. Les faits (`faits.json`) utilisent la numérotation **globale** (1..N sur tout le long).
- Le chapitre 1 est l'accroche (« cold open »), sans carte de titre. Les autres ont une carte (`"carte": false` pour la retirer).
- Contraintes (`make_long.validate_long`) : 4 à 12 chapitres, 70 à 260 phrases (≈ 8-12 min parlées, cible 1 400-2 000 mots), ≤ 160 caractères par phrase, deux scènes de même type jamais consécutives dans un chapitre, au plus 3 Shorts marqués, chacun de 4 à 24 phrases, tenant dans un seul chapitre et ≤ 58 s une fois la voix produite.

## 2. Audio : une seule voix continue

`make_long.py` aplatit les phrases (ordre des chapitres) dans `voix-entree.json` (`phrases` + `pauses`) et appelle `voice.py --episode-file voix-entree.json` : même voix clonée, même cache par phrase (`cache/NN-<hash>.wav`), donc une phrase corrigée ne régénère que celle-là. Avant la 1ʳᵉ phrase de chaque chapitre à carte, `pauses` ajoute `pause_chapitre_s` de silence (la carte de titre s'affiche pendant ce silence). Sortie : `voice.wav` (48 kHz, -16 LUFS sur l'ensemble) et `timings.json` au format habituel, en temps absolu du long. `make_long` en dérive `chapitres.json` (début/fin de chaque chapitre).

**Limite GPU** : `voice.py --budget-s 5400` s'arrête proprement (code 3) avant une nouvelle phrase une fois 90 min écoulées ; `make_long` libère alors `gpu.lock`, laisse l'état à `ecrit` avec `voix_progression` et sort en code 3 (« à reprendre »). Le lancement suivant reprend au cache, phrase par phrase. Le chargement du modèle (~1 min) est le seul coût d'une reprise.

## 3. Rendu 16:9 (`src/long/index.tsx`, composition `Long`, 1920×1080, 30 i/s)

Mêmes thèmes, icônes, courbes d'animation que le 9:16 ; scènes redessinées en paysage (`src/long/scenes.tsx`). En plus : sous-titres sur une à deux lignes en bas, carte de titre animée à chaque chapitre, barre de progression par chapitre (segments proportionnels à la durée) avec titre du chapitre en haut à droite. Le rendu se fait **par chapitre** (`--frames`, un bundle unique, `--concurrency=2`, `--muted`) : un chapitre fini n'est jamais refait si le travail est interrompu. Les segments sont assemblés sans recompression, puis l'audio `voice.wav` est ajouté et normalisé à -14 LUFS (deux passes). `qa.json` : durée, LUFS, pic, chapitres (début, fin, durée), alertes de relecture ; cible 7-13 min.

## 4. Découpe en Shorts (`cut_shorts.py <id>`)

On **re-rend en 9:16** avec le moteur existant, à partir des mêmes données : pas de recadrage de la vidéo 16:9. Pour chaque chapitre marqué (3 au plus) : `episodes-b/<id>-sN/` reçoit `episode.json` (phrases `debut..fin`, scènes recalées, la scène active au début passe à la phrase 1, doublons de type fusionnés), `timings.json` (temps recalés, `lead` 0,15 s), `voice.wav` (extrait du `voice.wav` du long, fondu 25/80 ms, normalisé -16 LUFS comme `voice.py`), `faits.json` filtré et renuméroté, `publication.json` (titre = accroche, renvoi vers le long), `origine.json`, et un `status.json` à `ecrit`. `make_short.py <id>-sN --voix-prete` valide, **saute `voice.py`** (voix et timings déjà présents) et rend. Un Short ne fait jamais appel à la voix.

## 5. États et temps de calcul

Le long suit `ecrit → controle → pret → …` comme un Short (`make_long` possède `ecrit → controle`). Les Shorts dérivés naissent à `ecrit` avec voix prête. Estimation pour un long de 10 min : voix 40-80 min (GPU, découpée en reprises de ≤ 90 min), rendu 16:9 ≈ 25-45 min (18 000 images, CPU), mixage 1 min ; chaque Short dérivé ≈ 3-5 min de rendu.

## 6. Commandes

```
python autopilot/long/make_demo.py                      # démo sans voix : episodes-b/_demo-long/
python autopilot/make_long.py <id> [--budget-min 90]     # voix (reprises) -> Shorts -> rendu -> qa.json ; code 3 = relancer
python autopilot/cut_shorts.py <id>                      # (déjà lancé par make_long) crée <id>-s1..s3
python autopilot/make_short.py <id>-s1                   # rend un Short dérivé (voix jamais régénérée)
python -m unittest discover -s autopilot/long/tests
```
