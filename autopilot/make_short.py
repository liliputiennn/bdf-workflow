"""Fabrique un Short complet à partir d'un épisode : validation -> voix -> rendu -> mixage final -> contrôle qualité.

Usage :  python autopilot/make_short.py <id> [--essais 4] [--sans-voix] [--max-duree 60]
Entrée   episodes-b/<id>/episode.json   (écrit par Claude, voir le schéma dans src/infographie/types.ts)
Sortie   exports-b/<id>/<id>.mp4  +  qa.json   (code retour 0 = publiable, 2 = en quarantaine)
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = r"C:\VoiceStudio\tts-direct\venv\Scripts\python.exe"
SCENE_TYPES = {"titre-geant", "chiffre", "barres", "courbe", "ligne-temps", "anneau", "duel", "objet", "question", "liste", "fiche", "annonce", "photo"}
def _themes() -> set[str]:
    """Les thèmes connus sont ceux de src/infographie/themes.ts : une seule source de vérité."""
    try:
        src = (ROOT / "src" / "infographie" / "themes.ts").read_text(encoding="utf-8")
        trouves = set(re.findall(r'^  "([a-z0-9-]+)": \{', src, re.M))
    except OSError:
        trouves = set()
    return trouves or {"papier-vert", "menthe", "nuit-vert"}


THEMES = _themes()
ICONES = {"carte", "hotdog", "magasin", "pieces", "panier"}
FORBIDDEN = re.compile(r"\b(garanti|sans risque|devenez riche|100 ?% ?sûr)\b", re.I)


def validate(ep: dict) -> list[str]:
    """Contrôles de forme (le fond, lui, se vérifie via les sources de chaque chiffre)."""
    err = []
    for k in ("id", "titre", "theme", "chaine", "phrases", "scenes"):
        if k not in ep:
            err.append(f"« {k} » manque")
    if err:
        return err
    if ep["theme"] not in THEMES:
        err.append(f"thème « {ep['theme']} » inconnu ({', '.join(sorted(THEMES))})")
    if ep.get("theme_accent") is not None and ep["theme_accent"] not in THEMES:
        err.append(f"thème d'accent « {ep['theme_accent']} » inconnu")
    for i, s in enumerate(ep["scenes"], 1):
        if isinstance(s, dict) and s.get("theme") is not None and s["theme"] not in THEMES:
            err.append(f"scène {i} : thème « {s['theme']} » inconnu")
    n = len(ep["phrases"])
    if not 4 <= n <= 24:
        err.append(f"{n} phrases : il en faut de 4 à 24")
    prev, last_type = 0, ""
    for i, s in enumerate(ep["scenes"]):
        if s.get("type") not in SCENE_TYPES:
            err.append(f"scène {i + 1} : type « {s.get('type')} » inconnu")
            continue
        ph = s.get("phrase")
        if not isinstance(ph, int) or not 1 <= ph <= n:
            err.append(f"scène {i + 1} : « phrase » doit être entre 1 et {n}")
        elif ph <= prev:
            err.append(f"scène {i + 1} : les scènes doivent avancer dans le script")
        else:
            prev = ph
        if i == 0 and s.get("phrase") != 1:
            err.append("la première scène doit commencer à la phrase 1")
        if s["type"] == last_type:
            err.append(f"scène {i + 1} : deux « {s['type']} » de suite")
        last_type = s["type"]
        if s["type"] == "objet" and s.get("params", {}).get("icone") not in ICONES:
            err.append(f"scène {i + 1} : icône inconnue ({', '.join(sorted(ICONES))})")
    for i, p in enumerate(ep["phrases"]):
        if FORBIDDEN.search(p):
            err.append(f"phrase {i + 1} : formulation interdite (promesse de gain)")
        if len(p) > 140:
            err.append(f"phrase {i + 1} : trop longue ({len(p)} caractères)")
    return err


def run(cmd, **kw):
    print("$", " ".join(map(str, cmd)) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, check=True, **kw)


def loudness(path: Path) -> dict:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    return json.loads(re.search(r"\{[\s\S]*\}", out).group())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--essais", type=int, default=4)
    ap.add_argument("--sans-voix", action="store_true")
    ap.add_argument("--voix-prete", action="store_true", help="Short dérivé d'un long : voice.wav et timings.json existent déjà, voice.py n'est jamais appelé")
    ap.add_argument("--max-duree", type=float, default=60.0)
    a = ap.parse_args()
    ep_dir = ROOT / "episodes-b" / a.id
    if (ep_dir / "origine.json").exists():  # Short dérivé d'un long (cut_shorts.py) : sa voix vient du long, jamais de voice.py
        a.voix_prete = True
    out_dir = ROOT / "exports-b" / a.id
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    qa = {"id": a.id, "problemes": [], "alertes": []}

    ep = json.loads((ep_dir / "episode.json").read_text(encoding="utf-8"))
    qa["problemes"] += validate(ep)
    if qa["problemes"]:
        (out_dir / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Épisode invalide :", *qa["problemes"], sep="\n - ")
        return 2

    if a.voix_prete:
        manque = [f for f in ("voice.wav", "timings.json") if not (ep_dir / f).exists()]
        if manque:
            qa["problemes"].append("voix prête annoncée mais absente : " + ", ".join(manque))
            (out_dir / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
            print("Épisode invalide :", *qa["problemes"], sep="\n - ")
            return 2
    if not a.sans_voix and not a.voix_prete:
        voix = [VENV_PY, str(ROOT / "autopilot" / "voice.py")]
        if os.environ.get("BDF_VOIX") == "kaggle":  # cloud : voix sur le GPU gratuit de Kaggle
            voix = [sys.executable, str(ROOT / "autopilot" / "cloud" / "kaggle" / "lancer_voix.py")]
        run([*voix, str(ep_dir), "--essais", str(a.essais)],
            env={**__import__("os").environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"})
    rep = json.loads((ep_dir / "voice_report.json").read_text(encoding="utf-8")) if (ep_dir / "voice_report.json").exists() else {"a_relire": []}
    for r in rep["a_relire"]:
        qa["alertes"].append(f"phrase {r['phrase']} : lecture douteuse (score {r['score']}) : entendu « {r['entendu']} »")

    # images automatiques (scènes photo/annonce avec « recherche ») : un échec n'empêche jamais le rendu
    subprocess.run([sys.executable, str(ROOT / "autopilot" / "visuels.py"), str(ep_dir)], check=False)
    silent = out_dir / "rendu.mp4"
    run(f'npx remotion render src/infographie/index.ts Short "{silent}" --props="{{\\"id\\":\\"{a.id}\\"}}" --public-dir=episodes-b --concurrency={os.environ.get("BDF_CONCURRENCY", "4")}', cwd=ROOT, shell=True)

    # mixage final : voix déjà à -16 LUFS, on normalise l'ensemble à -14 LUFS (deux passes) et on remux
    m = loudness(silent)
    final = out_dir / f"{a.id}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=9:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", str(final)])
    silent.unlink()

    # contrôles qualité
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout)
    f = loudness(final)
    qa.update({"duree_s": round(dur, 1), "lufs": float(f["input_i"]), "pic_dbtp": float(f["input_tp"]), "calcul_total_s": round(time.time() - t0)})
    if dur > a.max_duree:
        qa["problemes"].append(f"durée {dur:.0f} s > {a.max_duree:.0f} s")
    if not -15.5 <= qa["lufs"] <= -12.5:
        qa["problemes"].append(f"volume {qa['lufs']} LUFS hors de -14 ± 1,5")
    if qa["pic_dbtp"] > -0.5:
        qa["problemes"].append(f"pic {qa['pic_dbtp']} dBTP : risque d'écrêtage")
    qa["publiable"] = not qa["problemes"] and not qa["alertes"]
    (out_dir / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=1))
    return 0 if qa["publiable"] else 2


if __name__ == "__main__":
    sys.exit(main())
