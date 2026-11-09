"""Publieur YouTube : `pret` -> `programme` -> `publie` (voir autopilot/CONTRAT.md).

    python autopilot/publish/publish.py <id> [--dry-run]
    python autopilot/publish/publish.py --en-attente [--chaine ID] [--dry-run]   # toutes les chaînes ACTIVES (ou une seule)
    python autopilot/publish/publish.py --exemple <id>      # crée un publication.json d'exemple s'il n'existe pas

Codes de sortie : 0 tout va bien (y compris « reporté pour cause de quota »), 1 au moins un épisode en
quarantaine ou un échec de validation, 3 authentification à refaire (rien n'est mis en quarantaine).
La dernière ligne imprimée est un résumé JSON pour l'orchestrateur.

Plusieurs chaînes : chacune a son jeton, ses créneaux et ses réglages (profil `autopilot/chaines/<id>.json`) ; le quota est celui du projet,
partagé. Une chaîne dont le jeton est refusé est signalée (`state/youtube_auth-<id>.json`) sans empêcher les autres de publier ;
un quota épuisé arrête tout le monde (c'est le même pour toutes).
"""
import contextlib
import json
import os
import struct
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import chaines  # noqa: E402
import commentaire  # noqa: E402
from traduction import decalage  # noqa: E402
import common  # noqa: E402
import horaire  # noqa: E402
import langues  # noqa: E402
import reglages  # noqa: E402
import seo  # noqa: E402
from auth import Jeton, ecrire_etat_jetons, noter_etat_auth  # noqa: E402
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
    elif len(desc.encode("utf-8")) > 3 * cfg["description_max_octets"]:
        pb.append(f"description trop longue : {len(desc.encode('utf-8'))} octets (même raccourcie, elle serait méconnaissable)")
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
    langue = cfg.get("langue", "fr")  # langue de la chaîne (son profil)
    if pub.get("langue", langue) != langue:
        av.append(f"langue « {pub.get('langue')} » (attendu {langue})")
    if not isinstance(pub.get("contenu_ia", False), bool):
        pb.append("contenu_ia doit être true ou false")
    return pb, av, pub


