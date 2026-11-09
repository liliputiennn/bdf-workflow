"""File de traduction : quels épisodes d'une chaîne source doivent être adaptés pour une chaîne cible, et leurs demandes.

Pour chaque chaîne cible valide (`source` dans son profil, `active` ou `preparation`) :
  - les épisodes éligibles de la chaîne source : autonomes (ni découpés d'un long, ni eux-mêmes des adaptations), en `controle`, `pret`,
    `programme` ou `publie` (jamais `quarantaine`, jamais un épisode encore en cours d'écriture), pas déjà adaptés ni en cours d'adaptation ;
  - le stock de la cible (en jours) comparé à `source.cible_jours_de_stock` (défaut 4) : on ne demande que ce qu'il faut ;
  - une « demande » `episodes-b/_traductions/<cible>-<id>/demande.json` par épisode : la source complète + les consignes de la langue.

Rien ici n'active une chaîne, ne publie, ni ne lit de secret.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot import chaines, langues  # noqa: E402
from autopilot.common import EPISODES, chaine_de, get_status, list_episodes, now, read_json, write_json  # noqa: E402
from autopilot.writer import stock  # noqa: E402

ETATS_SOURCE = ("controle", "pret", "programme", "publie")
CIBLE_JOURS_DEFAUT = 4.0
MAX_PAR_PASSAGE_DEFAUT = 3
ATTENTE_CLAUDE_H_DEFAUT = 36.0
CONSIGNES = "autopilot/traduction/CONSIGNES-TRADUCTION.md"


def dossier_demandes() -> Path:
    return EPISODES / "_traductions"


def id_cible(cible: str, source_id: str) -> str:
    return f"{cible}-{source_id}"


def options(p: dict) -> dict:
    s = p.get("source") or {}
    def num(cle, defaut):
        v = s.get(cle)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else defaut
    return {"cible_jours_de_stock": num("cible_jours_de_stock", CIBLE_JOURS_DEFAUT), "decalage_heures": num("decalage_heures", 48.0),
            "attente_claude_heures": num("attente_claude_heures", ATTENTE_CLAUDE_H_DEFAUT), "max_par_passage": int(num("max_par_passage", MAX_PAR_PASSAGE_DEFAUT))}


def chaines_cibles(seulement: str | None = None, profils: dict | None = None) -> list[dict]:
    """Chaînes qui reprennent une autre chaîne (`source`) et qu'on alimente : valides, `active` ou `preparation`. Jamais une chaîne ignorée."""
    out = []
    for p in chaines.preparees(profils):
        src = p.get("source")
        if isinstance(src, dict) and src.get("mode", "traduction") == "traduction" and (seulement in (None, p["id"])):
            out.append(p)
    return out


def demandes_ouvertes(cible: str | None = None) -> list[str]:
    """Identifiants des demandes d'adaptation en attente (dossier `_traductions/<id>/demande.json`)."""
    ids = []
    for d in sorted(dossier_demandes().glob("*")):
        dem = read_json(d / "demande.json", None) if d.is_dir() else None
        if isinstance(dem, dict) and cible in (None, dem.get("chaine_cible")) and not (EPISODES / d.name / "status.json").exists():
            ids.append(d.name)
    return ids


def est_autonome(source_id: str) -> bool:
    d = EPISODES / source_id
    return not (d / "origine.json").exists() and not (d / "traduction.json").exists()


def deja_pris(cible: str, source_id: str) -> bool:
    """Un épisode adapté, un brouillon ou une demande existent déjà pour cette source (même écartés en quarantaine : jamais deux fois)."""
    i = id_cible(cible, source_id)
    return ((EPISODES / i).exists() or (EPISODES / "_brouillons" / i).exists() or (dossier_demandes() / i).exists()
            or (EPISODES / "_ecartes" / i).exists())


def sources_eligibles(p: dict) -> list[str]:
    """Épisodes de la chaîne source de `p` à adapter, les plus anciens d'abord."""
    src = p["source"]["chaine"]
    lot = []
    for ep in list_episodes(chaine=src):
        st = get_status(ep)
        if st.get("etat") not in ETATS_SOURCE or not est_autonome(ep) or deja_pris(p["id"], ep):
            continue
        if not (EPISODES / ep / "faits.json").exists() or not (EPISODES / ep / "publication.json").exists():
            continue
        lot.append((st.get("maj") or "", ep))
    return [ep for _, ep in sorted(lot)]


