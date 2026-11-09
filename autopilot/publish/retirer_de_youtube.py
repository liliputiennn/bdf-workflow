"""Retire de la vue publique les vidéos du workflow déjà envoyées, SANS rien supprimer : elles repassent en « privé » et leur mise en ligne programmée est annulée.

    python autopilot/publish/retirer_de_youtube.py --dry-run
    python autopilot/publish/retirer_de_youtube.py

Récupère les identifiants YouTube dans les états des épisodes du PC ET du dépôt cloud (dossier bdf-public), puis marque ces épisodes
en quarantaine (« retiré de YouTube ») pour qu'ils ne soient plus ni programmés ni comptés dans le stock. Rien n'est effacé : fichiers, vidéos et
identifiants restent ; on peut tout remettre en ligne plus tard.
"""
import glob, json, os, sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
import reglages  # noqa: E402
from auth import Jeton  # noqa: E402
from quota import RegistreQuota  # noqa: E402
from youtube import YouTube  # noqa: E402

CLOUD = Path(os.environ.get("BDF_DEPOT_CLOUD", str(Path.home() / "bdf-public")))
CHAMPS = ("privacyStatus", "embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids")  # pas de publishAt : la programmation est annulée
RAISON = "retiré de YouTube le 04/11/2026 (refonte du programme : on ne garde que « gagner de l'argent ») ; vidéo repassée en privé, fichiers conservés"


def collecter() -> dict:
    trouves = {}
    for racine in (common.EPISODES, CLOUD / "episodes-b"):
        for f in glob.glob(str(racine / "*" / "status.json")):
            d = json.load(open(f, encoding="utf-8"))
            vid = (d.get("youtube") or {}).get("video_id")
            if vid:
                trouves.setdefault(vid, []).append(Path(f))
    return trouves


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    liens = collecter()
    print(f"{len(liens)} vidéo(s) YouTube reliées à des épisodes : {', '.join(liens)}")
    cfg = reglages.charger()
    yt = YouTube(Jeton(), cfg, RegistreQuota(cfg))
    for v in yt.lire_videos(list(liens), "status,snippet"):
        st = v["status"]
        print(f"{'[dry-run] ' if dry else ''}{v['id']} : {st.get('privacyStatus')}"
              + (f" programmée {st['publishAt']}" if st.get("publishAt") else "") + f" | {v['snippet']['title'][:60]}")
        if dry:
            continue
        nouveau = {k: st[k] for k in CHAMPS if k in st}
        nouveau["privacyStatus"] = "private"
        nouveau["containsSyntheticMedia"] = False
        yt.mettre_a_jour_statut(v["id"], nouveau)
        for f in liens[v["id"]]:
            d = json.load(open(f, encoding="utf-8"))
            d.update(etat="quarantaine", raison=RAISON)
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
