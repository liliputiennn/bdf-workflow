"""Publieur YouTube : `pret` -> `programme` -> `publie` (voir autopilot/CONTRAT.md).

    python autopilot/publish/publish.py <id> [--dry-run]
    python autopilot/publish/publish.py --en-attente [--dry-run]
    python autopilot/publish/publish.py --exemple <id>      # crée un publication.json d'exemple s'il n'existe pas

Codes de sortie : 0 tout va bien (y compris « reporté pour cause de quota »), 1 au moins un épisode en
quarantaine ou un échec de validation, 3 authentification à refaire (rien n'est mis en quarantaine).
La dernière ligne imprimée est un résumé JSON pour l'orchestrateur.
"""
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
import horaire  # noqa: E402
import reglages  # noqa: E402
from auth import Jeton, noter_etat_auth  # noqa: E402
from erreurs import ErreurAuth, ErreurContenu, ErreurQuota, ErreurReseau  # noqa: E402
from quota import RegistreQuota, maintenant_utc  # noqa: E402
from youtube import YouTube, construire_ressource  # noqa: E402

ANGLES = ("<", ">")


# --- fichiers de l'épisode -------------------------------------------------------------------------------

def chemin_video(ep_id: str) -> Path:
    return common.EXPORTS / ep_id / f"{ep_id}.mp4"


def chemin_miniature(ep_id: str) -> Path | None:
    """La miniature faite à la main a priorité sur l'automatique."""
    for ext in (".png", ".jpg", ".jpeg"):
        p = common.ROOT / "miniatures-manuelles" / f"{ep_id}{ext}"
        if p.exists():
            return p
    p = common.ep_dir(ep_id) / "miniature.png"
    return p if p.exists() else None


def dimensions_png(p: Path) -> tuple[int, int] | None:
    with open(p, "rb") as f:
        tete = f.read(24)
    if tete[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", tete[16:24])


def valider(ep_id: str, cfg: dict) -> tuple[list[str], list[str], dict | None]:
    """Contrôles sans réseau. Retourne (problèmes bloquants, avertissements, publication.json)."""
    pb, av = [], []
    video = chemin_video(ep_id)
    if not video.exists():
        pb.append(f"vidéo absente : {video}")
    elif video.stat().st_size == 0:
        pb.append("vidéo vide")
    mini = chemin_miniature(ep_id)
    if mini is None:
        pb.append("miniature absente (miniature.png ou miniatures-manuelles/<id>.png)")
    else:
        taille = mini.stat().st_size
        if taille > cfg["miniature_max_octets"]:
            pb.append(f"miniature trop lourde : {taille} octets (maximum {cfg['miniature_max_octets']})")
        if mini.suffix.lower() == ".png":
            dim = dimensions_png(mini)
            if dim is None:
                pb.append("miniature : ce n'est pas un vrai PNG")
            elif dim != (1280, 720):
                av.append(f"miniature en {dim[0]}x{dim[1]} au lieu de 1280x720")
    pub = common.read_json(common.ep_dir(ep_id) / "publication.json", None)
    if not isinstance(pub, dict):
        pb.append("publication.json absent ou illisible")
        return pb, av, None
    if pub.get("_exemple"):
        pb.append("publication.json est un exemple (champ _exemple) : le rédacteur doit l'écrire")
    titre = pub.get("titre")
    if not isinstance(titre, str) or not titre.strip():
        pb.append("titre manquant")
    elif len(titre) > cfg["titre_max"]:
        pb.append(f"titre trop long : {len(titre)} caractères (maximum {cfg['titre_max']})")
    desc = pub.get("description")
    if not isinstance(desc, str) or not desc.strip():
        pb.append("description manquante")
    elif len(desc.encode("utf-8")) > cfg["description_max_octets"]:
        pb.append(f"description trop longue : {len(desc.encode('utf-8'))} octets (maximum {cfg['description_max_octets']})")
    tags = pub.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) and t.strip() for t in tags):
        pb.append("tags : liste de textes non vides attendue")
    elif sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1) > cfg["tags_max_caracteres"]:
        pb.append(f"tags : plus de {cfg['tags_max_caracteres']} caractères au total")
    elif not tags:
        av.append("aucun tag")
    for nom, valeur in (("titre", titre), ("description", desc), ("tags", " ".join(tags) if isinstance(tags, list) else "")):
        if isinstance(valeur, str) and any(a in valeur for a in ANGLES):
            pb.append(f"{nom} : les signes < et > sont refusés par YouTube")
    if pub.get("langue", "fr") != "fr":
        av.append(f"langue « {pub.get('langue')} » (attendu fr)")
    if not isinstance(pub.get("contenu_ia", False), bool):
        pb.append("contenu_ia doit être true ou false")
    return pb, av, pub


