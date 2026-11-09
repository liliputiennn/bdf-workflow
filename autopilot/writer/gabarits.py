"""Gabarits visuels tournants, formes de titre et styles de miniature : la variété qui protège la chaîne du « contenu inauthentique ».

Pourquoi : des dizaines de vidéos par semaine avec la même mise en page et la même forme de titre ressemblent à de la production en série
(META-YOUTUBE.md, « Contenu inauthentique »). Chaque nouvel épisode reçoit donc, de ce module, trois consignes qui tournent :
  - un GABARIT visuel (quelles scènes dominent), construit avec les scènes qui existent déjà : aucune scène nouvelle à coder ;
  - une FORME de titre (liste, question, comparaison, interdit, affirmation, chiffre) ;
  - un STYLE de miniature (createur, telephone, pile, chiffre, question, contraste).
Règle : jamais deux fois de suite le même gabarit, la même forme de titre ni le même style de miniature (et pas les deux derniers :
on prend celui qui n'a pas servi depuis le plus longtemps). Le registre est `autopilot/state/gabarits.json` ; `stock.py besoin` attribue.
Les longs reçoivent une forme de titre et un style de miniature, pas de gabarit (leurs chapitres alternent déjà les scènes).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.common import STATE, now, read_json, write_json  # noqa: E402

REGISTRE_MAX = 24

# nom -> (description pour le rédacteur, scènes exigées {type: minimum}, familles dont il faut au moins n scènes [(types, n)])
GABARITS = {
    "fiche": {
        "nom": "Fiche business n°X",
        "consigne": "Un panneau « business n°X » (scène `fiche` : coût de lancement, temps par jour, gain par jour en accent) puis un `chiffre` ou des `barres` qui "
                    "détaillent le calcul. Le spectateur retient UN business, avec ses trois chiffres.",
        "exige": {"fiche": 1},
        "familles": [(("chiffre", "barres", "anneau", "duel"), 1)],
    },
    "annonces": {
        "nom": "Cartes d'annonce",
        "consigne": "Deux cartes d'annonce ou de prix (scène `annonce`, prix réellement constaté, source citée) qui montrent l'achat puis la revente, "
                    "avec un `chiffre` pour ce qui reste.",
        "exige": {"annonce": 2},
        "familles": [(("chiffre", "barres"), 1)],
    },
    "clips": {
        "nom": "Clips plein écran",
        "consigne": "L'image fait le travail : au moins deux scènes `clip` ou `photo` plein écran (un `clip` au moins pour montrer l'action), "
                    "peu de texte, un seul chiffre qui claque en conclusion.",
        "exige": {},
        "familles": [(("clip", "photo"), 2), (("clip",), 1)],
    },
    "compteur": {
        "nom": "Compteur de gain animé",
        "consigne": "Le gain monte à l'écran : deux scènes `chiffre` (le compteur s'anime de zéro au gain par jour puis au gain du mois) et une scène "
                    "`barres`, `anneau` ou `ligne-temps` pour comparer. Estimation annoncée comme un calcul.",
        "exige": {"chiffre": 2},
        "familles": [(("barres", "anneau", "ligne-temps"), 1)],
    },
    "avant-apres": {
        "nom": "Comparaison avant / après",
        "consigne": "Deux colonnes face à face : une scène `duel` (avant / après, coût / gain, acheté / revendu, à proportions vraies) et une `barres` ou "
                    "`ligne-temps` pour l'écart, puis une `question` pour relancer les commentaires.",
        "exige": {"duel": 1},
        "familles": [(("barres", "ligne-temps", "courbe"), 1)],
    },
}
FORMES_TITRE = {
    "liste": "un nombre + objets précis (« 5 machines à acheter… »)",
    "question": "une vraie question que se pose quelqu'un (« Combien rapporte… ? »)",
    "comparaison": "deux choses face à face (« … ou … », « … contre … »)",
    "interdit": "un conseil à l'impératif négatif (« Arrête de… », « N'achète pas… avant… »)",
    "affirmation": "une affirmation concrète qui surprend (« Le … qui rapporte… »)",
    "chiffre": "un chiffre d'abord, sans liste (« 57 € par jour avec… »)",
}
STYLES_MINIATURE = ("createur", "telephone", "pile", "chiffre", "question", "contraste")


def controler(ep: dict) -> tuple[list[str], list[str]]:
    """(erreurs, avertissements) : si l'épisode déclare un gabarit, les scènes qu'il promet doivent y être."""
    g = ep.get("gabarit")
    if g is None:
        return [], ["« gabarit » non déclaré : le rédacteur doit recopier le gabarit attribué par `stock.py besoin` (variété visuelle)"]
    if g not in GABARITS:
        return [f"gabarit « {g} » inconnu ({', '.join(GABARITS)})"], []
    types = [s.get("type") for s in ep.get("scenes", []) if isinstance(s, dict)]
    err = []
    spec = GABARITS[g]
    for t, mini in spec["exige"].items():
        if types.count(t) < mini:
            err.append(f"gabarit « {g} » : il faut au moins {mini} scène(s) « {t} » ({types.count(t)} trouvée(s))")
    for famille, mini in spec["familles"]:
        n = sum(types.count(t) for t in famille)
        if n < mini:
            err.append(f"gabarit « {g} » : il faut au moins {mini} scène(s) parmi {', '.join(famille)} ({n} trouvée(s))")
    return err, []


def registre() -> list[dict]:
    return (read_json(STATE / "gabarits.json", None) or {}).get("recents", [])


def _moins_recent(options: list[str], cle: str, recents: list[dict]) -> str:
    """L'option qui n'a pas servi depuis le plus longtemps (jamais servie = prioritaire), jamais celle de la dernière vidéo."""
    dernier = {o: -1 for o in options}
    for i, r in enumerate(recents):
        if r.get(cle) in dernier:
            dernier[r[cle]] = i
    interdit = recents[-1].get(cle) if recents else None
    candidats = [o for o in options if o != interdit] or list(options)
    return min(candidats, key=lambda o: (dernier[o], options.index(o)))


def attribuer(sujets: list[dict], ecrire: bool = True) -> list[dict]:
    """Ajoute à chaque sujet `gabarit` (Shorts seulement), `forme_titre` et `style_miniature`, en tournant, et mémorise l'attribution."""
    recents = list(registre())
    for s in sujets:
        long = s.get("format") == "long"
        forme = _moins_recent(list(FORMES_TITRE), "forme", recents)
        style = _moins_recent(list(STYLES_MINIATURE), "style", recents)
        g = None if long else _moins_recent(list(GABARITS), "gabarit", recents)
        s["forme_titre"] = forme
        s["style_miniature"] = style
        if g:
            s["gabarit"] = g
            s["gabarit_consigne"] = GABARITS[g]["consigne"]
        s["forme_titre_consigne"] = FORMES_TITRE[forme]
        recents.append({"id": s.get("id"), "gabarit": g, "forme": forme, "style": style, "date": now()})
    if ecrire and sujets:
        write_json(STATE / "gabarits.json", {"recents": recents[-REGISTRE_MAX:]})
    return sujets
