"""Aides de test : fausse voix (bips au rythme des mots, sans modèle ni GPU) et épisodes minimaux pour chaque format."""
import json
import wave
from pathlib import Path

import numpy as np

SR = 48000


def fausse_voix(ep_dir: Path, phrases: list[str], pauses: dict | None = None, mot_s: float = 0.28, ecart_s: float = 0.14) -> dict:
    """Écrit voice.wav + timings.json au format de voice.py (lead 0,15 s, `pauses` = secondes de silence avant la phrase n, 1 = première)."""
    pauses = {int(k): float(v) for k, v in (pauses or {}).items()}
    t, morceaux, lignes = 0.15, [np.zeros(int(0.15 * SR), dtype=np.float32)], []
    for i, ph in enumerate(phrases):
        if pauses.get(i + 1, 0) > 0 and i > 0:
            morceaux.append(np.zeros(int(pauses[i + 1] * SR), dtype=np.float32))
            t += pauses[i + 1]
        mots = ph.split()
        mots_t = []
        for w in mots:
            n = int(mot_s * SR)
            x = (0.25 * np.sin(2 * np.pi * (180 + 11 * (len(w) % 7)) * np.arange(n) / SR) * np.hanning(n)).astype(np.float32)
            morceaux.append(x)
            mots_t.append({"w": w, "start": round(t, 3), "end": round(t + mot_s, 3)})
            t += mot_s
        debut = mots_t[0]["start"] if mots_t else t
        lignes.append({"start": debut, "end": round(t, 3), "words": mots_t})
        morceaux.append(np.zeros(int(ecart_s * SR), dtype=np.float32))
        t += ecart_s
    pcm = (np.concatenate(morceaux) * 32767).astype(np.int16)
    with wave.open(str(ep_dir / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    tim = {"total": round(t, 3), "lines": lignes}
    (ep_dir / "timings.json").write_text(json.dumps(tim, ensure_ascii=False), encoding="utf-8")
    return tim
