"""Valide un épisode écrit par le rédacteur, puis le fait entrer dans le workflow.

Usage :  python autopilot/writer/valider.py <id> [--sans-reseau]

Le rédacteur écrit dans `episodes-b/_brouillons/<id>/` :
  - un Short : episode.json, faits.json, publication.json ;
  - un long (6 à 12 minutes, chapitres) : episode-long.json, faits.json, publication.json.
Ce script :
  - contrôle la forme (mêmes règles que `autopilot/make_short.py` / `autopilot/long/longlib.py`), la durée estimée,
    les faits et leurs sources, la publication ; vérifie chaque fait dans ses sources (autopilot/writer/factcheck.py) ;
  - si tout est bon : déplace le dossier vers `episodes-b/<id>/` et pose l'état `ecrit`
    (pour un long, écrit aussi `episode.json`, une vue à plat servant à la miniature et à la publication) ;
  - sinon : affiche les erreurs (JSON sur la sortie standard) pour que le rédacteur corrige, et après 3 échecs
    déplace l'épisode en `quarantaine` avec la raison (relecture humaine).
Code retour : 0 = accepté, 1 = à corriger, 2 = mis en quarantaine.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.common import EPISODES, ep_dir, get_status, read_json, set_status, write_json  # noqa: E402
from autopilot.make_short import validate as valider_forme  # noqa: E402
from autopilot.long import longlib  # noqa: E402
from autopilot.writer.factcheck import domaine, url_valide, verifier  # noqa: E402

BROUILLONS = EPISODES / "_brouillons"
MOTS_NOMBRE = set("zero deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente quarante cinquante soixante cent cents mille million millions milliard milliards pourcent pour-cent".split())
MIN_MOTS, MAX_MOTS = 55, 170  # environ 3 mots par seconde : 20 à 55 secondes
MIN_MOTS_LONG, MAX_MOTS_LONG = 1000, 2200  # 6 à 12 minutes
MAX_ESSAIS = 3
MAX_MOTS_PHRASE = 15
MAX_MOTS_PHRASE_LONG = 26  # sous-titres coupés en morceaux courts à l'écran : la phrase peut être plus longue qu'en Short
STYLES_MINIATURE = ("createur", "telephone", "pile", "chiffre", "question", "contraste")
ICONES = ("carte", "hotdog", "magasin", "pieces", "panier")


def a_un_nombre(phrase: str) -> bool:
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ0-9-]+", phrase.lower())
    return any(re.search(r"\d", m) or m in MOTS_NOMBRE for m in mots)


def controles_faits(phrases: list, faits, reseau: bool):
    """Faits sourcés : au moins 2 sources de 2 sites, vérifiées dans la page ; toute phrase chiffrée est couverte."""
    err: list[str] = []
    avert: list[str] = []
    if not isinstance(faits, list) or not faits:
        err.append("faits.json doit être une liste non vide de faits")
        faits = []
    couvertes = set()
    for i, f in enumerate(faits):
        n = f"fait {i + 1}"
        if not isinstance(f, dict):
            err.append(f"{n} : doit être un objet")
            continue
        for k in ("claim", "valeur", "phrase", "sources", "check"):
            if k not in f:
                err.append(f"{n} : « {k} » manque")
        ph = f.get("phrase")
        if isinstance(ph, int) and 1 <= ph <= len(phrases):
            couvertes.add(ph)
        else:
            err.append(f"{n} : « phrase » doit être un numéro entre 1 et {len(phrases)}")
        src = f.get("sources") or []
        if len(src) < 2:
            err.append(f"{n} : il faut au moins 2 sources")
        for u in src:
            r = url_valide(u)
            if r:
                err.append(f"{n} : {u} refusée ({r})")
        if len({domaine(u) for u in src}) < 2:
            err.append(f"{n} : les sources doivent venir d'au moins 2 sites différents")
        if not f.get("check"):
            err.append(f"{n} : « check » (mots ou nombres à retrouver dans la page) est vide")
        elif not err or reseau:
            f["verified"] = verifier(f, reseau) if reseau else f.get("verified", [])
            if reseau and not f["verified"]:
                err.append(f"{n} : aucune source ne contient {f['check']} ; trouve une source qui l'écrit vraiment ou corrige le chiffre")
            elif reseau and len(f["verified"]) == 1:
                avert.append(f"{n} : une seule source confirme le fait automatiquement")
    for i, p in enumerate(phrases, 1):
        if a_un_nombre(p) and i not in couvertes:
            err.append(f"phrase {i} : contient un nombre mais aucun fait ne la couvre (ajoute-le dans faits.json avec 2 sources)")
    return err, avert, faits


def controles_miniature(mini) -> list[str]:
    err: list[str] = []
    if not isinstance(mini, dict):
        return ["« miniature » manque (style, texte_haut, gros, icone : voir CONSIGNES.md)"]
    if mini.get("style") not in STYLES_MINIATURE:
        err.append("miniature : « style » doit être " + ", ".join(STYLES_MINIATURE))
    mots_haut = len(str(mini.get("texte_haut", "")).split())
    if not 1 <= mots_haut <= 5:
        err.append(f"miniature : « texte_haut » doit avoir 1 à 5 mots ({mots_haut} trouvés)")
    if mini.get("icone") not in ICONES:
        err.append("miniature : « icone » doit être " + ", ".join(ICONES))
    if mini.get("style") == "contraste" and not (isinstance(mini.get("contraste"), list) and len(mini["contraste"]) == 2):
        err.append("miniature : le style « contraste » demande deux valeurs dans « contraste »")
    if mini.get("style") != "question" and not str(mini.get("gros", "")).strip():
        err.append("miniature : « gros » (le chiffre le plus frappant) manque")
    return err


def controles_publication(pub) -> list[str]:
    err: list[str] = []
    if not isinstance(pub, dict):
        return ["publication.json doit être un objet"]
    t = pub.get("titre", "")
    if not t or len(t) > 70:
        err.append(f"publication : titre vide ou trop long ({len(t)} caractères, 70 au plus)")
    if not str(pub.get("description", "")).strip():
        err.append("publication : description vide")
    tags = pub.get("tags", [])
    if not isinstance(tags, list) or not 3 <= len(tags) <= 15:
        err.append("publication : de 3 à 15 tags attendus")
    if pub.get("contenu_ia") is not True:
        err.append("publication : « contenu_ia » doit valoir true (voix synthétique)")
    return err


def controles(ep: dict, faits, pub, reseau: bool = True):
    """Un Short (9:16, 20 à 55 secondes)."""
    err: list[str] = []
    avert: list[str] = []
    err += valider_forme(ep)
    if err and "phrases" not in ep:
        return err, avert, faits
    phrases = ep.get("phrases", [])
    mots = sum(len(p.split()) for p in phrases)
    for i, p in enumerate(phrases, 1):
        if len(p.split()) > MAX_MOTS_PHRASE:
            err.append(f"phrase {i} : {len(p.split())} mots, {MAX_MOTS_PHRASE} au plus (coupe-la en deux : elle recouvrirait le graphique)")
    if not MIN_MOTS <= mots <= MAX_MOTS:
        err.append(f"{mots} mots au total : il en faut de {MIN_MOTS} à {MAX_MOTS} (environ 20 à 55 secondes)")
    e2, a2, faits = controles_faits(phrases, faits, reseau)
    err += e2
    avert += a2
    err += [f"episode.json : {e}" if e.startswith("« miniature »") else e for e in controles_miniature(ep.get("miniature"))]
    err += controles_publication(pub)
    return err, avert, faits


def controles_long(ep: dict, faits, pub, reseau: bool = True):
    """Un long (16:9, 6 à 12 minutes, chapitres) : même exigence de sources, durée et chapitres propres au format."""
    err: list[str] = list(longlib.validate_long(ep))
    avert: list[str] = []
    if err and not isinstance(ep.get("chapitres"), list):
        return err, avert, faits
    try:
        plat = longlib.flatten(ep)
    except (KeyError, TypeError):
        return err or ["episode-long.json : chapitres illisibles"], avert, faits
    phrases = plat["phrases"]
    mots = sum(len(p.split()) for p in phrases)
    for i, p in enumerate(phrases, 1):
        if len(p.split()) > MAX_MOTS_PHRASE_LONG:
            err.append(f"phrase {i} (globale) : {len(p.split())} mots, {MAX_MOTS_PHRASE_LONG} au plus")
    if not MIN_MOTS_LONG <= mots <= MAX_MOTS_LONG:
        err.append(f"{mots} mots au total : il en faut de {MIN_MOTS_LONG} à {MAX_MOTS_LONG} (6 à 12 minutes)")
    e2, a2, faits = controles_faits(phrases, faits, reseau)
    err += e2
    avert += a2
    err += [f"episode-long.json : {e}" if e.startswith("« miniature »") else e for e in controles_miniature(ep.get("miniature"))]
    err += controles_publication(pub)
    return err, avert, faits


def vue_a_plat(ep: dict) -> dict:
    """`episode.json` d'un long : phrases et scènes bout à bout (numérotation globale). Sert à la miniature et à la publication, jamais au rendu."""
    plat = longlib.flatten(ep)
    out = {"id": ep["id"], "format": "long", "titre": ep["titre"], "theme": ep["theme"], "chaine": ep["chaine"],
           "phrases": plat["phrases"], "scenes": plat["scenes"], "miniature": ep.get("miniature")}
    if ep.get("theme_accent"):
        out["theme_accent"] = ep["theme_accent"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--sans-reseau", action="store_true")
    a = ap.parse_args()
    d = BROUILLONS / a.id
    long = (d / "episode-long.json").exists()
    nom = "episode-long.json" if long else "episode.json"
    ep = read_json(d / nom)
    if ep is None:
        print(json.dumps({"ok": False, "erreurs": [f"{d}\\{nom} introuvable ou illisible (JSON invalide ?)"]}, ensure_ascii=False))
        return 1
    faits, pub = read_json(d / "faits.json"), read_json(d / "publication.json")
    if ep.get("id") != a.id:
        ep["id"] = a.id
    err, avert, faits = (controles_long if long else controles)(ep, faits, pub, reseau=not a.sans_reseau)
    if not err:
        write_json(d / "faits.json", faits)
        write_json(d / nom, ep)
        if long:
            write_json(d / "episode.json", vue_a_plat(ep))
        os.replace(d, EPISODES / a.id)
        set_status(a.id, "ecrit", tentatives=0)
        print(json.dumps({"ok": True, "format": "long" if long else "short", "avertissements": avert, "dossier": str(EPISODES / a.id)}, ensure_ascii=False))
        return 0
    essais_f = d / ".essais"
    essais = int(essais_f.read_text()) + 1 if essais_f.exists() else 1
    essais_f.write_text(str(essais))
    if essais >= MAX_ESSAIS:
        raison = f"validation échouée {essais} fois : " + " | ".join(err[:4])
        write_json(d / "erreurs.json", {"erreurs": err, "avertissements": avert})
        os.replace(d, EPISODES / a.id)
        set_status(a.id, "quarantaine", raison, tentatives=essais)
        print(json.dumps({"ok": False, "quarantaine": True, "erreurs": err}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": False, "essai": essais, "essais_max": MAX_ESSAIS, "erreurs": err, "avertissements": avert}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