def stock_cible(p: dict) -> dict:
    """Stock de la chaîne cible en jours (épisodes en stock + brouillons + demandes ouvertes, à la cadence de la chaîne)."""
    c = stock.compter(p["id"])
    ouvertes = len([i for i in demandes_ouvertes(p["id"]) if not (EPISODES / "_brouillons" / i).exists()])
    rythme = stock.rythme_par_jour(p["id"])
    jours = round((c["videos_en_stock"] + c["shorts_a_venir"] + c["brouillons"] + ouvertes) / rythme, 2)
    return {"videos_en_stock": c["videos_en_stock"], "brouillons": c["brouillons"], "demandes": ouvertes, "rythme_par_jour": round(rythme, 2), "jours_de_stock": jours}


def construire_demande(p: dict, source_id: str) -> dict:
    """La demande complète d'adaptation d'un épisode : tout ce dont Claude (ou le moteur de repli) a besoin, sans rien d'autre à chercher."""
    d = EPISODES / source_id
    long = (d / "episode-long.json").exists()
    langue = langues.langue_de(p["langue"])
    info = langues.infos(langue)
    nom_ep = "episode-long.json" if long else "episode.json"
    ep = read_json(d / nom_ep, {}) or {}
    return {
        "id": id_cible(p["id"], source_id), "source": source_id, "chaine_source": p["source"]["chaine"], "chaine_cible": p["id"],
        "langue": langue, "langue_nom": info["nom"], "langue_source": langues.langue_de((chaines.profil(p["source"]["chaine"]) or {}).get("langue", "fr")),
        "format": "long" if long else "short", "fichier_episode": nom_ep, "cree_le": now(),
        "nom_chaine": p["nom"], "consignes": CONSIGNES,
        "episode": ep, "faits": read_json(d / "faits.json", []), "publication": read_json(d / "publication.json", {}),
        "mots_source": sum(len(x.split()) for x in ([x for c in ep.get("chapitres", []) for x in c.get("phrases", [])] if long else ep.get("phrases", []))),
        "libelles": info["libelles"],
    }


def creer_demande(p: dict, source_id: str) -> dict:
    dem = construire_demande(p, source_id)
    write_json(dossier_demandes() / dem["id"] / "demande.json", dem)
    return dem


def alimenter(p: dict, maximum: int | None = None, seulement_source: str | None = None) -> dict:
    """Crée les demandes qui manquent pour que le stock de `p` atteigne sa cible. Renvoie le bilan (demandes créées, stock avant)."""
    opt = options(p)
    avant = stock_cible(p)
    maxi = opt["max_par_passage"] if maximum is None else maximum
    creees: list[str] = []
    if seulement_source:
        if not deja_pris(p["id"], seulement_source) and (EPISODES / seulement_source / "episode.json").exists():
            creees.append(creer_demande(p, seulement_source)["id"])
    else:
        rythme = avant["rythme_par_jour"]
        manque = max(0, math.ceil(opt["cible_jours_de_stock"] * rythme - avant["jours_de_stock"] * rythme))
        for s in sources_eligibles(p):
            if len(creees) >= min(maxi, manque):
                break
            creees.append(creer_demande(p, s)["id"])
    return {"chaine": p["id"], "stock_avant": avant, "cible_jours": opt["cible_jours_de_stock"], "creees": creees,
            "sources_restantes": len(sources_eligibles(p))}


def etat_chaine(p: dict) -> dict:
    """Vue d'une chaîne cible pour l'orchestrateur et la web app : file, épisodes adaptés par état, sources restantes."""
    opt = options(p)
    adaptes = [i for i in list_episodes(chaine=p["id"]) if (EPISODES / i / "traduction.json").exists()]
    par_etat: dict[str, int] = {}
    a_relire = 0
    for i in adaptes:
        e = get_status(i).get("etat", "ecrit")
        par_etat[e] = par_etat.get(e, 0) + 1
        a_relire += 1 if (read_json(EPISODES / i / "traduction.json", {}) or {}).get("a_relire") else 0
    ouvertes = demandes_ouvertes(p["id"])
    brouillons = [i for i in ouvertes if (EPISODES / "_brouillons" / i).exists()]
    src_prof = chaines.profil(p["source"]["chaine"]) or {}
    return {"chaine": p["id"], "source": p["source"]["chaine"], "mode": p["source"].get("mode", "traduction"), "langue": p["langue"],
            "langue_source": src_prof.get("langue", "fr"), "voix": chaines.voix_info(p), "preparation": bool(p.get("preparation")),
            "active": bool(p.get("active")), "cible_jours_de_stock": opt["cible_jours_de_stock"], "decalage_heures": opt["decalage_heures"],
            "stock": stock_cible(p), "adaptes": len(adaptes), "adaptes_par_etat": par_etat, "a_relire": a_relire,
            "file": {"demandes": len(ouvertes) - len(brouillons), "brouillons": len(brouillons), "ids": ouvertes[:20]},
            "sources_restantes": len(sources_eligibles(p)), "claude_bloque": (Path(stock.STATE) / "claude_blocked.json").exists()}
