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

FICHIERS = ["youtube_quota.json", "youtube_auth.json", "youtube_audit.json", "tiktok.json", "chaines_youtube.json", "jetons.json"]  # + youtube_auth-<chaine>.json (une par chaîne)
DEPOT = common.ROOT / "etat-cloud"


EXCLUS = common.ROOT / "autopilot" / "tiktok" / "exclus.json"  # suivi par Git : vidéos TikTok gérées à la main, jamais renvoyées


def fusionner_exclus_tiktok(etat_dir: Path = None, exclus: Path = None) -> int:
    """Ajoute à l'état TikTok les vidéos exclues à la main (sans écraser une entrée existante). Retourne le nombre d'ajouts."""
    import json
    etat_dir, exclus = etat_dir or common.STATE, exclus or EXCLUS
    if not exclus.exists():
        return 0
    voulu = (json.loads(exclus.read_text(encoding="utf-8")).get("envoyes") or {})
    f = etat_dir / "tiktok.json"
    etat = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    env = etat.setdefault("envoyes", {})
    n = 0
    for ep, v in voulu.items():
        if ep not in env:
            env[ep] = v
            n += 1
    if n:
        etat_dir.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def main(mode: str) -> int:
    common.STATE.mkdir(parents=True, exist_ok=True)
    src, dst = (DEPOT, common.STATE) if mode == "restore" else (common.STATE, DEPOT)
    dst.mkdir(parents=True, exist_ok=True)
    for f in FICHIERS + sorted(q.name for q in src.glob("youtube_auth-*.json")):
        if (src / f).exists():
            shutil.copy(src / f, dst / f)
            print(f"{mode} : {f}")
    if mode == "restore":
        n = fusionner_exclus_tiktok()
        print(f"restore : {n} exclusion(s) TikTok ajoutée(s)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("restore", "save"):
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
