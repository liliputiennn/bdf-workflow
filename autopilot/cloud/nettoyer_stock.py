"""Cloud : supprime du stock les vidéos déjà publiées (pour rester petit), après quelques jours de marge.

Usage : python autopilot/cloud/nettoyer_stock.py [--jours 2] [--dry-run]
"""
import argparse, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import common  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    limite = datetime.now(timezone.utc) - timedelta(days=a.jours)
    n = 0
    for ep in common.list_episodes("publie"):
        t = (common.get_status(ep).get("youtube") or {}).get("publie_a") or common.get_status(ep).get("maj")
        try:
            quand = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
            if quand.tzinfo is None:
                quand = quand.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if quand > limite:
            continue
        cmd = [sys.executable, str(ICI / "stockage.py"), "purge", f"exports/{ep}/", "--jours", "0"] + (["--dry-run"] if a.dry_run else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        if "0 objet" not in r.stdout:
            print(f"[{ep}] " + r.stdout.strip().splitlines()[0] if r.stdout.strip() else f"[{ep}] rien")
            n += 1
    print(f"{n} épisode(s) nettoyé(s) du stock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
