"""Adaptation automatique d'un épisode par un traducteur « texte à texte » (repli gratuit, ou n'importe quel callable).

Le traducteur ne voit que des chaînes : toute la structure (scènes, chiffres, faits, sources) est recopiée de la source, ce qui garantit la
parité exigée par `parite.py`. Ensuite on localise :
  - texte parlé : tout chiffre devient des mots dans la langue cible (`langues.chiffres_en_lettres`) ;
  - texte d'écran : séparateurs de milliers et décimales à la convention de la langue (« 12 000,5 € » -> « €12,000.5 ») ;
  - titre, description, tags, question de commentaires, miniature : traduits, hashtags refaits à partir des tags traduits.

Le repli ne traite que les Shorts : un long (chapitres, cadeau recopié dans la description, chapitres horodatés) attend Claude.
Bibliothèque standard seulement.
"""
import copy
import re
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot import langues, seo  # noqa: E402
from autopilot.traduction.parite import IGNOREES as _IGN, PROTEGEES as _PROT  # noqa: E402

IGNOREES = _IGN - {"miniature"}      # la miniature, elle, se traduit (la parité, elle, ne la compare pas)
PROTEGEES = _PROT | {"style"}        # « style » de miniature (createur, telephone…) : un identifiant, pas un texte

Traducteur = Callable[[list], list]
CLES_LIBRES_MINIATURE = ("texte_haut", "gros")
NBSP = "  "


def a_des_lettres(t: str) -> bool:
    return bool(re.search(r"[^\W\d_]", t or "", re.UNICODE))


def localiser_ecran(t: str, langue: str) -> str:
    """Nombres affichés à l'écran : convention de la langue cible (anglais : virgule pour les milliers, point décimal, devise devant)."""
    if langues.langue_de(langue) not in ("en",):
        return t
    t = re.sub(r"(?<=\d)[ " + NBSP + r"](?=\d{3}(?!\d))", ",", t)
    t = re.sub(r"(?<=\d),(?=\d{1,2}(?!\d))", ".", t)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)[ " + NBSP + r"]?€", r"€\1", t)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)[ " + NBSP + r"]?\$", r"$\1", t)
    t = re.sub(r"(\d)[ " + NBSP + r"]%", r"\1%", t)
    return t


def _liste(obj, cle=None, protege=False, chemin=()):
    """Parcourt la structure : chaque chaîne libre est rendue avec son chemin (liste de clés/indices)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in IGNOREES:
                continue
            yield from _liste(v, k, protege or k in PROTEGEES, chemin + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _liste(v, cle, protege, chemin + (i,))
    elif isinstance(obj, str) and not protege and not obj.startswith("http"):
        yield chemin, obj


def _lire(obj, chemin):
    for c in chemin:
        obj = obj[c]
    return obj


def _ecrire(obj, chemin, valeur):
    for c in chemin[:-1]:
        obj = obj[c]
    obj[chemin[-1]] = valeur


def mots_accent(phrase: str, n: int = 2) -> list[str]:
    """Mots à faire claquer dans un gros titre : les plus longs de la phrase (dans la langue cible)."""
    mots = [m for m in re.findall(r"[^\W\d_]{4,}", phrase, re.UNICODE)]
    return sorted(set(mots), key=lambda m: (-len(m), m))[:n]


def adapter_episode(ep: dict, traducteur: Traducteur, langue: str, etiquette_chaine: str, nouvel_id: str) -> dict:
    """Épisode cible : même structure, textes traduits et localisés. `ep` n'est pas modifié."""
    out = copy.deepcopy(ep)
    elements = [(ch, t) for ch, t in _liste(out) if a_des_lettres(t)]
    # les accents d'un gros titre sont refaits à partir de la phrase traduite (ils doivent être des mots de la phrase)
    a_traduire = [(ch, t) for ch, t in elements if "accents" not in ch]
    uniques = list(dict.fromkeys(t for _, t in a_traduire))
    traduits = dict(zip(uniques, traducteur(uniques))) if uniques else {}
    parlee = set()
    for ch, t in a_traduire:
        r = traduits[t].strip()
        if ch[0] == "phrases" or (ch[0] == "chapitres" and "phrases" in ch):
            r = langues.chiffres_en_lettres(r, langue)
            parlee.add(ch)
        else:
            r = localiser_ecran(r, langue)
        _ecrire(out, ch, r)
    # textes d'écran sans lettres (« 12 000 € », « 0,5 % ») : seulement la convention des nombres
    for ch, t in _liste(out):
        if not a_des_lettres(t) and ch[0] != "phrases":
            _ecrire(out, ch, localiser_ecran(t, langue))
    phrases = out["phrases"] if "phrases" in out else None
    for sc in out.get("scenes", []):
        if sc.get("type") == "titre-geant" and "accents" in (sc.get("params") or {}) and phrases:
            sc["params"]["accents"] = mots_accent(phrases[min(sc["phrase"], len(phrases)) - 1])
    out["id"], out["chaine"], out["langue"] = nouvel_id, etiquette_chaine, langues.langue_de(langue)
    return out


