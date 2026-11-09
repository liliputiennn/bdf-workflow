"""Briques partagées des formats maison : contrôle de sources, mots à refuser, normalisation de texte.

Importé par `quiz.py`, `apprendre.py`, `sommeil.py`, `musique_enfants.py` ; jamais par le moteur lui-même.
"""
import re
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from autopilot.writer.factcheck import domaine, url_valide, verifier  # noqa: E402


def norm(s: str) -> str:
    """Minuscules sans accents ni ponctuation (comparaisons tolérantes)."""
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def chiffres(s: str) -> bool:
    return bool(re.search(r"\d", str(s)))


# promesses de gain, santé miraculeuse, injonctions : refusées dans TOUS les formats
RE_PROMESSE = re.compile(r"garanti|sans risque|devenez? riche|gagner de l.argent|revenus? passifs?|100 ?% ?(?:s[uû]r|efficace)|miracle", re.I)


def controle_sources(item: dict, nom: str, reseau: bool = True, minimum: int = 2) -> tuple[list[str], list[str]]:
    """Un fait vérifiable : `sources` (>= `minimum` adresses https de sites différents) et `check` (mots à retrouver dans les pages).
    Réseau : au moins une source doit contenir TOUS les mots de `check` ; une seule source qui les contient = avertissement."""
    err: list[str] = []
    avert: list[str] = []
    src = item.get("sources")
    if not isinstance(src, list) or len([u for u in src if isinstance(u, str)]) < minimum:
        return [f"{nom} : il faut au moins {minimum} sources (adresses https de sites différents)"], avert
    for u in src:
        r = url_valide(u) if isinstance(u, str) else "pas une adresse"
        if r:
            err.append(f"{nom} : {u} refusée ({r})")
    if len({domaine(u) for u in src if isinstance(u, str)}) < minimum:
        err.append(f"{nom} : les sources doivent venir d'au moins {minimum} sites différents")
    check = item.get("check")
    if not isinstance(check, list) or not check or not all(isinstance(c, str) and c.strip() for c in check):
        err.append(f"{nom} : « check » (mots à retrouver dans les pages) manque")
        return err, avert
    if err:
        return err, avert
    if reseau:
        ok = verifier({"sources": src, "check": check}, True)
        if not ok:
            err.append(f"{nom} : aucune source ne contient {check} ; cite une page qui l'écrit vraiment")
        elif len(ok) == 1:
            avert.append(f"{nom} : une seule source confirme automatiquement")
    return err, avert