def _horodatage(s: float) -> str:
    s = int(round(s))
    h, reste = divmod(s, 3600)
    m, sec = divmod(reste, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def chapitres_description(ep_id: str, langue: str = "fr") -> str:
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
    return langues.libelle(langue, "chapitres") + (" :\n" if langues.langue_de(langue) == "fr" else ":\n") + "\n".join(f"{_horodatage(d)} {t}" for d, t in lignes)


def est_long(ep_id: str) -> bool:
    """Vidéo 16:9 hors Short : un long à chapitres (`episode-long.json`) ou une vidéo d'un format maison marquée `"video": "long"` dans son episode.json (sommeil, quiz long, chansons)."""
    d = common.ep_dir(ep_id)
    return (d / "episode-long.json").exists() or (common.read_json(d / "episode.json", {}) or {}).get("video") == "long"


def tenir_dans(texte: str, limite_octets: int) -> str:
    """Raccourcit `texte` à `limite_octets` octets au plus, en coupant à une fin de paragraphe, de ligne ou de phrase."""
    if len(texte.encode("utf-8")) <= limite_octets:
        return texte
    coupe = texte.encode("utf-8")[: max(0, limite_octets - 4)].decode("utf-8", "ignore")
    for sep in ("\n\n", "\n", ". "):
        i = coupe.rfind(sep)
        if i > len(coupe) * 0.6:
            coupe = coupe[: i + (1 if sep == ". " else 0)]
            break
    return coupe.rstrip() + " …"


def origine_du_short(ep_id: str) -> dict:
    """`origine.json` d'un Short découpé dans un long ({} pour un Short écrit seul)."""
    return common.read_json(common.ep_dir(ep_id) / "origine.json", None) or {}


def url_du_long(ep_id: str) -> str | None:
    """Adresse YouTube du long d'où vient ce Short, si le long a déjà été envoyé."""
    long_id = origine_du_short(ep_id).get("long")
    if not long_id or not common.ep_dir(long_id).exists():
        return None
    return (common.get_status(long_id).get("youtube") or {}).get("url")


def description_finale(pub: dict, cfg: dict, ep_id: str | None = None) -> str:
    """Description envoyée à YouTube : texte du rédacteur (raccourci si besoin) + chapitres, question, mots-clés et hashtags, qui ne sautent jamais.
    Référencement : une dizaine de hashtags (15 au plus, sinon YouTube les ignore tous) et un bloc « Mots-clés » sont COMPLÉTÉS s'ils manquent."""
    desc = pub["description"].strip()
    lang = pub.get("langue") or cfg.get("langue") or "fr"  # langue de la vidéo : libellés ajoutés par le publieur (chapitres, mots-clés, mention)
    long = bool(ep_id) and est_long(ep_id)
    if ep_id and not long:
        desc = seo.relier_au_long(desc, url_du_long(ep_id))  # le Short renvoie vers l'adresse du long dès qu'elle existe
    reserves = ["#Shorts"] if (cfg["hashtag_shorts"] and not long and "#shorts" not in desc.lower()) else []  # un long 16:9 n'est pas un Short
    desc = seo.limiter_hashtags(desc, cfg.get("hashtags_max", seo.HASHTAGS_MAX) - len(reserves))
    ajouts = []
    if long:
        chap = chapitres_description(ep_id, lang)
        if chap and "00:00" not in desc:
            ajouts.append(chap)
    q = (pub.get("question_commentaires") or "").strip()
    if cfg["question_dans_description"] and q and q not in desc:
        ajouts.append(q)
    ia = "voix de synthèse (ia)"
    mention = langues.libelle(lang, "mention_ia")
    deja_dit = ia in desc.lower() or "synthèse" in desc.lower() or mention.lower() in desc.lower() or "synthetic voice" in desc.lower()
    if cfg.get("mention_ia_description", True) and pub.get("contenu_ia") and not deja_dit:
        ajouts.append(mention)  # le badge YouTube est désactivé : on le dit ici, dans la description
    tags = [t for t in (pub.get("tags") or []) if isinstance(t, str)]
    if cfg.get("mots_cles_dans_description", True) and tags and not seo.a_bloc_mots_cles(desc):
        ajouts.append(seo.bloc_mots_cles(pub.get("titre", ""), tags, lang))
    ligne = seo.completer_hashtags(desc + "\n" + "\n".join(ajouts), tags, pub.get("titre", ""), chaine=cfg.get("hashtags_chaine") or [],
                                   reserves=reserves, cible=cfg.get("hashtags_cible", seo.HASHTAGS_CIBLE),
                                   maximum=cfg.get("hashtags_max", seo.HASHTAGS_MAX))
    if ligne:
        ajouts.append(ligne)
    reserve = len("".join("\n\n" + x for x in ajouts).encode("utf-8"))
    desc = tenir_dans(desc, max(300, cfg["description_max_octets"] - reserve - 10))
    return desc + "".join("\n\n" + x for x in ajouts)


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

def creneaux_pris(cfg: dict, chaine: str | None = None) -> set:
    """Instants (UTC) déjà réservés par une vidéo envoyée ou programmée : plusieurs vidéos par jour, une par créneau.
    Chaque chaîne a sa propre grille de créneaux : avec `chaine`, seules ses vidéos comptent."""
    pris = set()
    for ep in common.list_episodes(chaine=chaine):
        st = common.get_status(ep)
        yt = st.get("youtube") or {}
        if st["etat"] != "quarantaine" and yt.get("video_id") and yt.get("publie_a"):
            pris.add(horaire.lire_iso(yt["publie_a"]))
    return pris


def heures_du_format(long: bool, cfg: dict) -> tuple[list[str], set | None]:
    """(heures locales de mise en ligne, jours de la semaine autorisés ou None) pour un long ou un Short."""
    if long:
        return [cfg.get("heure_long") or cfg["heure_publication"]], set(cfg.get("jours_longs", [0, 2, 4]))
    base = cfg.get("heures_shorts") or [cfg["heure_publication"]]
    return horaire.etaler_heures(base, cfg.get("shorts_par_creneau", 1), cfg.get("ecart_creneau_minutes", 15)), None


def prochain_creneau_pour(long: bool, cfg: dict, maintenant_utc, pris: set):
    heures, jours = heures_du_format(long, cfg)
    return horaire.prochain_creneau_libre(heures, cfg["fuseau"], maintenant_utc, pris, cfg["marge_minimale_minutes"], jours)


def _maj_youtube(ep_id: str, **champs) -> dict:
    yt = dict(common.get_status(ep_id).get("youtube") or {})
    yt.update(champs)
    return yt


def commenter(ep_id: str, yt: YouTube, cfg: dict, afficher=print) -> str | None:
    """Poste le commentaire du cadeau sous un long devenu public (une seule fois). Ne lève jamais : la vidéo prime.
    Renvoie 'poste', 'echec' ou None (rien à faire). Le texte est aussi écrit dans `commentaire-epingle.txt` pour le coller à la main."""
    if not cfg.get("commentaire_auto", True):
        return None
    yt_st = common.get_status(ep_id).get("youtube") or {}
    if not yt_st.get("video_id") or yt_st.get("commentaire_id"):
        return None
    texte = commentaire.texte(common.read_json(common.ep_dir(ep_id) / "publication.json", {}) or {})
    if not texte:
        return None
    (common.ep_dir(ep_id) / "commentaire-epingle.txt").write_text(texte, encoding="utf-8")
    try:
        cid = yt.poster_commentaire(yt_st["video_id"], texte)
    except (ErreurQuota, ErreurReseau) as err:
        afficher(f"  commentaire reporté : {err}")
        return "echec"
    except (ErreurAuth, ErreurContenu) as err:
        afficher(f"  commentaire non posté ({err}) : refais la connexion YouTube (auth.py) pour l'autoriser, ou colle commentaire-epingle.txt à la main")
        common.set_status(ep_id, common.get_status(ep_id)["etat"], None, youtube=_maj_youtube(ep_id, commentaire_erreur=str(err)))
        return "echec"
    common.set_status(ep_id, common.get_status(ep_id)["etat"], None,
                      youtube=_maj_youtube(ep_id, commentaire_id=cid, commentaire_a_epingler=True, commentaire_erreur=None))
    afficher("  commentaire du cadeau posté : reste à l'épingler dans YouTube Studio (un clic, l'API ne le permet pas)")
    return "poste"


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
        if not (st.get("youtube") or {}).get("video_id"):  # adaptation : jamais avant la version source (décalage du profil)
            ok_decalage, raison_decalage = decalage.pret_a_sortir(ep_id, maintenant())
            if not ok_decalage:
                return {"id": ep_id, "resultat": "ignore", "detail": raison_decalage}
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
                publie_a = ancien or horaire.iso_utc(prochain_creneau_pour(est_long(ep_id), cfg, maintenant(), creneaux_pris(cfg, common.chaine_de(ep_id))))
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
            commenter(ep_id, yt, cfg, afficher)
            return {"id": ep_id, "resultat": "publie", "detail": yt_etat["url"]}
        common.set_status(ep_id, "programme", None, youtube=yt_etat, tentatives=0)
        return {"id": ep_id, "resultat": "programme", "detail": f"{yt_etat['url']} ({visibilite}, {yt_etat.get('publie_a')})"}
    finally:
        verrou.__exit__(None, None, None)


def synchroniser(yt: YouTube, cfg: dict, maintenant=maintenant_utc, afficher=print, chaine: str | None = None) -> list[dict]:
    """Fait passer `programme` -> `publie` quand la vidéo est devenue publique (1 unité de quota par vidéo échue)."""
    sortie = []
    for ep_id in common.list_episodes("programme", chaine=chaine):
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
                commenter(ep_id, yt, cfg, afficher)
            sortie.append({"id": ep_id, "resultat": "publie", "detail": yt_st.get("url")})
        elif vis == "prive_force":
            noter_audit(ep_id, yt_st["video_id"])
            with common.episode_lock(ep_id):
                common.set_status(ep_id, "programme", None, youtube=_maj_youtube(ep_id, visibilite="prive_force"))
            sortie.append({"id": ep_id, "resultat": "toujours_prive", "detail": "audit YouTube requis"})
    # commentaire du cadeau qui n'a pas pu être posté (autorisation à refaire, quota) : nouvel essai à chaque passage
    for ep_id in common.list_episodes("publie", chaine=chaine):
        yt_st = common.get_status(ep_id).get("youtube") or {}
        if yt_st.get("commentaire_id") or not commentaire.texte(common.read_json(common.ep_dir(ep_id) / "publication.json", {}) or {}):
            continue
        with common.episode_lock(ep_id):
            if commenter(ep_id, yt, cfg, afficher) == "poste":
                sortie.append({"id": ep_id, "resultat": "commentaire_poste", "detail": "à épingler dans YouTube Studio"})
    return sortie


# --- ligne de commande ----------------------------------------------------------------------------------

def _ordre_des_shorts(courts: list[str]) -> list[str]:
    """Les Shorts découpés dans un long passent d'abord (ils ne coûtent ni écriture ni voix en plus), en alternant les longs d'origine
    pour ne pas enchaîner dix Shorts du même sujet ; puis les Shorts écrits seuls. Un Short dont le long est déjà envoyé précède les autres."""
    derives: dict[str, list[str]] = {}
    seuls = []
    for i in courts:
        o = origine_du_short(i).get("long")
        (derives.setdefault(o, []) if o else seuls).append(i)
    # long déjà envoyé (adresse connue) en premier : le Short peut y renvoyer
    envoyes = sorted(derives, key=lambda o: 0 if (common.get_status(o).get("youtube") or {}).get("video_id") else 1)
    sortie = []
    while any(derives[o] for o in envoyes):
        for o in envoyes:
            if derives[o]:
                sortie.append(derives[o].pop(0))
    return sortie + seuls


def _signature(ep_id: str) -> tuple[str, str | None]:
    """(forme du titre, gabarit visuel) d'un épisode : sert à ne jamais publier deux vidéos de même forme l'une après l'autre."""
    pub = common.read_json(common.ep_dir(ep_id) / "publication.json", None) or {}
    ep = common.read_json(common.ep_dir(ep_id) / "episode.json", None) or {}
    return seo.forme_du_titre(str(pub.get("titre", ""))), ep.get("gabarit")


def _conflit(a: tuple, b: tuple) -> bool:
    """Même forme de titre (hors « autre », la forme fourre-tout) ou même gabarit visuel."""
    return (a[0] == b[0] and a[0] != "autre") or (a[1] is not None and a[1] == b[1])


def diversifier(ids: list[str], fenetre: int = 6) -> list[str]:
    """Règle « jamais deux titres de la même forme (ni deux gabarits identiques) de suite » : à chaque place, on prend la première vidéo
    de la file (dans les `fenetre` suivantes) qui ne ressemble pas à la précédente ; sans alternative, l'ordre d'origine est gardé."""
    restants, sortie = list(ids), []
    while restants:
        prec = _signature(sortie[-1]) if sortie else None
        choix = next((i for i in restants[:fenetre] if prec is None or not _conflit(_signature(i), prec)), restants[0])
        restants.remove(choix)
        sortie.append(choix)
    return sortie


def ordonner_par_rythme(ids: list[str], cfg: dict, maintenant=maintenant_utc, chaine: str | None = None) -> list[str]:
    """Rythme de la chaîne : 8 Shorts par jour (4 créneaux de 2) et un long les `jours_longs`.
    Chaque format a ses propres créneaux ; on range les épisodes dans l'ordre chronologique des créneaux qu'ils vont prendre,
    pour que la limite d'envois par passage serve d'abord les créneaux les plus proches (longs et Shorts mêlés)."""
    longs = [i for i in ids if est_long(i)]
    courts = diversifier(_ordre_des_shorts([i for i in ids if not est_long(i)]))
    pris, sortie = set(creneaux_pris(cfg, chaine)), []
    while longs or courts:
        cl = prochain_creneau_pour(True, cfg, maintenant(), pris) if longs else None
        cs = prochain_creneau_pour(False, cfg, maintenant(), pris) if courts else None
        if cl is not None and (cs is None or cl <= cs):
            sortie.append(longs.pop(0))
            pris.add(cl)
        else:
            sortie.append(courts.pop(0))
            pris.add(cs)
    return sortie


def dry_run(ids: list[str], cfg: dict, chaine: str | None = None) -> int:
    code = 0
    pris = creneaux_pris(cfg, chaine)
    for ep_id in ids:
        print(f"[{ep_id}] état : {common.get_status(ep_id)['etat']}")
        pb, av, pub = valider(ep_id, cfg)
        for a in av:
            print(f"  avertissement : {a}")
        for p in pb:
            print(f"  PROBLÈME : {p}")
        if pub and not pb:
            creneau = prochain_creneau_pour(est_long(ep_id), cfg, maintenant_utc(), pris)
            pris.add(creneau)
            nb_h = len(seo.hashtags_du_texte(description_finale(pub, cfg, ep_id)))
            print(f"  {nb_h} hashtags dans la description finale (15 au plus)")
            print(f"  titre ({len(pub['titre'])} car.) : {pub['titre']}")
            print(f"  {len(pub.get('tags', []))} tags, contenu_ia={pub.get('contenu_ia', False)}, miniature : {chemin_miniature(ep_id)}")
            print(f"  mise en ligne prévue : {horaire.iso_utc(creneau)} (privé jusque-là)")
            print("  OK : prêt à publier")
        code = code or (1 if pb else 0)
    return code


def a_du_travail(chaine: str) -> bool:
    """Vrai si la chaîne a une vidéo à envoyer, à synchroniser ou un commentaire à poster : sinon son jeton n'est même pas ouvert."""
    if common.list_episodes("pret", chaine=chaine) or common.list_episodes("programme", chaine=chaine):
        return True
    for ep_id in common.list_episodes("publie", chaine=chaine):
        yt_st = common.get_status(ep_id).get("youtube") or {}
        if not yt_st.get("commentaire_id") and commentaire.texte(common.read_json(common.ep_dir(ep_id) / "publication.json", {}) or {}):
            return True
    return False


def plans_de_publication(args: list[str], chaine_cli: str | None, en_attente: bool) -> tuple[list[tuple[dict, dict, list[str]]], list[str]]:
    """[(profil, réglages, épisodes à publier)] pour chaque chaîne concernée, et les erreurs de demande (chaîne inconnue...).
    `--en-attente` : toutes les chaînes ACTIVES (une chaîne inactive est ignorée) ; sinon la chaîne de chaque épisode nommé."""
    profils = chaines.charger_profils()
    erreurs: list[str] = []
    plans: list[tuple[dict, dict, list[str]]] = []
    if en_attente:
        # cloud : seuls les épisodes dont la vidéo a été récupérée dans le stock (liste séparée par des virgules, « - » = aucun)
        seulement = os.environ.get("BDF_PUBLIER_SEULEMENT")
        for p in chaines.actives(profils):
            if chaine_cli and p["id"] != chaine_cli:
                continue
            cfg = reglages.charger_chaine(p)
            ids = common.list_episodes("pret", chaine=p["id"])
            if seulement is not None:
                ids = [i for i in ids if i in seulement.split(",")]
            plans.append((p, cfg, ordonner_par_rythme(ids, cfg, chaine=p["id"])))
        if chaine_cli and not any(p["id"] == chaine_cli for p, _, _ in plans):
            erreurs.append(f"chaîne « {chaine_cli} » inconnue, inactive ou au profil invalide : rien à publier")
        return plans, erreurs
    par_chaine: dict[str, list[str]] = {}
    for ep_id in args:
        par_chaine.setdefault(common.chaine_de(ep_id), []).append(ep_id)
    for ident, ids in par_chaine.items():
        p = profils.get(ident)
        if p is None or not p["valide"]:
            erreurs.append(f"{', '.join(ids)} : chaîne « {ident} » sans profil valide (autopilot/chaines/{ident}.json)")
            continue
        plans.append((p, reglages.charger_chaine(p), ids))
    return plans, erreurs


def main(argv: list[str]) -> int:
    args = list(argv)
    chaine_cli = None
    if "--chaine" in args:  # la valeur suit l'option : elle n'est pas un identifiant d'épisode
        i = args.index("--chaine")
        chaine_cli = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    seul_exemple = "--exemple" in args
    dry = "--dry-run" in args
    en_attente = "--en-attente" in args
    ids = [a for a in args if not a.startswith("--")]
    if seul_exemple:
        for ep_id in ids:
            print(f"{creer_exemple(ep_id)}")
        return 0
    if not en_attente and not ids:
        print(__doc__)
        return 2
    plans, erreurs = plans_de_publication(ids, chaine_cli, en_attente)
    for e in erreurs:
        print(f"PROBLÈME : {e}", file=sys.stderr)
    code = 1 if erreurs else 0
    if dry:
        for p, cfg, ids_c in plans:
            if len(plans) > 1 or p["id"] != chaines.CHAINE_DEFAUT:
                print(f"=== chaîne {p['id']} ({p['nom']}) ===")
            code = dry_run(ids_c, cfg, p["id"]) or code
        return code

    with contextlib.suppress(Exception):
        ecrire_etat_jetons()  # état de connexion de chaque chaîne (booléens), lu par l'orchestrateur et la web app
    quota = RegistreQuota(reglages.charger())  # un seul registre : le quota est celui du projet Google, partagé par toutes les chaînes
    resultats, auth_ko = [], False
    for p, cfg, ids_c in plans:
        ident = p["id"]
        if en_attente and not a_du_travail(ident):
            continue
        yt = YouTube(Jeton(chaine=ident), cfg, quota.pour(ident))
        envoyes, quota_epuise = 0, False
        try:
            if en_attente:
                resultats += [{**r, "chaine": ident} for r in synchroniser(yt, cfg, chaine=ident)]
            for ep_id in ids_c:
                if envoyes >= cfg["max_envois_par_execution"]:
                    break
                print(f"[{ep_id}]" + ("" if ident == chaines.CHAINE_DEFAUT else f" (chaîne {ident})"))
                r = {**publier(ep_id, yt, cfg), "chaine": ident}
                print(f"  -> {r['resultat']} {r['detail']}")
                resultats.append(r)
                if r["resultat"] == "reporte":
                    quota_epuise = True  # le quota est le même pour toutes les chaînes : inutile d'insister
                    break
                if r["resultat"] == "quarantaine":
                    code = code or 1
                if r["resultat"] in ("programme", "publie"):
                    envoyes += 1
        except ErreurAuth as e:
            # le jeton de CETTE chaîne est à refaire ; les autres chaînes continuent
            noter_etat_auth("a_refaire", str(e), chaine=ident)
            print(f"AUTHENTIFICATION À REFAIRE (chaîne {ident}) : {e}", file=sys.stderr)
            resultats.append({"chaine": ident, "resultat": "auth", "detail": str(e)})
            auth_ko = True
        except Exception as e:  # noqa: BLE001 - une chaîne qui plante ne doit pas arrêter les autres
            print(f"ERREUR INATTENDUE (chaîne {ident}) :\n{traceback.format_exc()}", file=sys.stderr)
            resultats.append({"chaine": ident, "resultat": "erreur", "detail": f"{type(e).__name__}: {e}"})
            code = code or 1
        if quota_epuise:
            break
    if auth_ko:
        code = 3
    print(json.dumps({"code": code, "resultats": resultats}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
