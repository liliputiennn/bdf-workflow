"""ElevenLabs : recherche de voix et voix off avec timings au caractère.

La clé est lue dans .env (ligne `ELEVENLABS_API_KEY=...` ou la clé seule) et n'est jamais affichée.

  python tools/eleven.py voices                       # voix FR masculines de la bibliothèque
  python tools/eleven.py add <public_owner_id> <voice_id> <nom>
  python tools/eleven.py tts <voice_id> <script.json> <out_dir> <timings.json>
"""
import base64
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io"
ROOT = Path(__file__).resolve().parent.parent


def key() -> str:
    raw = (ROOT / ".env").read_text(encoding="utf-8-sig").strip().splitlines()
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return line.split("=", 1)[1].strip().strip('"\'') if "=" in line else line
    sys.exit("clé introuvable dans .env")


def call(method: str, path: str, body=None, accept="application/json"):
    req = urllib.request.Request(API + path, method=method)
    req.add_header("xi-api-key", key())
    req.add_header("accept", accept)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")


def voices():
    sub = call("GET", "/v1/user/subscription")
    print(f"abonnement: {sub.get('tier')} | caractères {sub.get('character_count')}/{sub.get('character_limit')}")
    seen = set()
    for q in ({"language": "fr", "gender": "male", "use_cases": "narrative_story"},
              {"language": "fr", "gender": "male", "category": "professional"},
              {"language": "fr", "gender": "male"}):
        q = {**q, "page_size": "30", "sort": "cloned_by_count"}
        res = call("GET", "/v1/shared-voices?" + urllib.parse.urlencode(q))
        for v in res.get("voices", []):
            if v["voice_id"] in seen:
                continue
            seen.add(v["voice_id"])
            desc = (v.get("description") or "").replace("\n", " ")[:90]
            print(f"{v['voice_id']} | {v['public_owner_id']} | {v.get('name')} | {v.get('age')} | {v.get('accent')} | "
                  f"{v.get('use_case')} | uses={v.get('cloned_by_count')} | {desc}")


def add(owner: str, voice_id: str, name: str):
    res = call("POST", f"/v1/voices/add/{owner}/{voice_id}", {"new_name": name})
    print("ajoutée:", res)


def tts(voice_id: str, script: str, out_dir: str, timings: str):
    lines = json.loads(Path(script).read_text(encoding="utf-8"))
    # Texte continu : une phrase par ligne, l'intonation reste naturelle d'une phrase à l'autre.
    texts = [l.get("eleven", l["text"]) for l in lines]
    full = "\n".join(texts)
    body = {
        "text": full,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.42, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True, "speed": 1.04},
    }
    res = call("POST", f"/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128", body)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "voice.mp3").write_bytes(base64.b64decode(res["audio_base64"]))
    al = res["alignment"]
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    # découpe par phrase puis par mot
    result, pos = [], 0
    for text in texts:
        words, cur, cs = [], "", None
        start = st[pos]
        for k in range(len(text)):
            c, s0, e0 = chars[pos + k], st[pos + k], en[pos + k]
            if c.isspace():
                if cur:
                    words.append({"w": cur, "start": round(cs, 3), "end": round(prev_e, 3)})
                cur, cs = "", None
            else:
                if cs is None:
                    cs = s0
                cur += c
                prev_e = e0
        if cur:
            words.append({"w": cur, "start": round(cs, 3), "end": round(prev_e, 3)})
        end = en[pos + len(text) - 1]
        result.append({"start": round(start, 3), "end": round(end, 3), "words": words})
        pos += len(text) + 1  # saut de ligne
    total = en[-1] + 1.4
    Path(timings).write_text(json.dumps({"total": round(total, 3), "lines": result}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok: {len(result)} phrases, {total:.1f}s")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"voices": voices, "add": add, "tts": tts}[cmd](*args)
