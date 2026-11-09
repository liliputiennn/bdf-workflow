"""Banque de sujets : choisit les prochains sujets à écrire, sans répétition.

Sources : `subjects/*.json` (liste de { titre, theme, angle }) et `ideas/*.json` de thème Business (faits déjà
sourcés). Un sujet est « pris » dès qu'un épisode du même identifiant existe (épisodes, brouillons) ou qu'il a été
attribué récemment (`autopilot/state/sujets.json`). Quand la banque est vide, `stock.py besoin` le signale et le
rédacteur en propose de nouveaux (`autopilot/state/sujets_proposes.json`, même format que `subjects/*.json`).
"""
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.common import EPISODES, ROOT, STATE, now, read_json, write_json  # noqa: E402
from autopilot import chaines  # noqa: E402

ATTRIBUTION_TTL = timedelta(days=2)

# Banc d'idées classé : un sujet peut déclarer ses `leviers` (ce qui fait cliquer) ; son score est la somme de leurs points, les mieux classés passent
# d'abord dans leur thème. Un champ `score` explicite l'emporte. Constat du 04/11/2026 sur les plus grosses vidéos du créneau : objet concret à acheter,
# contraste (« bête mais rentable »), urgence (« avant les autres »), contrainte qui parle à tous (« sans argent »), nombre précis dans le titre.
LEVIERS = {"objet": 30, "contraste": 25, "urgence": 20, "contrainte": 15, "chiffre": 10, "classement": 10, "calcul": 10}
# Cap éditorial du 4 novembre 2026 : jamais de lois, statuts, démarches, papiers, assurances. Un sujet qui en fait son titre est écarté.
RE_JURIDIQUE_TITRE = re.compile(r"\bla loi\b|\blois\b|l[ée]gal|\bstatut|d[ée]marches?\b|papiers|assurance|carte pro\b|obligatoire|cotisation|imp[ôo]ts?\b", re.IGNORECASE)
RE_JURIDIQUE_ANGLE = re.compile(r"\bla loi\b|\blois\b|l[ée]gal|\bstatuts?\b|d[ée]marches?\b|papiers|assurance|obligatoire|cotisation|imp[ôo]ts?\b|d[ée]clarer|d[ée]claration", re.IGNORECASE)
NOTE_CAP = " [Cap éditorial : ignore tout ce qui touche aux lois, statuts, démarches, papiers, assurances et impôts ; parle seulement de comment faire et de combien ça rapporte.]"
# Réapprovisionnement : à 8 Shorts par jour, la banque doit toujours avoir de quoi tenir plusieurs semaines.
SEUIL_SHORTS_BANQUE = 40
SEUIL_LONGS_BANQUE = 6


def score(s: dict) -> int:
    if isinstance(s.get("score"), (int, float)):
        return int(s["score"])
    return sum(LEVIERS.get(l, 0) for l in (s.get("leviers") or []))


def slug(titre: str, n: int = 48) -> str:
    s = unicodedata.normalize("NFD", titre.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].strip("-")


def _chaine(chaine: str | None) -> dict:
    return chaines.profil(chaine or chaines.CHAINE_DEFAUT) or chaines.defaut_fr()


def brouillons(chaine: str | None = None) -> list[Path]:
    """Dossiers de brouillons d'une chaîne (`chaine_id` de leur publication.json, sinon la chaîne par défaut)."""
    ch = chaine or chaines.CHAINE_DEFAUT
    return [d for d in (EPISODES / "_brouillons").glob("*") if d.is_dir()
            and ((read_json(d / "publication.json", {}) or {}).get("chaine_id") or chaines.CHAINE_DEFAUT) == ch]


