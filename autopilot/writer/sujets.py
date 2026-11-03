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

ATTRIBUTION_TTL = timedelta(days=2)


def slug(titre: str, n: int = 48) -> str:
    s = unicodedata.normalize("NFD", titre.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].strip("-")


def banque() -> list[dict]:
    items: list[dict] = []
    for f in sorted((ROOT / "subjects").glob("*.json")) + [STATE / "sujets_proposes.json"]:
        for s in read_json(f, []) or []:
            if isinstance(s, dict) and s.get("titre"):
                items.append({"id": slug(s["titre"]), "titre": s["titre"], "theme": s.get("theme", "Business"), "angle": s.get("angle", ""), "idee": None, "priorite": int(s.get("priorite", 0) or 0), "format": s.get("format") or ("long" if str(s.get("theme", "")).lower().startswith("top 10") else "short")})
    for f in sorted((ROOT / "ideas").glob("*.json")):
        d = read_json(f, {})
        if str(d.get("theme", "")).lower().startswith("bus"):
            items.append({"id": d["slug"], "titre": d.get("hook", d["slug"]), "theme": "Business", "angle": "", "idee": f"ideas/{f.name}"})
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
    for s in libres:
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
    prio = [s for s in libres if s.get("priorite")]
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


def prochains(n: int, max_longs: int = 1) -> list[dict]:
    """n sujets non pris : prioritaires d'abord (« 10 business » avec un thème), le reste en alternant les thèmes."""
    sortie = choisir([s for s in banque() if s["id"] not in pris()], n, max_longs=max_longs)
    att = read_json(STATE / "sujets.json", {}) or {}
    for s in sortie:
        att[s["id"]] = now()
    if sortie:
        write_json(STATE / "sujets.json", att)
    return sortie


def restants() -> int:
    return len([s for s in banque() if s["id"] not in pris()])
