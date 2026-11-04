"""Fabrique une vidéo longue 16:9 : validation -> voix (GPU, par reprises) -> Shorts -> rendu par chapitre -> mixage -> contrôle qualité.

Usage :  python autopilot/make_long.py <id> [--essais 4] [--budget-min 90] [--sans-voix] [--sans-shorts] [--concurrence 2] [--souple] [--force]
Entrée   episodes-b/<id>/episode-long.json   (format : autopilot/long/CONCEPTION.md)
Sortie   exports-b/<id>/<id>.mp4  +  qa.json
Codes    0 = publiable (état « controle »)   2 = quarantaine   3 = à reprendre (voix inachevée, GPU occupé, panne passagère)
La voix peut prendre plus d'une heure : elle s'arrête proprement après --budget-min minutes (le cache par phrase est conservé),
libère le GPU et sort en code 3 ; relancer la même commande reprend là où elle s'était arrêtée.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "long"))

import common  # noqa: E402
import cut_shorts  # noqa: E402
import longlib as L  # noqa: E402

ROOT = common.ROOT
VENV_PY = r"C:\VoiceStudio\tts-direct\venv\Scripts\python.exe"
FPS = 30
TAIL_FRAMES = 60  # doit rester égal à TAIL dans src/long/Long.tsx
DUREE_MIN_S, DUREE_MAX_S = 5 * 60, 15 * 60  # hors de cette plage : quarantaine
DUREE_CIBLE_S = (6 * 60, 12 * 60)  # hors de cette plage : alerte (choix : 6 à 12 minutes)
ESSAIS_VOIX_MAX = 3


def run(cmd, **kw):
    print("$", " ".join(map(str, cmd)) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, check=True, **kw)


def quarantaine(ep_id: str, qa: dict, raison: str) -> int:
    qa["publiable"] = False
    common.write_json(common.EXPORTS / ep_id / "qa.json", qa)
    common.set_status(ep_id, "quarantaine", raison)
    print("QUARANTAINE :", raison, flush=True)
    return 2


# ─────────── voix ───────────

def voix_a_jour(ep_dir: Path, entree: dict) -> bool:
    ok = (ep_dir / "voice.wav").exists() and (ep_dir / "timings.json").exists()
    return ok and (ep_dir / "voix.sha").exists() and (ep_dir / "voix.sha").read_text().strip() == L.sha(entree)


def lancer_voix(ep_id: str, ep_dir: Path, essais: int, budget_s: float) -> int:
    """Une reprise de voix sous verrou GPU. 0 = terminée, 3 = budget atteint, autre = échec."""
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"}
    cmd = [VENV_PY, str(HERE / "voice.py"), str(ep_dir), "--episode-file", "voix-entree.json", "--essais", str(essais), "--budget-s", str(int(budget_s))]
    if os.environ.get("BDF_VOIX") == "kaggle":  # cloud : la voix tourne sur le GPU gratuit de Kaggle (cloud/kaggle/lancer_voix.py)
        cmd = [sys.executable, str(HERE / "cloud" / "kaggle" / "lancer_voix.py")] + cmd[2:]
    if os.environ.get("BDF_LOCUTEUR"):  # essai d'une voix intégrée (Qwen3 CustomVoice) à la place du clone, pour comparer
        cmd += ["--locuteur", os.environ["BDF_LOCUTEUR"], "--style", os.environ.get("BDF_STYLE", "")]
    with common.gpu_lock(), open(ep_dir / "voice.log", "a", encoding="utf-8") as log, open(ep_dir / "voice.err", "a", encoding="utf-8") as err:
        print("$", " ".join(cmd), flush=True)
        return subprocess.run(cmd, env=env, stdout=log, stderr=err).returncode


def progression(ep_dir: Path, total: int) -> dict:
    faites = 0
    try:
        for m in re.finditer(r"^\[(\d+)/(\d+)\]", (ep_dir / "voice.log").read_text(encoding="utf-8", errors="replace"), re.M):
            if int(m.group(2)) == total:
                faites = int(m.group(1))
    except FileNotFoundError:
        pass
    return {"faites": faites, "total": total, "arret": common.now()}


# ─────────── rendu ───────────

def plages_images(chaps: list[dict], total_s: float) -> list[tuple[int, int]]:
    """Plage d'images [a, b] de chaque chapitre ; elles couvrent exactement 0 .. durée totale."""
    total_f = math.ceil(total_s * FPS) + TAIL_FRAMES
    bornes = [0] + [max(1, round(c["borne_s"] * FPS)) for c in chaps[1:]] + [total_f]
    for i in range(1, len(bornes)):
        bornes[i] = max(bornes[i], bornes[i - 1] + 1)
    return [(bornes[i], bornes[i + 1] - 1) for i in range(len(chaps))]


