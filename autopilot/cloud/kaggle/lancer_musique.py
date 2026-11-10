"""Fait générer la chanson (ACE-Step 1.5, MIT) d'un épisode « musique enfants » sur le GPU gratuit de Kaggle.

Usage : python autopilot/cloud/kaggle/lancer_musique.py episodes-b/<id> [--entree chanson-entree.json] [--essais 2] [--timeout-min 90] [--dry-run]
Entrée : <dossier>/chanson-entree.json (écrit par musique_enfants.generer_audio). Sorties : chanson.wav, alignement.json dans le dossier de l'épisode.
Prérequis : CLI `kaggle`, KAGGLE_USERNAME et KAGGLE_API_TOKEN (ou ~/.kaggle) ; aucun jeu de données privé n'est nécessaire (modèles téléchargés par le noyau).
Codes de sortie : 0 fait · 1 échec · 2 réglage manquant.
"""
import argparse, base64, json, os, shutil, sys, tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import lancer_voix as lv  # noqa: E402  (kaggle(), attendre())

FORMATS = ICI.parent.parent / "formats"
SLUG = os.environ.get("BDF_KERNEL_SLUG_MUSIQUE", "bdf-musique-chantee")


def construire_kernel(dossier: Path, entree: bytes, options: dict, utilisateur: str, gpu: bool = True) -> Path:
    texte = (ICI / "kernel_musique.py").read_text(encoding="utf-8")
    texte = (texte.replace("__INPUT_B64__", base64.b64encode(entree).decode()).replace("__OPTIONS_B64__", base64.b64encode(json.dumps(options).encode()).decode())
             .replace("__ALIGN_B64__", base64.b64encode((FORMATS / "alignement.py").read_bytes()).decode()))
    (dossier / "script.py").write_text(texte, encoding="utf-8")
    meta = {"id": f"{utilisateur}/{SLUG}", "title": SLUG, "code_file": "script.py", "language": "python", "kernel_type": "script", "is_private": True,
            "enable_gpu": gpu, "enable_tpu": False, "enable_internet": True, "dataset_sources": [], "competition_sources": [], "kernel_sources": []}
    (dossier / "kernel-metadata.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return dossier


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--entree", default="chanson-entree.json")
    ap.add_argument("--essais", type=int, default=2)
    ap.add_argument("--timeout-min", type=int, default=90)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ep = Path(a.episode_dir).resolve()
    utilisateur = os.environ.get("KAGGLE_USERNAME", "")
    if not utilisateur and not a.dry_run:
        print("KAGGLE_USERNAME manquant")
        return 2
    entree = (ep / a.entree).read_bytes()
    options = {"essais": a.essais, "whisper": "small", "modele_dit": "acestep-v15-turbo"}
    with tempfile.TemporaryDirectory(prefix="bdf-kaggle-mus-") as tmp:
        d = construire_kernel(Path(tmp), entree, options, utilisateur or "essai")
        if a.dry_run:
            compile(( d / "script.py").read_text(encoding="utf-8"), "script.py", "exec")  # le script généré doit au moins être du Python valide
            print(f"[dry-run] noyau prêt : {sorted(p.name for p in d.iterdir())}")
            return 0
        r = lv.kaggle("kernels", "push", "-p", str(d), "--accelerator", "NvidiaTeslaT4")
        print(r.stdout.strip(), r.stderr.strip())
        if r.returncode:
            return 1
        kid = f"{utilisateur}/{SLUG}"
        etat = lv.attendre(kid, a.timeout_min * 60)
        sortie = Path(tmp) / "sortie-telechargee"
        lv.kaggle("kernels", "output", kid, "-p", str(sortie), "-o")
        base = sortie / "sortie" if (sortie / "sortie").exists() else sortie
        verdict = json.loads((base / "etat.json").read_text(encoding="utf-8")) if (base / "etat.json").exists() else {}
        for nom in ("chanson.wav", "alignement.json"):
            if (base / nom).exists():
                shutil.copy(base / nom, ep / nom)
        code = verdict.get("code", 1)
        print(f"[kaggle] fin : état={etat} code={code} : {verdict.get('message', 'pas de verdict')}")
        if etat != "complete" and code == 0:
            code = 1
        return code


if __name__ == "__main__":
    sys.exit(main())
