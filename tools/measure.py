"""Mesures audio pour la Console.

  takes   <script.json> <out.json> <prise1.mp3> [...]                    : compare les prises de voix
  clarity <voix.wav> <fond.wav> <timings.json> <script.json> <final.mp4> <out.json> : clarté de la voix dans le mix
"""
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8")
_model = None


def model():
    global _model
    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    return _model


def norm(w: str) -> str:
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


def ref_words(script_path: str):
    lines = json.loads(Path(script_path).read_text(encoding="utf-8"))
    return [norm(w) for l in lines for w in l["text"].replace("…", " ").split() if norm(w)]


def similarity(audio: str, ref) -> float:
    segs, _ = model().transcribe(audio, language="fr")
    hyp = [norm(w) for s in segs for w in s.text.split() if norm(w)]
    return round(difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False).ratio() * 100, 1)


def pauses(audio: str) -> int:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", audio, "-af", "silencedetect=n=-40dB:d=0.35", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return out.count("silence_end")


def takes(script_path, out_path, *files):
    ref = ref_words(script_path)
    res = {}
    for i, f in enumerate(files):
        res[Path(f).name] = {"similarity": similarity(f, ref), "pauses": pauses(f)}
        print(f"{i + 1}/{len(files)}", flush=True)
    Path(out_path).write_text(json.dumps(res, indent=1), encoding="utf-8")


def clarity(voice_wav, bed_wav, timings_path, script_path, final_mp4, out_path):
    v, sr = sf.read(voice_wav)
    b, _ = sf.read(bed_wav)
    v = v.mean(1) if v.ndim > 1 else v
    b = b.mean(1) if b.ndim > 1 else b
    n = min(len(v), len(b))
    v, b = v[:n], b[:n]
    lines = json.loads(Path(timings_path).read_text(encoding="utf-8"))["lines"]
    w = int(0.25 * sr)
    medians, worst = [], 99.0
    for l in lines:
        a, e = int(l["start"] * sr), int(l["end"] * sr)
        vals = []
        for k in range(a, max(a + 1, e - w), w):
            x = np.sqrt(np.mean(v[k:k + w] ** 2))
            y = np.sqrt(np.mean(b[k:k + w] ** 2)) + 1e-9
            if x > 0.02:
                vals.append(20 * np.log10(x / y))
        if vals:
            medians.append(float(np.median(vals)))
            worst = min(worst, float(min(vals)))
    print("1/2", flush=True)
    whisper = similarity(final_mp4, ref_words(script_path))
    print("2/2", flush=True)
    res = {"medianDb": round(float(np.median(medians)), 1), "worstDb": round(worst, 1), "whisper": whisper}
    Path(out_path).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"takes": takes, "clarity": clarity}[cmd](*args)
