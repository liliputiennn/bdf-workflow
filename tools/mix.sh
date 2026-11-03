#!/usr/bin/env bash
# Mixage final, voix prioritaire.
# Usage : tools/mix.sh <video_sans_voix.mp4> <voix.mp3> <sortie.mp4>
#  1. voix : passe-haut, présence, compression douce, -16 LUFS
#  2. fond (musique + SFX) : bande de la voix creusée (2-4 kHz), puis compressé par la voix (sidechain)
#  3. somme, limiteur, puis normalisation en deux passes à -14 LUFS (niveau TikTok/Reels)
set -euo pipefail
BED="$1"; VOICE="$2"; OUT="$3"
TMP="$(mktemp -d)"
DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$BED")"

ffmpeg -loglevel error -y -i "$VOICE" -af "highpass=f=75,lowpass=f=15000,equalizer=f=220:t=q:w=1.0:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=2.5,acompressor=threshold=-24dB:ratio=3:attack=4:release=140:makeup=3,loudnorm=I=-16:TP=-2:LRA=6,apad=whole_dur=$DUR" -ar 48000 -ac 2 -t "$DUR" "$TMP/voice.wav"

ffmpeg -loglevel error -y -i "$BED" -i "$TMP/voice.wav" -filter_complex "\
[1:a]asplit=2[v][key];\
[0:a]aresample=48000,equalizer=f=2800:t=q:w=1.4:g=-6,equalizer=f=1200:t=q:w=1.0:g=-2,volume=-3dB[bed];\
[bed][key]sidechaincompress=threshold=0.015:ratio=9:attack=6:release=320:knee=4:makeup=1,asplit=2[ducked][dk];\
[v][ducked]amix=inputs=2:weights='1 1':normalize=0,alimiter=limit=0.89:attack=3:release=60[mix]" \
  -map "[mix]" -ar 48000 "$TMP/mix.wav" -map "[dk]" -ar 48000 "$TMP/ducked.wav"

# normalisation deux passes
read -r I TP LRA THR OFF < <(ffmpeg -hide_banner -nostats -i "$TMP/mix.wav" -af loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json -f null - 2>&1 \
  | python -c "import sys,json,re; d=json.loads(re.search(r'\{[\s\S]*\}', sys.stdin.read()).group()); print(d['input_i'],d['input_tp'],d['input_lra'],d['input_thresh'],d['target_offset'])")
ffmpeg -loglevel error -y -i "$TMP/mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=9:measured_I=$I:measured_TP=$TP:measured_LRA=$LRA:measured_thresh=$THR:offset=$OFF:linear=true" -ar 48000 "$TMP/final.wav"

ffmpeg -loglevel error -y -i "$BED" -i "$TMP/final.wav" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k "$OUT"
cp "$TMP/voice.wav" "${OUT%.mp4}-voix-traitee.wav"
cp "$TMP/ducked.wav" "${OUT%.mp4}-fond-duck.wav"
rm -rf "$TMP"
echo "ok -> $OUT"
