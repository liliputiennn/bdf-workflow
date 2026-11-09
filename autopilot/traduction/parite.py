"""Parité structurelle entre un épisode source et son adaptation : tout sauf les mots doit rester identique.

Règle d'or du chantier 2 : on adapte les TEXTES (phrases parlées, textes d'écran, titre, description, miniature), jamais la structure
ni les chiffres. Ainsi les scènes, les faits sourcés et le calage de la voix restent alignés quelle que soit la langue.

- même forme (mêmes clés, mêmes listes de même longueur) ;
- nombres, booléens et valeurs vides identiques ;
- chaînes « techniques » identiques (`type`, `icone`, `theme`, `fichier`, `recherche`, adresses…) ; les autres chaînes sont libres.

Bibliothèque standard seulement.
"""
import math
import re
from typing import Any

# Clés dont la valeur texte est technique : elle doit rester celle de la source.
PROTEGEES = {"type", "icone", "theme", "theme_accent", "gabarit", "fichier", "recherche", "musique", "format", "contenu_ia", "borne",
             "sources", "check", "verified"}
# Clés ajoutées ou réécrites par l'outil lui-même, jamais comparées.
IGNOREES = {"id", "chaine", "langue", "cadeau", "miniature", "_exemple"}


def _comparer(a: Any, b: Any, chemin: str, err: list[str], protege: bool = False) -> None:
    if isinstance(a, bool) or isinstance(b, bool):
        if a is not b:
            err.append(f"{chemin} : booléen différent")
        return
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)):
            err.append(f"{chemin} : le chiffre doit rester {a!r} (trouvé {b!r}) — une traduction ne change jamais un nombre")
        return
    if a is None or b is None:
        if a is not b:
            err.append(f"{chemin} : valeur absente d'un côté")
        return
    if isinstance(a, dict):
        if not isinstance(b, dict):
            err.append(f"{chemin} : un objet est attendu")
            return
        for k in sorted(set(a) | set(b)):
            if k in IGNOREES:
                continue
            if k not in a:
                err.append(f"{chemin}.{k} : clé en trop (absente de la source)")
            elif k not in b:
                err.append(f"{chemin}.{k} : clé manquante (présente dans la source)")
            else:
                _comparer(a[k], b[k], f"{chemin}.{k}", err, protege or k in PROTEGEES)
        return
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            err.append(f"{chemin} : {len(a)} élément(s) attendu(s) comme dans la source (trouvé {len(b) if isinstance(b, list) else 'autre chose'})")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _comparer(x, y, f"{chemin}[{i + 1}]", err, protege)
        return
    if isinstance(a, str):
        if not isinstance(b, str):
            err.append(f"{chemin} : un texte est attendu")
        elif (protege or re.match(r"https?://", a)) and a != b:
            err.append(f"{chemin} : valeur technique à recopier telle quelle ({a!r})")
        elif not a.strip() and b.strip() or a.strip() and not b.strip():
            err.append(f"{chemin} : texte vide d'un seul côté")


def comparer_episode(source: dict, cible: dict) -> list[str]:
    """Défauts de parité entre deux `episode.json` / `episode-long.json` (liste vide = parité)."""
    err: list[str] = []
    _comparer(source, cible, "épisode", err)
    ms, mc = source.get("miniature"), cible.get("miniature")
    if (ms is None) != (mc is None):
        err.append("épisode.miniature : doit exister des deux côtés" if ms else "épisode.miniature : absente de la source")
    return err


def comparer_faits(source, cible) -> list[str]:
    """Faits : mêmes numéros de phrase, mêmes sources, mêmes termes à retrouver dans les pages ; `claim` et `valeur` s'adaptent."""
    if not isinstance(source, list) or not isinstance(cible, list):
        return ["faits.json : une liste est attendue"]
    err: list[str] = []
    if len(source) != len(cible):
        return [f"faits.json : {len(source)} fait(s) comme dans la source attendus (trouvé {len(cible)})"]
    for i, (a, b) in enumerate(zip(source, cible), 1):
        if not isinstance(b, dict):
            err.append(f"fait {i} : un objet est attendu")
            continue
        for k in ("phrase", "sources", "check"):
            if a.get(k) != b.get(k):
                err.append(f"fait {i} : « {k} » doit rester celui de la source ({a.get(k)!r})")
        if not str(b.get("claim", "")).strip():
            err.append(f"fait {i} : « claim » (l'affirmation, dans la langue cible) manque")
    return err


def comparer_publication(source: dict, cible: dict, titres_distincts: bool = True) -> list[str]:
    """Publication : même nombre de tags utiles n'est pas exigé ; le titre doit être différent de celui de la source (pas de copie)."""
    err: list[str] = []
    if not isinstance(cible, dict):
        return ["publication.json doit être un objet"]
    if titres_distincts and str(cible.get("titre", "")).strip().lower() == str(source.get("titre", "")).strip().lower():
        err.append("publication : le titre est identique à celui de la source : réécris-le pour le public cible (pas de copie)")
    if cible.get("description") and cible.get("description") == source.get("description"):
        err.append("publication : la description est recopiée telle quelle de la source")
    return err