def banque(chaine: str | None = None) -> list[dict]:
    """Banque de sujets d'UNE chaîne : `subjects/` pour la chaîne par défaut, le dossier `dossiers.sujets` de son profil pour les autres.
    Un sujet d'une autre chaîne reçoit l'identifiant `<chaine>-<titre>` : tous les épisodes partagent `episodes-b/`, les identifiants doivent rester uniques."""
    pr = _chaine(chaine)
    defaut = pr["id"] == chaines.CHAINE_DEFAUT
    prefixe = "" if defaut else pr["id"] + "-"
    proposes = STATE / ("sujets_proposes.json" if defaut else f"sujets_proposes-{pr['id']}.json")
    items: list[dict] = []
    for f in sorted(chaines.dossier_sujets(pr).glob("*.json")) + [proposes]:
        for s in read_json(f, []) or []:
            if isinstance(s, dict) and s.get("titre"):
                if RE_JURIDIQUE_TITRE.search(s["titre"]):
                    continue  # sujet juridique : écarté par le cap éditorial du 4 novembre 2026
                angle = s.get("angle", "")
                if RE_JURIDIQUE_ANGLE.search(angle):
                    angle += NOTE_CAP
                items.append({"id": prefixe + slug(s["titre"], 48 - len(prefixe)), "titre": s["titre"], "theme": s.get("theme", "Business"), "angle": angle, "idee": None, "priorite": int(s.get("priorite", 0) or 0), "format": s.get("format") or ("long" if str(s.get("theme", "")).lower().startswith("top 10") else "short"), "score": score(s)})
    for f in sorted((ROOT / "ideas").glob("*.json")) if defaut else []:  # les idées sourcées (ideas/) appartiennent à la chaîne historique
        d = read_json(f, {})
        if str(d.get("theme", "")).lower().startswith("bus"):
            items.append({"id": d["slug"], "titre": d.get("hook", d["slug"]), "theme": "Business", "angle": "", "idee": f"ideas/{f.name}", "score": 0, "format": "short"})
    return items


def pris() -> set[str]:
    ids = {d.name for d in EPISODES.glob("*") if d.is_dir()} | {d.name for d in (EPISODES / "_brouillons").glob("*") if d.is_dir()}
    att = read_json(STATE / "sujets.json", {}) or {}
    limite = datetime.now() - ATTRIBUTION_TTL
    ids |= {k for k, v in att.items() if datetime.fromisoformat(v) > limite}
    return ids


def alterner(libres: list[dict], n: int) -> list[dict]:
    """n sujets en alternant les thèmes pour que deux vidéos de suite ne se ressemblent pas."""
    par_theme: dict[str, list[dict]] = {}
    for s in sorted(libres, key=lambda x: -x.get("score", 0)):  # tri stable : à score égal, l'ordre des fichiers
        par_theme.setdefault(s["theme"], []).append(s)
    sortie: list[dict] = []
    while len(sortie) < n and any(par_theme.values()):
        for theme in sorted(par_theme, key=lambda t: -len(par_theme[t])):
            if par_theme[theme] and len(sortie) < n:
                sortie.append(par_theme[theme].pop(0))
    return sortie


def choisir(libres: list[dict], n: int, ratio: int = 4, max_longs: int = 1) -> list[dict]:
    """Les sujets prioritaires d'abord (champ `priorite`, dans l'ordre des fichiers), mais une place sur `ratio` reste
    à un sujet ordinaire pour garder de la variété ; sans sujet ordinaire (ou prioritaire), l'autre catégorie complète.
    Un sujet « long » (6 à 12 minutes) est lourd à écrire et à fabriquer : au plus `max_longs` par passage."""
    prio = sorted([s for s in libres if s.get("priorite")], key=lambda x: -x.get("score", 0))
    autres = alterner([s for s in libres if not s.get("priorite")], n)
    sortie: list[dict] = []
    longs = 0

    def prendre(liste: list[dict]) -> bool:
        nonlocal longs
        for k, s in enumerate(liste):
            if s.get("format") == "long":
                if longs >= max_longs:
                    continue
                longs += 1
            sortie.append(liste.pop(k))
            return True
        return False

    while len(sortie) < n and (prio or autres):
        place = len(sortie) + 1
        ordre = (autres, prio) if (autres and (place % ratio == 0 or not prio)) else (prio, autres)
        if not (prendre(ordre[0]) or prendre(ordre[1])):
            break
    return sortie


def prochains(n: int, max_longs: int = 1, chaine: str | None = None) -> list[dict]:
    """n sujets non pris : prioritaires d'abord (« 10 business » avec un thème), le reste en alternant les thèmes."""
    sortie = choisir([s for s in banque(chaine) if s["id"] not in pris()], n, max_longs=max_longs)
    att = read_json(STATE / "sujets.json", {}) or {}
    for s in sortie:
        att[s["id"]] = now()
    if sortie:
        write_json(STATE / "sujets.json", att)
    return sortie


def restants(format: str | None = None, chaine: str | None = None) -> int:
    """Sujets encore libres (tous formats, ou seulement `short` / `long`) dans la banque de la chaîne."""
    deja = pris()
    return len([s for s in banque(chaine) if s["id"] not in deja and (format is None or s.get("format", "short") == format)])


def a_reapprovisionner(chaine: str | None = None) -> bool:
    """Vrai quand la banque de Shorts ou de longs passe sous son seuil : le rédacteur doit proposer de nouveaux sujets."""
    return restants("short", chaine) < SEUIL_SHORTS_BANQUE or restants("long", chaine) < SEUIL_LONGS_BANQUE
