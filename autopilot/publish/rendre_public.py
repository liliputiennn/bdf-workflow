"""Passe en public les vidéos privées de la chaîne, une fois l'audit YouTube API Services obtenu.

    python autopilot/publish/rendre_public.py --dry-run     # liste ce qui serait fait
    python autopilot/publish/rendre_public.py               # vidéos privées issues des épisodes du workflow
    python autopilot/publish/rendre_public.py --toutes      # TOUTES les vidéos privées de la chaîne (y compris perso)

Par prudence, seules les vidéos reliées à un épisode (`status.json` -> youtube.video_id) sont touchées par défaut.
Les vidéos dont la mise en ligne programmée est encore à venir ne sont pas touchées : elles se publieront seules.
Coût de quota : 50 unités par vidéo passée en public (+ 1 unité par lot de lecture).
Si YouTube garde la vidéo en privé malgré la demande, le projet n'est pas encore audité : le script le dit.
"""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
import horaire  # noqa: E402
import reglages  # noqa: E402
from auth import Jeton, noter_etat_auth  # noqa: E402
from erreurs import ErreurAuth, ErreurContenu, ErreurPublication, ErreurQuota, ErreurReseau  # noqa: E402
from quota import RegistreQuota, maintenant_utc  # noqa: E402
from youtube import YouTube  # noqa: E402

CHAMPS_STATUT = ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids", "containsSyntheticMedia")


def episodes_par_video() -> dict[str, str]:
    return {yt["video_id"]: ep for ep in common.list_episodes()
            if (yt := common.get_status(ep).get("youtube") or {}).get("video_id")}


def rendre_public(yt: YouTube, cfg: dict, toutes: bool = False, dry_run: bool = False, maintenant=maintenant_utc,
                  afficher=print) -> dict:
    liens = episodes_par_video()
    ids = yt.lister_envois_chaine()
    bilan = {"publiees": [], "toujours_privees": [], "ignorees": [], "reportees": []}
    for video in yt.lire_videos(ids, "status"):
        vid, st = video["id"], video.get("status", {})
        if st.get("privacyStatus") != "private":
            continue
        if not toutes and vid not in liens:
            bilan["ignorees"].append(vid)
            continue
        if st.get("publishAt") and horaire.lire_iso(st["publishAt"]) > maintenant():
            afficher(f"{vid} : mise en ligne programmée le {st['publishAt']}, on n'y touche pas")
            bilan["ignorees"].append(vid)
            continue
        ep = liens.get(vid)
        if dry_run:
            afficher(f"{vid} ({ep or 'hors workflow'}) : passerait en public")
            continue
        nouveau = {k: st[k] for k in CHAMPS_STATUT if k in st}
        nouveau["privacyStatus"] = "public"
        try:
            yt.mettre_a_jour_statut(vid, nouveau)
            apres = yt.lire_videos([vid], "status")
        except ErreurQuota as e:
            afficher(f"quota insuffisant, reprise demain ({e})")
            bilan["reportees"].append(vid)
            break
        except ErreurContenu as e:
            afficher(f"{vid} : refusé par YouTube ({e})")
            bilan["toujours_privees"].append(vid)
            continue
        if apres and apres[0].get("status", {}).get("privacyStatus") == "public":
            afficher(f"{vid} ({ep or 'hors workflow'}) : maintenant public")
            bilan["publiees"].append(vid)
            if ep:
                with common.episode_lock(ep):
                    yt_st = dict(common.get_status(ep).get("youtube") or {})
                    yt_st.update(visibilite="public")
                    common.set_status(ep, "publie", None, youtube=yt_st)
        else:
            afficher(f"{vid} : YouTube le garde en privé -> l'audit API n'est pas encore accordé")
            bilan["toujours_privees"].append(vid)
    if bilan["publiees"]:
        chemin = common.STATE / "youtube_audit.json"
        audit = common.read_json(chemin, None) or {"constats": []}
        audit.update(etat="audite", maj=common.now(), explication="Des vidéos ont pu passer en public : l'audit est accordé.")
        common.write_json(chemin, audit)
    return bilan


def main(argv: list[str]) -> int:
    cfg = reglages.charger()
    yt = YouTube(Jeton(), cfg, RegistreQuota(cfg))
    try:
        bilan = rendre_public(yt, cfg, toutes="--toutes" in argv, dry_run="--dry-run" in argv)
    except ErreurAuth as e:
        noter_etat_auth("a_refaire", str(e))
        print(f"AUTHENTIFICATION À REFAIRE : {e}", file=sys.stderr)
        return 3
    except (ErreurReseau, ErreurPublication) as e:
        print(f"ÉCHEC : {e}", file=sys.stderr)
        return 1
    print({k: len(v) for k, v in bilan.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
