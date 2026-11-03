"""Cloud : les états de la publication (quota YouTube, connexion…) doivent survivre d'une exécution à l'autre.

Usage : python autopilot/cloud/etat_cloud.py restore   (dépôt -> autopilot/state/)
        python autopilot/cloud/etat_cloud.py save      (autopilot/state/ -> dépôt, dossier etat-cloud/)
Fichiers suivis : youtube_quota.json, youtube_auth.json, youtube_audit.json, tiktok.json (jamais de secrets : ce sont des compteurs et des statuts).
"""
import shutil, sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import common  # noqa: E402

FICHIERS = ["youtube_quota.json", "youtube_auth.json", "youtube_audit.json", "tiktok.json"]
DEPOT = common.ROOT / "etat-cloud"


def main(mode: str) -> int:
    common.STATE.mkdir(parents=True, exist_ok=True)
    src, dst = (DEPOT, common.STATE) if mode == "restore" else (common.STATE, DEPOT)
    dst.mkdir(parents=True, exist_ok=True)
    for f in FICHIERS:
        if (src / f).exists():
            shutil.copy(src / f, dst / f)
            print(f"{mode} : {f}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("restore", "save"):
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
