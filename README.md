# Bureau des Faits

Chaîne de faits vrais en pixel art (Remotion) et sa Console de production.

## Lancer la Console

    npm run console

Puis ouvrir http://127.0.0.1:5180. L'API tourne sur 127.0.0.1:5181.

Prérequis : ffmpeg, Git Bash, uv et le venv du tri des rushs (`../../rush-sorter/.venv`, pour Whisper),
et l'audio Pixabay (`bash tools/fetch-audio.sh` sur une nouvelle machine).

## Produire la semaine (1 vidéo par jour)

1. **Semaine** : choisir 7 sujets (banque d'idées ou sujet libre), « Générer le brief », le coller dans
   UNE conversation Claude. Claude écrit d'un coup script, texte voix, texte de publication et scènes.
2. **Importer** la réponse : elle est vérifiée (erreurs en français, avec la ligne) puis les 7 épisodes
   sont créés (`episodes/<id>/scenes.json`, `script.json`, `TEXTE-VOIX.txt`, `POST.md`).
3. **ElevenLabs (site)** : générer chaque voix (Nicolas – Narrator), déposer les MP3 dans « Voix ».
4. **Rendre la semaine** : calage + rendu + paquet `exports/<date>/<id>/` (vidéo, couverture, texte,
   fiche de contrôle). Toast Windows et bandeau à la fin. Publication à la main, case « publié ».

Scènes : un épisode « en données » n'a aucun code. Le stock de types de scène est dans `src/scenes/`
(catalogue : composition `Catalogue-Scenes` dans `npm run dev`). Une scène sur mesure codée une fois
s'ajoute à `src/scenes/custom/` et se réutilise par son nom. Les épisodes signature restent codés
(`src/episodes/`, registre). Après une modification manuelle d'un `scenes.json` : `npm run gen:episodes`.

Lot en ligne de commande : `npm run batch` (semaine en cours), `-- --id=<id>`, `-- --all`, `-- --dry-run`.

## Tests

    npm test