def rendre_chapitres(ep_id: str, ep_dir: Path, out_dir: Path, plages: list[tuple[int, int]], concurrence: int) -> list[Path]:
    parts = out_dir / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    signature = L.sha([(ep_dir / "episode-long.json").read_text(encoding="utf-8"), (ep_dir / "timings.json").read_text(encoding="utf-8")])
    props = out_dir / ".props.json"
    common.write_json(props, {"id": ep_id})
    bundle = out_dir / ".bundle"
    fichiers = []
    restant = [i for i, (a, b) in enumerate(plages) if not _part_ok(parts, i, signature, a, b)]
    if restant:
        if bundle.exists():
            shutil.rmtree(bundle)
        run(["npx", "remotion", "bundle", "src/long/index.tsx", f"--out-dir={bundle}", "--public-dir=episodes-b"], cwd=ROOT, shell=(os.name == "nt"))
    for i, (a, b) in enumerate(plages):
        f = parts / f"ch{i + 1:02d}.mp4"
        fichiers.append(f)
        if i in restant:
            run(["npx", "remotion", "render", str(bundle), "Long", str(f), f"--props={props}", f"--frames={a}-{b}", "--muted",
                 f"--concurrency={concurrence}", "--crf=24", "--codec=h264"], cwd=ROOT, shell=(os.name == "nt"))
            common.write_json(parts / f"ch{i + 1:02d}.json", {"sig": signature, "a": a, "b": b})
    shutil.rmtree(bundle, ignore_errors=True)
    return fichiers


def _part_ok(parts: Path, i: int, signature: str, a: int, b: int) -> bool:
    meta = common.read_json(parts / f"ch{i + 1:02d}.json")
    return bool(meta) and meta == {"sig": signature, "a": a, "b": b} and (parts / f"ch{i + 1:02d}.mp4").exists()


def assembler(fichiers: list[Path], voix: Path, final: Path, total_frames: int) -> None:
    """Concatène les chapitres sans recompression, ajoute la voix normalisée à -14 LUFS (deux passes)."""
    liste = fichiers[0].parent / "liste.txt"
    liste.write_text("".join(f"file '{f.name}'\n" for f in fichiers), encoding="utf-8")
    m = L.mesure(voix, -14.0, -1.5, 9.0)
    dur = total_frames / FPS
    af = L.filtre_loudnorm(m, -14.0, -1.5, 9.0) + f",apad=whole_dur={dur:.3f}"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(liste), "-i", str(voix), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-t", f"{dur:.3f}", "-movflags", "+faststart", str(final)])


# ─────────── principal ───────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--essais", type=int, default=4)
    ap.add_argument("--budget-min", type=float, default=90.0, help="durée maximale d'une reprise de voix sur le GPU")
    ap.add_argument("--sans-voix", action="store_true", help="n'appelle jamais voice.py (voice.wav et timings.json doivent exister)")
    ap.add_argument("--sans-shorts", action="store_true")
    ap.add_argument("--concurrence", type=int, default=2)
    ap.add_argument("--souple", action="store_true", help="démo/tests : ni taille minimale du texte ni durée minimale")
    ap.add_argument("--force", action="store_true", help="refait aussi un long déjà contrôlé ou plus avancé")
    a = ap.parse_args(argv)

    ep_dir = common.ep_dir(a.id)
    out_dir = common.EXPORTS / a.id
    out_dir.mkdir(parents=True, exist_ok=True)
    qa = {"id": a.id, "format": "long", "problemes": [], "alertes": []}
    t0 = time.time()
    ep = common.read_json(ep_dir / "episode-long.json")
    if ep is None:
        print("episode-long.json introuvable ou illisible")
        return quarantaine(a.id, qa, "episode-long.json introuvable ou illisible")
    etat = common.get_status(a.id)["etat"]
    if etat in ("controle", "pret", "programme", "publie") and not a.force and (out_dir / f"{a.id}.mp4").exists():
        print(f"déjà à l'état « {etat} » (--force pour refaire)")
        return 0

    try:
        with common.episode_lock(a.id):
            return _fabriquer(a, ep, ep_dir, out_dir, qa, t0)
    except TimeoutError:
        print("épisode verrouillé par un autre travail")
        return 3