def adapter_faits(faits: list, traducteur: Traducteur, langue: str) -> list:
    """Faits : `claim` et `valeur` traduits ; sources, termes `check`, numéro de phrase et `verified` repris tels quels de la source."""
    out = copy.deepcopy(faits)
    textes = [t for f in out for t in (str(f.get("claim", "")), str(f.get("valeur", ""))) if t.strip()]
    uniques = list(dict.fromkeys(textes))
    tr = dict(zip(uniques, traducteur(uniques))) if uniques else {}
    for f in out:
        for k in ("claim", "valeur"):
            v = str(f.get(k, ""))
            if v.strip():
                f[k] = localiser_ecran(tr[v].strip(), langue) if k == "valeur" else tr[v].strip()
    return out


def adapter_publication(pub: dict, traducteur: Traducteur, langue: str, chaine_id: str, titre_traduit: str | None = None) -> dict:
    """Publication : titre, description (sans la ligne de hashtags, refaite), tags, question traduits ; `langue`, `chaine_id`, `contenu_ia` fixés."""
    lg = langues.langue_de(langue)
    lignes = [l for l in str(pub.get("description", "")).split("\n")]
    corps = [l for l in lignes if l.strip() and not _ligne_de_hashtags(l) and not seo.a_bloc_mots_cles(l)]
    tags = [t for t in (pub.get("tags") or []) if isinstance(t, str) and t.strip()]
    textes = [str(pub.get("titre", ""))] + corps + tags + ([str(pub["question_commentaires"])] if pub.get("question_commentaires") else [])
    uniques = list(dict.fromkeys(t for t in textes if t.strip()))
    tr = dict(zip(uniques, traducteur(uniques))) if uniques else {}
    titre = (titre_traduit or tr.get(str(pub.get("titre", "")), "")).strip()[:70]
    tags_t = list(dict.fromkeys(tr[t].strip().lower() if len(tr[t].split()) < 4 else tr[t].strip() for t in tags))
    desc_corps = [re.sub(r"^(Vidéo complète)", langues.libelle(lg, "video_complete"), tr[l].strip()) for l in corps]
    hashtags = [h for h in (seo.hashtag(t) for t in tags_t) if h][:12]
    description = "\n\n".join(desc_corps)
    if hashtags:
        description += "\n\n" + " ".join(dict.fromkeys(hashtags))
    question = tr.get(str(pub.get("question_commentaires", "")), langues.libelle(lg, "question_defaut")).strip()
    return {"titre": titre, "description": description, "tags": tags_t[:15], "question_commentaires": question,
            "langue": lg, "contenu_ia": True, "chaine_id": chaine_id}


def _ligne_de_hashtags(l: str) -> bool:
    mots = l.split()
    return bool(mots) and all(m.startswith("#") for m in mots)
