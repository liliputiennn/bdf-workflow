"""Fait tourner la voix d'un épisode sur le GPU gratuit de Kaggle, à la place de voice.py local.

Usage : python autopilot/cloud/kaggle/lancer_voix.py episodes-b/<id> [--episode-file voix-entree.json]
        [--essais 4] [--seuil 0.9] [--budget-s 0] [--timeout-min 150] [--dry-run]

Prérequis (voir ARCHITECTURE.md) : CLI `kaggle` installée, variables KAGGLE_USERNAME et KAGGLE_API_TOKEN (ou ~/.kaggle),
jeux de données privés `bdf-voix-modele`, `bdf-voix-whisper`, `bdf-voix-ref`.
Écrit voice.wav, timings.json, voice_report.json et cache/ dans le dossier de l'épisode, comme voice.py.
Codes de sortie : 0 fait · 3 budget atteint, à relancer · 1 échec · 2 réglage manquant.
"""
import argparse, base64, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ICI = Path(__file__).resolve().parent
AUTOPILOT = ICI.parent.parent
JEUX = ["bdf-voix-modele", "bdf-voix-whisper", "bdf-voix-ref"]
SLUG = os.environ.get("BDF_KERNEL_SLUG", "bdf-voix")  # un autre nom permet de lancer un test sans gêner la fabrication


def construire_kernel(dossier: Path, entree: bytes, options: dict, utilisateur: str, gpu: bool = True) -> Path:
    """Écrit script.py (modèle + texte de l'épisode + voice.py intégrés) et kernel-metadata.json dans `dossier`."""
    texte = (ICI / "kernel_template.py").read_text(encoding="utf-8")
    voice = base64.b64encode((AUTOPILOT / "voice.py").read_bytes()).decode()
    texte = texte.replace("__INPUT_B64__", base64.b64encode(entree).decode()).replace("__VOICE_B64__", voice).replace(
        "__OPTIONS_B64__", base64.b64encode(json.dumps(options).encode()).decode())
    (dossier / "script.py").write_text(texte, encoding="utf-8")
    meta = {
        "id": f"{utilisateur}/{SLUG}", "title": SLUG, "code_file": "script.py", "language": "python", "kernel_type": "script",
        "is_private": True, "enable_gpu": gpu, "enable_tpu": False, "enable_internet": True,
        "dataset_sources": [f"{utilisateur}/{j}" for j in JEUX], "competition_sources": [], "kernel_sources": [],
    }
    (dossier / "kernel-metadata.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return dossier


def _env_kaggle() -> dict:
    """Ajoute le dossier Scripts de pip --user au PATH (Windows : `kaggle.exe` n'y est pas par défaut)."""
    import site
    scripts = os.path.join(os.path.dirname(site.getusersitepackages()), "Scripts")
    return {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + scripts, "PYTHONIOENCODING": "utf-8"}


def kaggle(*args, **kw) -> subprocess.CompletedProcess:
    env = _env_kaggle()
    # Windows cherche l'exécutable dans le PATH du processus parent, pas dans `env` : on donne le chemin complet
    exe = shutil.which("kaggle", path=env["PATH"]) or shutil.which("kaggle.exe", path=env["PATH"])
    if not exe:
        raise SystemExit("outil `kaggle` introuvable : pip install kaggle six")
    return subprocess.run([exe, *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def attendre(kernel_id: str, timeout_s: int) -> str:
    """Interroge le statut toutes les 60 s ; renvoie complete / error / cancelled / timeout."""
    fin = time.time() + timeout_s
    dernier = ""
    while time.time() < fin:
        s = kaggle("kernels", "status", kernel_id).stdout.lower()
        etat = next((e for e in ("complete", "error", "cancel", "running", "queued") if e in s), "?")
        if etat != dernier:
            print(f"[kaggle] {etat} ({int((time.time() - (fin - timeout_s)) // 60)} min)", flush=True)
            dernier = etat
        if etat in ("complete", "error", "cancel"):
            return etat
        time.sleep(60)
    return "timeout"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--episode-file", default="episode.json")
    ap.add_argument("--essais", type=int, default=4)
    ap.add_argument("--seuil", type=float, default=0.9)
    ap.add_argument("--budget-s", type=float, default=0.0)
    ap.add_argument("--timeout-min", type=int, default=150)
    ap.add_argument("--modele-hf", default=os.environ.get("BDF_MODELE_HF", "Qwen/Qwen3-TTS-12Hz-1.7B-Base"), help="identifiant Hugging Face d'un autre modèle (ex. Qwen/Qwen3-TTS-12Hz-1.7B-Base), téléchargé dans le kernel")
    ap.add_argument("--vitesse", type=float, default=1.10, help="accélération de la voix finale (1.0 = vitesse d'origine)")
    ap.add_argument("--dry-run", action="store_true", help="prépare le kernel dans un dossier temporaire et s'arrête")
    a = ap.parse_args()
    ep = Path(a.episode_dir).resolve()
    utilisateur = os.environ.get("KAGGLE_USERNAME", "")
    if not utilisateur:
        print("KAGGLE_USERNAME manquant")
        return 2
    entree = (ep / a.episode_file).read_bytes()
    options = {"essais": a.essais, "seuil": a.seuil, "budget_s": a.budget_s, "fichier": a.episode_file, "modele_hf": a.modele_hf, "vitesse": a.vitesse}
    with tempfile.TemporaryDirectory(prefix="bdf-kaggle-") as tmp:
        d = construire_kernel(Path(tmp), entree, options, utilisateur)
        if a.dry_run:
            print(f"[dry-run] kernel prêt : {sorted(p.name for p in d.iterdir())}")
            return 0
        r = kaggle("kernels", "push", "-p", str(d), "--accelerator", "NvidiaTeslaT4")
        print(r.stdout.strip(), r.stderr.strip())
        if r.returncode:
            return 1
        kid = f"{utilisateur}/{SLUG}"
        etat = attendre(kid, a.timeout_min * 60)
        sortie = Path(tmp) / "sortie-telechargee"
        kaggle("kernels", "output", kid, "-p", str(sortie), "-o")
        verdict = {}
        if (sortie / "sortie" / "etat.json").exists():
            verdict = json.loads((sortie / "sortie" / "etat.json").read_text(encoding="utf-8"))
        elif (sortie / "etat.json").exists():
            verdict = json.loads((sortie / "etat.json").read_text(encoding="utf-8"))
        base = sortie / "sortie" if (sortie / "sortie").exists() else sortie
        for nom in ("voice.wav", "timings.json", "voice_report.json"):
            if (base / nom).exists():
                shutil.copy(base / nom, ep / nom)
        if (base / "cache").exists():
            shutil.copytree(base / "cache", ep / "cache", dirs_exist_ok=True)
        code = verdict.get("code", 1)
        print(f"[kaggle] fin : état={etat} code={code} : {verdict.get('message', 'pas de verdict')}")
        if code and verdict.get("log"):
            print("[kaggle] fin du journal de voice.py :" + "\n  " + "\n  ".join(verdict["log"][-12:]))
        if etat != "complete" and code == 0:
            code = 1
        return code


if __name__ == "__main__":
    sys.exit(main())