def _fabriquer(a, ep: dict, ep_dir: Path, out_dir: Path, qa: dict, t0: float) -> int:
    qa["problemes"] += L.validate_long(ep, minimum=not a.souple)
    if qa["problemes"]:
        return quarantaine(a.id, qa, "épisode long invalide : " + " ; ".join(qa["problemes"][:3]))

    entree = L.voix_entree(ep)
    common.write_json(ep_dir / "voix-entree.json", entree)
    qa["phrases"] = len(entree["phrases"])

    # 1. voix : une reprise de ≤ budget minutes, sous verrou GPU
    voix_s = 0
    if not a.sans_voix and not voix_a_jour(ep_dir, entree):
        t_voix = time.time()
        try:
            rc = lancer_voix(a.id, ep_dir, a.essais, a.budget_min * 60)
        except TimeoutError:
            common.set_status(a.id, "ecrit", None, voix_progression=progression(ep_dir, qa["phrases"]))
            print("GPU occupé par un autre travail de voix : à reprendre plus tard")
            return 3
        voix_s = round(time.time() - t_voix)
        if rc == 3:
            prog = progression(ep_dir, qa["phrases"])
            common.set_status(a.id, "ecrit", None, voix_progression=prog)
            print(f"VOIX À REPRENDRE : {prog['faites']}/{prog['total']} phrases faites, GPU libéré")
            return 3
        if rc != 0:
            st = common.get_status(a.id)
            n = st.get("tentatives", 0) + 1
            common.set_status(a.id, "ecrit", None, tentatives=n)
            if n >= ESSAIS_VOIX_MAX:
                return quarantaine(a.id, qa, f"voice.py a échoué {n} fois (code {rc}, voir voice.err)")
            print(f"voice.py a échoué (code {rc}), essai {n}/{ESSAIS_VOIX_MAX} : à reprendre")
            return 3
        (ep_dir / "voix.sha").write_text(L.sha(entree), encoding="utf-8")
        common.set_status(a.id, "ecrit", None, voix_progression=None, tentatives=0)
    elif not (ep_dir / "voice.wav").exists() or not (ep_dir / "timings.json").exists():
        return quarantaine(a.id, qa, "voice.wav / timings.json absents (--sans-voix)")
    qa["voix_calcul_s"] = voix_s

    timings = common.read_json(ep_dir / "timings.json")
    try:
        chaps = L.chapitres_temps(ep, timings)
    except ValueError as e:
        return quarantaine(a.id, qa, f"timings incohérents : {e}")
    rep = common.read_json(ep_dir / "voice_report.json", {"a_relire": []})
    for r in rep.get("a_relire", []):
        qa["alertes"].append(f"phrase {r['phrase']} : lecture douteuse (score {r['score']}) : entendu « {r['entendu']} »")
    common.write_json(ep_dir / "chapitres.json", chaps)

    # 2. Shorts dérivés : ne coûtent qu'un découpage audio, faits dès que la voix existe
    if not a.sans_shorts:
        try:
            qa["shorts"] = [s["id"] for s in cut_shorts.cut(a.id)["shorts"]]
        except Exception as e:  # un Short raté ne bloque jamais le long
            qa["alertes"].append(f"découpe des Shorts échouée : {e}")

    # 3. rendu par chapitre puis assemblage
    plages = plages_images(chaps, float(timings["total"]))
    total_f = plages[-1][1] + 1
    t_rendu = time.time()
    try:
        # images automatiques (scènes photo/annonce avec « recherche ») : un échec n'empêche jamais le rendu
        subprocess.run([sys.executable, str(HERE / "visuels.py"), str(ep_dir)], check=False)
        fichiers = rendre_chapitres(a.id, ep_dir, out_dir, plages, a.concurrence)
        final = out_dir / f"{a.id}.mp4"
        assembler(fichiers, ep_dir / "voice.wav", final, total_f)
    except subprocess.CalledProcessError as e:
        n = common.get_status(a.id).get("tentatives", 0) + 1
        common.set_status(a.id, "ecrit", None, tentatives=n)
        if n >= ESSAIS_VOIX_MAX:
            return quarantaine(a.id, qa, f"rendu en échec {n} fois : {e}")
        print(f"rendu interrompu ({e}) : les chapitres finis sont conservés, à reprendre")
        return 3
    shutil.rmtree(out_dir / "parts", ignore_errors=True)
    (out_dir / ".props.json").unlink(missing_ok=True)

    # 4. contrôle qualité
    dur = L.duree(final)
    f = L.mesure(final)
    qa.update({
        "duree_s": round(dur, 1), "lufs": float(f["input_i"]), "pic_dbtp": float(f["input_tp"]),
        "chapitres": [{"n": c["n"], "titre": c["titre"], "debut_s": c["borne_s"], "fin_s": c["borne_fin_s"], "duree_s": c["duree_s"]} for c in chaps],
        "rendu_s": round(time.time() - t_rendu), "calcul_total_s": round(time.time() - t0) + voix_s,
    })
    if not a.souple:
        if not DUREE_MIN_S <= dur <= DUREE_MAX_S:
            qa["problemes"].append(f"durée {dur / 60:.1f} min hors de {DUREE_MIN_S // 60}-{DUREE_MAX_S // 60} min")
        elif not DUREE_CIBLE_S[0] <= dur <= DUREE_CIBLE_S[1]:
            qa["alertes"].append(f"durée {dur / 60:.1f} min hors de la cible 7-13 min")
    if not -15.5 <= qa["lufs"] <= -12.5:
        qa["problemes"].append(f"volume {qa['lufs']} LUFS hors de -14 ± 1,5")
    if qa["pic_dbtp"] > -0.5:
        qa["problemes"].append(f"pic {qa['pic_dbtp']} dBTP : risque d'écrêtage")
    qa["publiable"] = not qa["problemes"] and not qa["alertes"]
    common.write_json(out_dir / "qa.json", qa)
    print(json.dumps(qa, ensure_ascii=False, indent=1))
    if qa["publiable"]:
        common.set_status(a.id, "controle", None)
        return 0
    common.set_status(a.id, "quarantaine", "; ".join(qa["problemes"] + qa["alertes"])[:300])
    return 2


if __name__ == "__main__":
    sys.exit(main())
