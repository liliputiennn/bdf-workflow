"""Cloud : récupère dans le stock (release GitHub) les vidéos des épisodes à publier, avant publish.py.

Usage : python autopilot/cloud/recuperer.py
Pour chaque épisode `pret` : télécharge exports/<id>/<id>.mp4, qa.json et miniature.png du stock vers exports-b/<id>/ et episodes-b/<id>/.
Écrit autopilot/state/publiables.txt : les identifiants dont la vidéo est bien là (les autres, fabriqués sur le PC, sont laissés tranquilles).
"""
import subprocess, sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import common  # noqa: E402


def get(cle: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(ICI / "stockage.py"), "get", cle, str(dest)], capture_output=True, text=True)
    return r.returncode == 0 and dest.exists()


def main() -> int:
    ok = []
    for ep in common.list_episodes("pret"):
        mp4 = common.EXPORTS / ep / f"{ep}.mp4"
        if not (mp4.exists() or get(f"exports/{ep}/{ep}.mp4", mp4)):
            print(f"[{ep}] vidéo absente du stock : ignorée")
            continue
        get(f"exports/{ep}/qa.json", common.EXPORTS / ep / "qa.json")
        mini = common.ep_dir(ep) / "miniature.png"
        if not mini.exists():
            get(f"exports/{ep}/miniature.png", mini)
        print(f"[{ep}] prête à publier ({mp4.stat().st_size / 1048576:.1f} Mo)")
        ok.append(ep)
    (common.STATE).mkdir(parents=True, exist_ok=True)
    (common.STATE / "publiables.txt").write_text(",".join(ok), encoding="utf-8")
    print(f"{len(ok)} épisode(s) à publier")
    return 0


if __name__ == "__main__":
    sys.exit(main())
