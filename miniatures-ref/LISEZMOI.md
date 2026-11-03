# Miniatures de référence

Dépose ici les miniatures qui, selon toi, « font venir les gens » : les tiennes, ou celles d'autres chaînes que tu admires.
Elles servent à **régler le style des miniatures automatiques** de la chaîne. Rien ici n'est publié ni copié tel quel.

## Comment faire

1. Enregistre l'image dans ce dossier (`miniatures-ref/`) : un fichier par miniature, en `.png` ou `.jpg`.
   - Dans YouTube : clic droit sur la miniature → « Copier l'adresse de l'image », ouvre-la dans le navigateur, puis « Enregistrer l'image sous… ». Ou une capture d'écran.
   - Taille idéale 1280×720 ; toute image 16:9 d'au moins 640 px de large convient.
2. Nomme-la de façon courte et claire : `chiffre-banque.png`, `question-hotdog.jpg`, `contraste-avant-apres.png`.
3. **Facultatif mais très utile** : à côté, un petit fichier texte du même nom (`chiffre-banque.txt`) avec une ou deux lignes :
   - ce que tu aimes (« le chiffre est énorme », « le visage », « les couleurs vives »…) ;
   - ce que tu ne veux pas reprendre (« trop chargé », « le logo »…) ;
   - le nombre de vues de la vidéo, si tu le connais.
4. Entre 5 et 20 références suffisent. Mélange les genres (chiffre, question, avant/après…) : c'est la variété qui permet de choisir.

## Ce qui se passe ensuite

Claude lit ces images, en tire une **fiche de style** (taille du texte, nombre de mots, couleurs, place de l'objet central, ambiance) puis ajoute une mise en page
dans `src/miniature/` en suivant `autopilot/miniature/styles/LISEZMOI.md`. Tu retrouves le résultat dans `_test-comparatif/sorties-b/miniatures/planche.png`,
où chaque essai est montré en grand et en 168×94 px (la taille d'une vignette sur mobile).

## Règles

- Les miniatures de référence inspirent un **style** (composition, proportions, énergie) ; on ne copie jamais le visuel, le logo ou la marque d'un tiers.
- Si une miniature est parfaite telle quelle pour une vidéo précise, mets-la plutôt dans `miniatures-manuelles/<id-de-l-épisode>.png` (1280×720, 2 Mo maximum) :
  elle remplace alors la miniature automatique de cet épisode.
