"""Retire le badge « contenu modifié ou synthétique » de YouTube sur les vidéos déjà envoyées par le workflow (publiées ou programmées).

    python autopilot/publish/retirer_badge_ia.py --dry-run     # liste ce qui serait changé
    python autopilot/publish/retirer_badge_ia.py               # applique (50 unités de quota par vidéo)
    python autopilot/publish/retirer_badge_ia.py --forcer      # écrit « pas de badge » même si l'API ne renvoie pas le champ

Seules les vidéos reliées à un épisode (status.json -> youtube.video_id) sont touchées. Rien d'autre n'est modifié :
visibilité, date de mise en ligne programmée et autres réglages sont renvoyés tels quels.
"""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
import reglages  # noqa: E402
from auth import Jeton  # noqa: E402
from erreurs import ErreurAuth, ErreurContenu, ErreurPublication, ErreurQuota, ErreurReseau  # noqa: E402
from quota import RegistreQuota  # noqa: E402
from youtube import YouTube  # noqa: E402

CHAMPS = ("privacyStatus", "publishAt", "embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids")


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    liens = {yt["video_id"]: ep for ep in common.list_episodes()
             if (yt := common.get_status(ep).get("youtube") or {}).get("video_id")}
    if not liens:
        print("aucune vidéo reliée à un épisode")
        return 0
    cfg = reglages.charger()
    yt = YouTube(Jeton(), cfg, RegistreQuota(cfg))
    faites, deja = [], []
    try:
        for video in yt.lire_videos(list(liens), "status"):
            vid, st = video["id"], video.get("status", {})
            # l'API ne renvoie pas toujours le champ : --forcer l'écrit à False même s'il est absent
            if not st.get("containsSyntheticMedia") and not ("--forcer" in argv and st.get("containsSyntheticMedia") is None):
                deja.append(vid)
                continue
            print(f"{'[dry-run] ' if dry else ''}{liens[vid]} ({vid}) : badge IA retiré, visibilité {st.get('privacyStatus')}"
                  + (f", programmée {st['publishAt']}" if st.get("publishAt") else ""))
            if dry:
                faites.append(vid)
                continue
            nouveau = {k: st[k] for k in CHAMPS if k in st}
            nouveau["containsSyntheticMedia"] = False
            yt.mettre_a_jour_statut(vid, nouveau)
            faites.append(vid)
    except ErreurAuth as e:
        print(f"AUTHENTIFICATION À REFAIRE : {e}", file=sys.stderr)
        return 3
    except ErreurQuota as e:
        print(f"quota insuffisant, reprise demain ({e})")
    except (ErreurReseau, ErreurPublication, ErreurContenu) as e:
        print(f"ÉCHEC : {e}", file=sys.stderr)
        return 1
    print(f"{len(faites)} vidéo(s) {'à modifier' if dry else 'modifiée(s)'}, {len(deja)} sans badge")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
