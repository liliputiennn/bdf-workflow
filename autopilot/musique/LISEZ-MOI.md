# Musiques de fond

Mets ici 6 à 8 pistes **sans voix** (mp3, wav, m4a, ogg ou flac, 2 minutes ou plus). Elles sont mixées automatiquement sous la voix de chaque vidéo (longs, Shorts, Shorts tirés des longs) : la musique baisse quand la voix parle et remonte dans les pauses.

## Où les prendre (Pixabay Music)

1. Va sur https://pixabay.com/music/ et cherche par exemple : `corporate`, `motivational`, `lofi`, `upbeat background`, `inspiring`, `technology`.
2. Garde des pistes **instrumentales**, régulières, sans gros solo ni montée dramatique (une mélodie qui accroche distrait de la voix).
3. Mélange 2 ambiances : calme (lo-fi, piano léger) et énergique (rythmé, motivant), 3 à 4 pistes chacune. Les longs enchaînent plusieurs pistes en fondu.
4. Télécharge-les ici. Pour imposer une piste à un épisode, ajoute `"musique": "début-du-nom-de-fichier"` dans son JSON ; pour n'avoir aucune musique : `"musique": "aucune"`.
5. Note dans `sources.txt` (une ligne par piste : nom du fichier + adresse de la page Pixabay). C'est ta preuve de licence si une réclamation arrive un jour.

## Licence

La licence Pixabay autorise l'usage commercial (YouTube monétisé compris) sans citer l'auteur, mais **interdit de redistribuer les fichiers tels quels**. Comme le dépôt GitHub est public, ces fichiers n'y sont jamais envoyés (voir `.gitignore`) : en cloud ils viennent d'un jeu de données Kaggle **privé**.

## Envoi vers le cloud

```
powershell -File autopilot/cloud/kaggle/envoyer_musique.ps1
```

À refaire seulement quand tu changes les pistes. La fabrication cloud suivante télécharge le jeu automatiquement. Sans jeu de données ou sans piste, les vidéos sortent comme avant, voix seule.
