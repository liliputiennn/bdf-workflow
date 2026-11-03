"""Action manuelle sur un épisode (appelée par la web app « Autopilote »).

Usage : python autopilot/episode_action.py <id> relancer|ecarter

- relancer : sort l'épisode de la quarantaine vers le dernier état atteint (d'après ses fichiers), sans rien refaire de plus.
- ecarter  : met l'épisode en quarantaine « écarté à la main » (le stock ne le compte plus ; les autres épisodes continuent).
Seul `status.json` est modifié (écriture atomique de common.set_status). Code retour 0 = fait, 1 = refusé.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ETATS_ACTIFS_PAS_TOUCHES = {"programme", "publie"}


def etat_atteint(ep: str) -> str:
    d = common.ep_dir(ep)
    if (d / "miniature.png").exists() and (common.EXPORTS / ep / f"{ep}.mp4").exists():
        return "pret"
    if (common.EXPORTS / ep / f"{ep}.mp4").exists():
        return "controle"
    return "ecrit"


def main(ep: str, action: str) -> int:
    if not (common.ep_dir(ep) / "episode.json").exists():
        print(f"épisode inconnu : {ep}")
        return 1
    st = common.get_status(ep)
    if st["etat"] in ETATS_ACTIFS_PAS_TOUCHES:
        print(f"{ep} est déjà {st['etat']} : action refusée")
        return 1
    if action == "relancer":
        if st["etat"] != "quarantaine":
            print(f"{ep} n'est pas en quarantaine ({st['etat']}) : rien à relancer")
            return 1
        nouveau = etat_atteint(ep)
        common.set_status(ep, nouveau, None, tentatives=0)
        print(f"{ep} : quarantaine -> {nouveau}")
        return 0
    if action == "ecarter":
        common.set_status(ep, "quarantaine", "écarté à la main (web app)")
        print(f"{ep} : écarté")
        return 0
    print(f"action inconnue : {action}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2]))