def _horodatage(s: float) -> str:
    s = int(round(s))
    h, reste = divmod(s, 3600)
    m, sec = divmod(reste, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def chapitres_description(ep_id: str) -> str:
    """Chapitres d'un long au format YouTube (« 00:00 Titre », le premier à 00:00, au moins 3, chacun d'au moins 10 s), ou ''."""
    chaps = common.read_json(common.ep_dir(ep_id) / "chapitres.json", None)
    if not isinstance(chaps, list) or len(chaps) < 3:
        return ""
    lignes = []
    for c in chaps:
        debut = 0.0 if not lignes else float(c.get("borne_s", c.get("debut_s", 0)))
        if lignes and debut - lignes[-1][0] < 10:
            return ""  # YouTube ignore tous les chapitres si l'un dure moins de 10 secondes
        lignes.append((debut, str(c.get("titre", "")).strip()))
    return "Chapitres :\n" + "\n".join(f"{_horodatage(d)} {t}" for d, t in lignes)


def est_long(ep_id: str) -> bool:
    return (common.ep_dir(ep_id) / "episode-long.json").exists()


def description_finale(pub: dict, cfg: dict, ep_id: str | None = None) -> str:
    desc = pub["description"].strip()
    long = bool(ep_id) and est_long(ep_id)
    if long:
        chap = chapitres_description(ep_id)
        if chap and "00:00" not in desc:
            desc += "\n\n" + chap
    q = (pub.get("question_commentaires") or "").strip()
    if cfg["question_dans_description"] and q and q not in desc:
        desc += "\n\n" + q
    ia = "voix de synthèse (ia)"
    if cfg.get("mention_ia_description", True) and pub.get("contenu_ia") and ia not in desc.lower() and "synthèse" not in desc.lower():
        desc += "\n\nVoix de synthèse (IA)."  # le badge YouTube est désactivé : on le dit ici, dans la description
    if cfg["hashtag_shorts"] and not long and "#shorts" not in desc.lower():  # un long 16:9 n'est pas un Short
        desc += "\n\n#Shorts"
    return desc


def creer_exemple(ep_id: str) -> Path:
    """Écrit un publication.json d'exemple, sans jamais écraser l'existant."""
    chemin = common.ep_dir(ep_id) / "publication.json"
    if chemin.exists():
        return chemin
    ep = common.read_json(common.ep_dir(ep_id) / "episode.json", {}) or {}
    titre = (ep.get("titre") or ep_id)[:70]
    phrases = ep.get("phrases") or []
    common.write_json(chemin, {
        "_exemple": True,
        "titre": titre,
        "description": " ".join(phrases[:3]) or f"Un fait expliqué simplement : {titre}.",
        "tags": ["business", "finance", "argent", "économie", "explication"],
        "question_commentaires": "Et toi, tu en pensais quoi avant de voir cette vidéo ?",
        "langue": "fr",
        "contenu_ia": True,
    })
    return chemin


# --- planification ---------------------------------------------------------------------------------------

def jours_pris(cfg: dict) -> set:
    pris = set()
    for ep in common.list_episodes():
        st = common.get_status(ep)
        yt = st.get("youtube") or {}
        if st["etat"] != "quarantaine" and yt.get("video_id") and yt.get("publie_a"):
            pris.add(horaire.vers_local(horaire.lire_iso(st["youtube"]["publie_a"]), cfg["fuseau"]).date())
    return pris


def _maj_youtube(ep_id: str, **champs) -> dict:
    yt = dict(common.get_status(ep_id).get("youtube") or {})
    yt.update(champs)
    return yt


def noter_audit(ep_id: str, video_id: str) -> None:
    """Note que YouTube a verrouillé la vidéo en privé (projet API non audité) dans state/youtube_audit.json."""
    chemin = common.STATE / "youtube_audit.json"
    audit = common.read_json(chemin, None) or {"etat": "non_audite", "constats": []}
    if audit.get("etat") != "audite":
        audit["etat"] = "non_audite"
    if not any(c.get("video_id") == video_id for c in audit["constats"]):
        audit["constats"].append({"episode": ep_id, "video_id": video_id, "date": common.now()})
    audit["maj"] = common.now()
    audit["explication"] = ("YouTube force la visibilité privée des vidéos envoyées par un projet API non audité. "
                            "Demander l'audit (INSTALLATION.md), puis lancer rendre_public.py.")
    common.write_json(chemin, audit)


def deduire_visibilite(video: dict, publie_a_prevu: str, maintenant: datetime) -> str:
    """'public', 'programme' (privé avec date de mise en ligne conservée) ou 'prive_force'."""
    st = video.get("status", {})
    if st.get("privacyStatus") in ("public", "unlisted"):
        return st["privacyStatus"] if st["privacyStatus"] == "public" else "non_repertorie"
    pa = st.get("publishAt")
    if pa and horaire.lire_iso(pa) > maintenant:
        return "programme"
    return "prive_force"


# --- publication d'un épisode ----------------------------------------------------------------------------

def publier(ep_id: str, yt: YouTube, cfg: dict, maintenant=maintenant_utc, afficher=print) -> dict:
    """Publie un épisode `pret`. Retourne {'id', 'resultat', 'detail'} ; ne lève que ErreurAuth."""
    try:
        verrou = common.episode_lock(ep_id)
        verrou.__enter__()
    except TimeoutError:
        return {"id": ep_id, "resultat": "ignore", "detail": "verrou occupé"}
    try:
        st = common.get_status(ep_id)
        if st["etat"] != "pret":
            return {"id": ep_id, "resultat": "ignore", "detail": f"état {st['etat']}"}
        pb, av, pub = valider(ep_id, cfg)
        for a in av:
            afficher(f"  avertissement : {a}")
        if pb:
            raison = "publication impossible : " + " ; ".join(pb)
            common.set_status(ep_id, "quarantaine", raison)
            return {"id": ep_id, "resultat": "quarantaine", "detail": raison}

        memo = common.ep_dir(ep_id) / "youtube_upload.json"
        deja = (st.get("youtube") or {}).get("video_id")
        if not deja:
            u, e = yt.quota.cout_total_publication()
            try:
                yt.quota.verifier(unites=u, envois=e)
            except ErreurQuota as err:
                return {"id": ep_id, "resultat": "reporte", "detail": f"quota : {err} ; nouvel essai après {err.prochain_essai}"}

        try:
            if not deja:
                ancien = (common.read_json(memo, {}) or {}).get("publie_a")
                publie_a = ancien or horaire.iso_utc(horaire.prochain_creneau(
                    cfg["heure_publication"], cfg["fuseau"], maintenant(), jours_pris(cfg), cfg["marge_minimale_minutes"]))
                ressource = construire_ressource({**pub, "description": description_finale(pub, cfg, ep_id)}, cfg, publie_a)
                afficher(f"  envoi de {chemin_video(ep_id).name} (mise en ligne prévue {publie_a})")
                memo_data = common.read_json(memo, {}) or {}
                memo_data["publie_a"] = publie_a
                common.write_json(memo, memo_data)
                video = yt.envoyer_video(chemin_video(ep_id), ressource, memo, afficher)
                deja = video["id"]
                common.set_status(ep_id, "pret", None, youtube=_maj_youtube(
                    ep_id, video_id=deja, url=f"https://youtu.be/{deja}", publie_a=publie_a, visibilite="envoye"))
                memo.unlink(missing_ok=True)
            else:
                publie_a = st["youtube"].get("publie_a")
                afficher(f"  reprise : vidéo {deja} déjà envoyée")

            miniature_ok = (common.get_status(ep_id)["youtube"] or {}).get("miniature")
            if not miniature_ok:
                try:
                    yt.definir_miniature(deja, chemin_miniature(ep_id))
                    common.set_status(ep_id, "pret", None, youtube=_maj_youtube(ep_id, miniature=True))
                except ErreurContenu as err:
                    # la vidéo est bien envoyée : une miniature refusée n'est pas une raison de la perdre
                    afficher(f"  miniature refusée : {err}")
                    common.set_status(ep_id, "pret", None, youtube=_maj_youtube(ep_id, miniature=False, miniature_erreur=str(err)))
                except ErreurAuth as err:
                    if "forbidden" in str(err).lower() or "403" in str(err):
                        afficher(f"  miniature non autorisée (chaîne à vérifier par téléphone ?) : {err}")
                        common.set_status(ep_id, "pret", None, youtube=_maj_youtube(ep_id, miniature=False, miniature_erreur=str(err)))
                    else:
                        raise
            lu = yt.lire_videos([deja], "status")
        except ErreurQuota as err:
            yt.quota.declarer_epuise(str(err))
            return {"id": ep_id, "resultat": "reporte", "detail": f"quota : {err} ; nouvel essai après {yt.quota.prochain_essai()}"}
        except ErreurReseau as err:
            tent = st.get("tentatives", 0) + 1
            if tent >= cfg["tentatives_max_avant_quarantaine"]:
                common.set_status(ep_id, "quarantaine", f"échecs réseau répétés vers YouTube : {err}", tentatives=tent)
                return {"id": ep_id, "resultat": "quarantaine", "detail": str(err)}
            common.set_status(ep_id, "pret", None, tentatives=tent)
            return {"id": ep_id, "resultat": "reseau", "detail": str(err)}
        except ErreurContenu as err:
            common.set_status(ep_id, "quarantaine", f"YouTube refuse la vidéo : {err}")
            return {"id": ep_id, "resultat": "quarantaine", "detail": str(err)}

        if not lu:
            common.set_status(ep_id, "quarantaine", f"vidéo {deja} introuvable à la relecture (rejetée ou supprimée ?)")
            return {"id": ep_id, "resultat": "quarantaine", "detail": "relecture vide"}
        statut = lu[0].get("status", {})
        if statut.get("uploadStatus") in ("rejected", "failed", "deleted"):
            motif = statut.get("rejectionReason") or statut.get("failureReason") or statut["uploadStatus"]
            common.set_status(ep_id, "quarantaine", f"YouTube a rejeté la vidéo {deja} : {motif}")
            return {"id": ep_id, "resultat": "quarantaine", "detail": motif}

        visibilite = deduire_visibilite(lu[0], publie_a, maintenant())
        if visibilite == "prive_force":
            noter_audit(ep_id, deja)
            afficher("  YouTube a forcé la visibilité en privé (projet API non audité) : vidéo envoyée, audit à demander.")
        yt_etat = _maj_youtube(ep_id, visibilite=visibilite)
        if visibilite == "public":
            common.set_status(ep_id, "publie", None, youtube=yt_etat, tentatives=0)
            return {"id": ep_id, "resultat": "publie", "detail": yt_etat["url"]}
        common.set_status(ep_id, "programme", None, youtube=yt_etat, tentatives=0)
        return {"id": ep_id, "resultat": "programme", "detail": f"{yt_etat['url']} ({visibilite}, {yt_etat.get('publie_a')})"}
    finally:
        verrou.__exit__(None, None, None)


def synchroniser(yt: YouTube, cfg: dict, maintenant=maintenant_utc, afficher=print) -> list[dict]:
    """Fait passer `programme` -> `publie` quand la vidéo est devenue publique (1 unité de quota par vidéo échue)."""
    sortie = []
    for ep_id in common.list_episodes("programme"):
        yt_st = common.get_status(ep_id).get("youtube") or {}
        if not yt_st.get("video_id") or not yt_st.get("publie_a"):
            continue
        if horaire.lire_iso(yt_st["publie_a"]) > maintenant():
            continue
        try:
            lu = yt.lire_videos([yt_st["video_id"]], "status")
        except ErreurQuota:
            break
        except ErreurReseau:
            continue
        if not lu:
            continue
        vis = deduire_visibilite(lu[0], yt_st["publie_a"], maintenant())
        if vis == "public":
            with common.episode_lock(ep_id):
                common.set_status(ep_id, "publie", None, youtube=_maj_youtube(ep_id, visibilite="public"))
            sortie.append({"id": ep_id, "resultat": "publie", "detail": yt_st.get("url")})
        elif vis == "prive_force":
            noter_audit(ep_id, yt_st["video_id"])
            with common.episode_lock(ep_id):
                common.set_status(ep_id, "programme", None, youtube=_maj_youtube(ep_id, visibilite="prive_force"))
            sortie.append({"id": ep_id, "resultat": "toujours_prive", "detail": "audit YouTube requis"})
    return sortie


# --- ligne de commande ----------------------------------------------------------------------------------

def dry_run(ids: list[str], cfg: dict) -> int:
    code = 0
    pris = jours_pris(cfg)
    for ep_id in ids:
        print(f"[{ep_id}] état : {common.get_status(ep_id)['etat']}")
        pb, av, pub = valider(ep_id, cfg)
        for a in av:
            print(f"  avertissement : {a}")
        for p in pb:
            print(f"  PROBLÈME : {p}")
        if pub and not pb:
            creneau = horaire.prochain_creneau(cfg["heure_publication"], cfg["fuseau"], maintenant_utc(), pris, cfg["marge_minimale_minutes"])
            pris.add(horaire.vers_local(creneau, cfg["fuseau"]).date())
            print(f"  titre ({len(pub['titre'])} car.) : {pub['titre']}")
            print(f"  {len(pub.get('tags', []))} tags, contenu_ia={pub.get('contenu_ia', False)}, miniature : {chemin_miniature(ep_id)}")
            print(f"  mise en ligne prévue : {horaire.iso_utc(creneau)} (privé jusque-là)")
            print("  OK : prêt à publier")
        code = code or (1 if pb else 0)
    return code


def main(argv: list[str]) -> int:
    cfg = reglages.charger()
    seul_exemple = "--exemple" in argv
    dry = "--dry-run" in argv
    ids = [a for a in argv if not a.startswith("--")]
    if seul_exemple:
        for ep_id in ids:
            print(f"{creer_exemple(ep_id)}")
        return 0
    if "--en-attente" in argv:
        ids = common.list_episodes("pret")
        # cloud : seuls les épisodes dont la vidéo a été récupérée dans le stock (liste séparée par des virgules, « - » = aucun)
        seulement = os.environ.get("BDF_PUBLIER_SEULEMENT")
        if seulement is not None:
            ids = [i for i in ids if i in seulement.split(",")]
    elif not ids:
        print(__doc__)
        return 2
    if dry:
        return dry_run(ids, cfg)

    quota = RegistreQuota(cfg)
    yt = YouTube(Jeton(), cfg, quota)
    resultats, code = [], 0
    try:
        if "--en-attente" in argv:
            resultats += synchroniser(yt, cfg)
        envoyes = 0
        for ep_id in ids:
            if envoyes >= cfg["max_envois_par_execution"]:
                break
            print(f"[{ep_id}]")
            r = publier(ep_id, yt, cfg)
            print(f"  -> {r['resultat']} {r['detail']}")
            resultats.append(r)
            if r["resultat"] == "reporte":
                break  # le quota est le même pour tous : inutile d'insister
            if r["resultat"] == "quarantaine":
                code = 1
            if r["resultat"] in ("programme", "publie"):
                envoyes += 1
    except ErreurAuth as e:
        noter_etat_auth("a_refaire", str(e))
        print(f"AUTHENTIFICATION À REFAIRE : {e}", file=sys.stderr)
        resultats.append({"resultat": "auth", "detail": str(e)})
        code = 3
    print(json.dumps({"code": code, "resultats": resultats}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
