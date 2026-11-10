"""Fabrique des formats maison (quiz, leçons de langue, sommeil, chansons) : voix -> rendu léger -> mixage -> contrôle qualité.

Usage :  python autopilot/formats/fabrique.py <id> [--sans-voix] [--voix-prete] [--essais 4]
Remplace `make_short.py` pour les chaînes dont le profil déclare `briques.fabrique` (même contrat que lui) :
  entrée   episodes-b/<id>/episode.json
  sortie   exports-b/<id>/<id>.mp4 + qa.json ; état « controle » ; code 0 = publiable, 2 = quarantaine (raison dans qa.json)
Le module de format du profil fournit : `script_voix(ep)` ({"phrases": [...], "pauses": {...}, "langues": {...}} ; phrases vides = pas de voix),
`rendre(ep, ep_dir, out_dir, profil, qa)` -> chemin du mp4, et les constantes `LUFS` et `DUREE_S` ({"short": (min, max), "long": (min, max)}).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from autopilot import chaines, common  # noqa: E402

VENV_PY = r"C:\VoiceStudio\tts-direct\venv\Scripts\python.exe"


def sha(o) -> str:
    return hashlib.sha1(json.dumps(o, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def voix(ep_id: str, ep_dir: Path, script: dict, essais: int, seuil: float | None = None) -> None:
    entree = {"phrases": script["phrases"], "pauses": script.get("pauses") or {}, "vitesses": script.get("vitesses") or {}, "langues": script.get("langues") or {}}
    marque = ep_dir / "voix.sha"
    cle = sha([entree, os.environ.get("BDF_LOCUTEUR", ""), os.environ.get("BDF_STYLE", ""), os.environ.get("BDF_REF_WAV", "")])
    if (ep_dir / "voice.wav").exists() and (ep_dir / "timings.json").exists() and marque.exists() and marque.read_text().strip() == cle:
        return
    common.write_json(ep_dir / "voix-entree.json", entree)
    cmd = [VENV_PY, str(RACINE / "autopilot" / "voice.py")]
    if os.environ.get("BDF_VOIX") == "kaggle":
        cmd = [sys.executable, str(RACINE / "autopilot" / "cloud" / "kaggle" / "lancer_voix.py")]
    cmd += [str(ep_dir), "--episode-file", "voix-entree.json", "--essais", str(essais)]
    if seuil is not None:  # seuil de relecture propre au format (voix lente et chuchotée : la reconnaissance se trompe plus, ex. « Ses » entendu « Les »)
        cmd += ["--seuil", str(seuil)]
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"}
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)
    marque.write_text(cle, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--essais", type=int, default=4)
    ap.add_argument("--sans-voix", action="store_true")
    ap.add_argument("--voix-prete", action="store_true")
    a = ap.parse_args(argv)
    ep_dir, out_dir = common.ep_dir(a.id), common.EXPORTS / a.id
    out_dir.mkdir(parents=True, exist_ok=True)
    qa = {"id": a.id, "problemes": [], "alertes": []}
    t0 = time.time()
    profil = chaines.profil(common.chaine_de(a.id)) or chaines.defaut_fr()
    module = chaines.charger_format(profil)
    ep = common.read_json(ep_dir / "episode.json", None)
    if module is None or not isinstance(ep, dict) or not hasattr(module, "rendre"):
        qa["problemes"].append("module de format ou episode.json introuvable")
        common.write_json(out_dir / "qa.json", qa)
        print("Épisode invalide :", *qa["problemes"], sep="\n - ")
        return 2
    script = module.script_voix(ep) if hasattr(module, "script_voix") else {"phrases": []}
    if script["phrases"]:
        if a.sans_voix or a.voix_prete:
            manque = [f for f in ("voice.wav", "timings.json") if not (ep_dir / f).exists()]
            if manque:
                qa["problemes"].append("voix annoncée prête mais absente : " + ", ".join(manque))
                common.write_json(out_dir / "qa.json", qa)
                print("Épisode invalide :", *qa["problemes"], sep="\n - ")
                return 2
        else:
            voix(a.id, ep_dir, script, a.essais, getattr(module, "SEUIL_VOIX", None))
        rep = common.read_json(ep_dir / "voice_report.json", {"a_relire": []}) or {"a_relire": []}
        for r in rep.get("a_relire", []):
            qa["alertes"].append(f"phrase {r['phrase']} : lecture douteuse (score {r['score']}) : entendu « {r['entendu']} »")
    if hasattr(module, "generer_audio"):  # format à chant généré (musique enfants) : ACE-Step sur Kaggle, ou fichiers déjà là avec --sans-voix
        try:
            module.generer_audio(ep, ep_dir, sans_cloud=a.sans_voix or a.voix_prete)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            qa["problemes"].append(f"chanson non générée : {e}")
            common.write_json(out_dir / "qa.json", qa)
            print("Épisode invalide :", *qa["problemes"], sep=chr(10) + " - ")
            return 2
    video = "long" if ep.get("video") == "long" else "short"
    final = module.rendre(ep, ep_dir, out_dir, profil, qa)
    bornes = getattr(module, "DUREE_S", {}).get(video)
    cible = getattr(module, "LUFS", -14.0)
    if bornes and not bornes[0] <= qa["duree_s"] <= bornes[1]:
        qa["problemes"].append(f"durée {qa['duree_s']:.0f} s hors de {bornes[0]}-{bornes[1]} s")
    if not cible - 1.5 <= qa["lufs"] <= cible + 1.5:
        qa["problemes"].append(f"volume {qa['lufs']} LUFS hors de {cible} ± 1,5")
    if qa["pic_dbtp"] > -0.5:
        qa["problemes"].append(f"pic {qa['pic_dbtp']} dBTP : risque d'écrêtage")
    qa["calcul_total_s"] = round(time.time() - t0)
    qa["publiable"] = not qa["problemes"] and not qa["alertes"] and Path(final).exists()
    common.write_json(out_dir / "qa.json", qa)
    print(json.dumps(qa, ensure_ascii=False, indent=1))
    if qa["publiable"]:
        common.set_status(a.id, "controle", None)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
