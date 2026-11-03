#!/usr/bin/env bash
# Retélécharge musique et SFX Pixabay (licence Pixabay : usage commercial OK, pas de redistribution tels quels)
# puis les normalise pour Remotion. Usage : bash tools/fetch-audio.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p public/fx public/music
while read -r n p _; do
  [ -f "sfx-src/$n.mp3" ] || curl -sSL -A "Mozilla/5.0" -o "sfx-src/$n.mp3" "https://cdn.pixabay.com/audio/$p"
  ffmpeg -loglevel error -y -i "sfx-src/$n.mp3" -af "loudnorm=I=-16:TP=-1.5,aresample=44100" -ac 2 "public/fx/$n.wav"
done < sfx-src/list.txt
while read -r n p; do
  [ -f "public/music/$n.mp3" ] || curl -sSL -A "Mozilla/5.0" -o "public/music/$n.mp3" "https://cdn.pixabay.com/audio/$p"
done < sfx-src/music.txt
ffmpeg -loglevel error -y -i public/music/detective-documentary.mp3 -af "loudnorm=I=-18:TP=-2" public/music/bed.wav
echo "ok : $(ls public/fx | wc -l) SFX, musique prête"
