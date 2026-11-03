"""Cale un MP3 de voix off (généré sur le site ElevenLabs) sur le script, au mot près.

Usage (venv rush-sorter) : python tools/align.py <voix.mp3> <script.json> <timings.json>
Whisper donne les mots horodatés ; on les aligne sur les mots du script (difflib),
puis on reconstruit début/fin de chaque phrase et de chaque mot.
"""
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8")
audio, script_path, out_path = sys.argv[1:4]


def norm(w: str) -> str:
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


lines = json.loads(Path(script_path).read_text(encoding="utf-8"))
script_words = []  # (ligne, mot affiché)
for li, l in enumerate(lines):
    for w in l["text"].replace("…", " ").split():
        if norm(w):
            script_words.append((li, w))

model = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = model.transcribe(audio, language="fr", word_timestamps=True, initial_prompt=" ".join(l["text"] for l in lines))
heard = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]

a = [norm(w) for _, w in script_words]
b = [norm(w) for w, _, _ in heard]
sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
times: list = [None] * len(a)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
        for k in range(i2 - i1):
            times[i1 + k] = (heard[j1 + k][1], heard[j1 + k][2])
    elif tag == "replace" and j2 > j1:
        # bloc de tailles différentes : on répartit linéairement
        t0, t1 = heard[j1][1], heard[j2 - 1][2]
        n = i2 - i1
        for k in range(n):
            times[i1 + k] = (t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n)
# trous : interpolation entre voisins connus
for i in range(len(times)):
    if times[i] is None:
        prev = next((times[j] for j in range(i - 1, -1, -1) if times[j]), (0, 0))
        nxt = next((times[j] for j in range(i + 1, len(times)) if times[j]), (prev[1] + 0.3, prev[1] + 0.6))
        times[i] = (prev[1], max(prev[1] + 0.05, nxt[0]))

result = []
for li in range(len(lines)):
    ws = [{"w": w, "start": round(times[k][0], 3), "end": round(times[k][1], 3)} for k, (l, w) in enumerate(script_words) if l == li]
    result.append({"start": ws[0]["start"], "end": ws[-1]["end"], "words": ws})
total = heard[-1][2] + 1.4
Path(out_path).write_text(json.dumps({"total": round(total, 3), "lines": result}, ensure_ascii=False, indent=1), encoding="utf-8")
matched = sum(1 for tag, i1, i2, *_ in sm.get_opcodes() if tag == "equal" for _ in range(i2 - i1))
print(f"ok : {len(result)} phrases, {total:.1f} s, {matched}/{len(a)} mots reconnus à l'identique")
