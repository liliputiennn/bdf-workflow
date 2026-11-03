"""Bascule vers le cloud : transfère l'état des épisodes du PC vers le dépôt cloud public et leurs vidéos prêtes vers le stock.

Usage : python autopilot/cloud/basculer.py [--dry-run]
Règles (protection contre les doublons YouTube) :
  - épisode absent du cloud : ses fichiers texte et son état sont copiés (jamais d'audio, de vidéo ni de cache) ;
  - épisode déjà dans le cloud mais `programme` ou `publie` sur le PC : l'état du PC (avec l'identifiant YouTube) écrase celui du cloud,
    pour que le cloud ne republie jamais une vidéo déjà envoyée ;
  - sinon l'état du cloud fait foi ;
  - Shorts dérivés d'un long (`origine.json`) à l'état `ecrit` : ignorés, le cloud les recrée en fabriquant le long ;
  - vidéos `controle`/`pret` du PC : envoyées dans le stock si elles n'y sont pas.
Nécessite `gh` connecté et GH_REPO (par défaut liliputiennn/bdf-workflow).
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import common  # noqa: E402

DEST = Path(os.environ.get("BDF_DEPOT_CLOUD", r"C:\Users\ESSAI\bdf-public"))
os.environ.setdefault("GH_REPO", "liliputiennn/bdf-workflow")
EXCLUS = {".wav", ".mp3", ".mp4", ".lock", ".log", ".err"}


def copier_texte(src: Path, dst: Path, dry: bool) -> int:
    n = 0
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() not in EXCLUS:
            n += 1
            if not dry:
                dst.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, dst / f.name)
    return n


def stock_assets() -> set:
    r = subprocess.run([sys.executable, str(ICI / "stockage.py"), "ls"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {l.split("\t")[0] for l in r.stdout.splitlines() if l.strip()}


def put(f: Path, cle: str, dry: bool) -> None:
    print(("  [dry-run] " if dry else "  ") + f"stock <- {cle} ({f.stat().st_size / 1048576:.1f} Mo)")
    if not dry:
        subprocess.run([sys.executable, str(ICI / "stockage.py"), "put", str(f), cle], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not (DEST / ".git").exists():
        print(f"dépôt cloud introuvable : {DEST}")
        return 2
    assets = stock_assets()
    nouveaux, ecrases, videos = [], [], 0
    for d in sorted(common.EPISODES.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name.startswith("apercu-") or not (d / "episode.json").exists():
            continue
        ep, st = d.name, common.get_status(d.name)
        etat, cible = st["etat"], DEST / "episodes-b" / d.name
        if (d / "origine.json").exists() and etat == "ecrit":
            continue
        if not cible.exists():
            copier_texte(d, cible, a.dry_run)
            if not a.dry_run:
                common.write_json(cible / "status.json", st)
            nouveaux.append(f"{ep} ({etat})")
        elif etat in ("programme", "publie"):
            if not a.dry_run:
                common.write_json(cible / "status.json", st)
            ecrases.append(f"{ep} ({etat})")
        if etat in ("controle", "pret"):
            mp4 = common.EXPORTS / ep / f"{ep}.mp4"
            if mp4.exists() and f"exports__{ep}__{ep}.mp4" not in assets:
                put(mp4, f"exports/{ep}/{ep}.mp4", a.dry_run)
                videos += 1
                qa = common.EXPORTS / ep / "qa.json"
                if qa.exists():
                    put(qa, f"exports/{ep}/qa.json", a.dry_run)
                mini = d / "miniature.png"
                if mini.exists() and f"exports__{ep}__miniature.png" not in assets:
                    put(mini, f"exports/{ep}/miniature.png", a.dry_run)
    print(f"épisodes ajoutés au cloud : {len(nouveaux)}", *[f"\n  + {x}" for x in nouveaux])
    print(f"états PC recopiés (anti-doublon) : {len(ecrases)}", *[f"\n  = {x}" for x in ecrases])
    print(f"vidéos envoyées dans le stock : {videos}")
    if not a.dry_run and (nouveaux or ecrases):
        run = lambda *c: subprocess.run(["git", "-C", str(DEST), *c], check=True)
        run("add", "-A", "episodes-b")
        run("-c", "user.name=Azur", "-c", "user.email=noreply@users.noreply.github.com", "commit", "-q", "-m", "Bascule : état des épisodes du PC")
        run("pull", "--rebase", "-q", "origin", "main")
        run("push", "-q", "origin", "main")
        print("dépôt cloud à jour")
    return 0


if __name__ == "__main__":
    sys.exit(main())
