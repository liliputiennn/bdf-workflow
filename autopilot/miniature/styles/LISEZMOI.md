# Ajouter un style de miniature à partir d'une référence

Tout le rendu est dans `src/miniature/` ; le contrôle qualité dans `autopilot/miniature.py`. Un « style » est un composant React de 20 à 40 lignes.

## 1. Lire la référence et remplir une fiche

Regarde l'image (et sa version réduite à 168 px de large : ce qui n'y est pas lisible ne compte pas) et note :

| Question | Exemple |
|---|---|
| Combien de mots ? (3 à 5 maximum) | « 14 % », 1 mot |
| Hauteur du texte principal / hauteur de l'image | 55 % |
| Largeur occupée par le texte principal | 50 % (jamais moins d'un tiers) |
| Police et casse | très grasse, capitales (Anton) |
| Couleurs : fond / texte / accent | fond sombre, texte jaune, accent rouge |
| Un seul objet central ? lequel, où ? | une carte, à droite |
| Effets | ombre dure, contour, rayons, flèche |
| Zone libre en bas à droite (durée YouTube) | oui |

## 2. Écrire le style

Dans `src/miniature/Miniature.tsx`, copie le composant le plus proche (`ChiffreChoc`, `Question` ou `Contraste`) et adapte-le. Outils disponibles :

- `<Texte g={1|2|3}>` : un texte. **`g=1` = texte principal** (contrôlé : contraste ≥ 4,5, ≥ un tiers de la largeur, pas coupé, pas sous la durée YouTube) ;
  `g=2` second texte important, `g=3` légendes (mesurés, jamais bloquants). Tout texte doit passer par `Texte` : c'est ce qui le rend visible au contrôle.
- `<Deco>` : décor (aplats, rayons, icône) ; invisible dans le rendu de contrôle.
- `ajuste(texte, largeurMax, hauteurMax)` : corps de police qui tient dans la boîte.
- `<Icon nom=... th=... />` : icônes de `src/infographie/icons.tsx` (une seule par miniature).
- Les couleurs viennent **toujours du thème** (`th.accent`, `th.deep`, `th.hot`, `th.ink`, `pal(th)`) : le style marche alors avec tous les thèmes de `src/infographie/themes.ts`,
  clairs ou sombres. Ne mets jamais de couleur codée en dur sauf pour un détail neutre (ombre noire).

## 3. L'enregistrer (4 endroits)

1. `src/miniature/resolve.ts` : ajoute le nom dans `STYLES` ; si le style a besoin de données nouvelles, ajoute le champ dans `MiniatureSpec` et sa déduction dans `resolveMiniature`
   (toujours prévoir un repli : si les données manquent, retomber sur `chiffre` ou `question`).
2. `src/miniature/Miniature.tsx` : une ligne `{resolved.style === "mon-style" && <MonStyle ... />}` dans `MiniatureView`.
3. `autopilot/miniature.py` : ajoute le nom dans `STYLES` (l'ordre = l'ordre des mises en page de secours).
4. `autopilot/miniature/exemples.py` : un jeu de données dans `EXEMPLES`, puis `python autopilot/miniature/exemples.py` régénère `planche.png`.

## 4. Vérifier

```bash
python autopilot/miniature/exemples.py            # rend styles × thèmes + planche, affiche le verdict du contrôle
npx vitest run tests/miniature.test.ts            # logique de déduction
python -m unittest discover -s autopilot/tests    # logique du contrôle et des états
```

Ouvre `planche.png` : la rangée du bas montre chaque miniature en 168×94 px. Si tu ne comprends pas la miniature en un coup d'œil à cette taille, elle est à refaire.

## Principes à ne pas casser

3 à 5 mots, texte énorme, un seul objet central, contraste fort, thème de l'épisode respecté, aucune marque réelle copiée,
rien d'important dans le coin bas droit (la durée de la vidéo s'y affiche).
