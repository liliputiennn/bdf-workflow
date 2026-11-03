"""Voix off locale (Kokoro, gratuit) : une phrase à la fois, timings exacts.

Usage : python tools/tts.py episodes/<slug>/script.json public/<id> src/episodes/<id>.timings.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

CACHE = Path.home() / ".cache/hyperframes/tts"
VOICE, SPEED, LANG = "ff_siwis", 1.12, "fr-fr"
LEAD, GAP, LONG_GAP = 0.35, 0.22, 0.6

script_path, out_dir, timings_path = map(Path, sys.argv[1:4])
lines = json.loads(script_path.read_text(encoding="utf-8"))
kokoro = Kokoro(str(CACHE / "models/kokoro-v1.0.onnx"), str(CACHE / "voices/voices-v1.0.bin"))

chunks, timings, t, sr = [], [], LEAD, 24000
chunks.append(np.zeros(int(LEAD * sr), dtype=np.float32))
for i, line in enumerate(lines):
    audio, sr = kokoro.create(line.get("say", line["text"]), voice=VOICE, speed=SPEED, lang=LANG)
    # coupe les silences de bord pour un débit serré
    nz = np.flatnonzero(np.abs(audio) > 0.01)
    audio = audio[max(0, nz[0] - 600): nz[-1] + 1200] if nz.size else audio
    dur = len(audio) / sr
    timings.append({"start": round(t, 3), "end": round(t + dur, 3)})
    gap = LONG_GAP if line["text"].endswith(("?", "entendue.")) else GAP
    chunks += [audio.astype(np.float32), np.zeros(int(gap * sr), dtype=np.float32)]
    t += dur + gap
    print(f"{i:02d} {dur:5.2f}s  {line['text'][:50]}")

out_dir.mkdir(parents=True, exist_ok=True)
sf.write(out_dir / "voice.wav", np.concatenate(chunks), sr)
timings_path.parent.mkdir(parents=True, exist_ok=True)
timings_path.write_text(json.dumps({"total": round(t + 1.2, 3), "lines": timings}, indent=1))
print(f"TOTAL {t:.2f}s")
