"""Archive l'ancien stock (ancienne direction artistique) et supprime ses vidéos, pour repartir de zéro avec la nouvelle.

Usage : python autopilot/cloud/archiver_ancienne_da.py [--dry-run]
- les 6 épisodes déjà envoyés sur YouTube (repassés en privé) RESTENT en place, avec leurs vidéos ;
- tous les autres épisodes (stock, brouillons déjà fabriqués) : leurs textes sont déplacés dans episodes-b/_archives/ancienne-da-20261104/
  (récupérables), leurs vidéos et miniatures dans exports-b/ sont SUPPRIMÉES ;
- dépôt cloud : ces épisodes sont retirés (git rm) et leurs fichiers du stock (release) supprimés.
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import common  # noqa: E402

CLOUD = Path(os.environ.get("BDF_DEPOT_CLOUD", str(Path.home() / "bdf-public")))
ARCHIVE = common.EPISODES / "_archives" / "ancienne-da-20261104"
os.environ.setdefault("GH_REPO", "liliputiennn/bdf-workflow")


def sur_youtube(ep: str) -> bool:
    """Vrai si l'épisode a une vidéo YouTube, d'après l'état du PC OU celui du cloud (les envois récents n'existent que dans le cloud)."""
    if (common.get_status(ep).get("youtube") or {}).get("video_id"):
        return True
    f = CLOUD / "episodes-b" / ep / "status.json"
    try:
        return bool((json.loads(f.read_text(encoding="utf-8")).get("youtube") or {}).get("video_id"))
    except (OSError, ValueError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    garder = [e for e in common.list_episodes() if sur_youtube(e)]
    archiver = [e for e in common.list_episodes() if e not in garder and not e.startswith("apercu-")]
    octets = sum(f.stat().st_size for e in archiver for f in (common.EXPORTS / e).rglob("*") if f.is_file()) if (common.EXPORTS).exists() else 0
    print(f"à garder (sur YouTube, en privé) : {len(garder)} | à archiver : {len(archiver)} | vidéos supprimées : {octets / 1e9:.2f} Go")
    if a.dry_run:
        return 0
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for e in archiver:
        src = common.ep_dir(e)
        if src.exists():
            shutil.move(str(src), str(ARCHIVE / e))
        shutil.rmtree(common.EXPORTS / e, ignore_errors=True)
    # dépôt cloud
    if (CLOUD / ".git").exists():
        for e in archiver:
            subprocess.run(["git", "-C", str(CLOUD), "rm", "-r", "-q", "--ignore-unmatch", f"episodes-b/{e}"], check=False)
            shutil.rmtree(CLOUD / "episodes-b" / e, ignore_errors=True)
        subprocess.run(["git", "-C", str(CLOUD), "-c", "user.name=Azur", "-c", "user.email=noreply@users.noreply.github.com", "commit", "-q", "-m",
                        "Ancienne direction artistique archivée : épisodes retirés du cloud"], check=False)
        subprocess.run(["git", "-C", str(CLOUD), "pull", "--rebase", "-q", "origin", "main"], check=False)
        subprocess.run(["git", "-C", str(CLOUD), "push", "-q", "origin", "main"], check=False)
    # stock (release)
    r = subprocess.run([sys.executable, str(ICI / "stockage.py"), "ls", "exports"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    noms = [l.split("\t")[0] for l in r.stdout.splitlines() if l.strip()]
    n = 0
    for nom in noms:
        if any(nom.startswith("exports__" + e + "__") for e in archiver):
            subprocess.run(["gh", "release", "delete-asset", "stock", nom, "--yes", "--repo", os.environ["GH_REPO"]], check=False, capture_output=True)
            n += 1
    print(f"archivés : {len(archiver)} épisodes ; fichiers supprimés du stock : {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
