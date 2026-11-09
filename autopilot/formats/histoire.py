"""Format « Histoire » : récits « incroyables mais vrais », monde entier. Crochets du moteur (voir chaines.HOOKS_FORMAT).

consignes(profil)                          -> texte ajouté à `stock.py besoin` (clé `consignes_format`)
valider_episode(ep, faits, pub, profil)    -> (erreurs, avertissements) en plus des contrôles standard de valider.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "long"))
import longlib  # noqa: E402

ANNEE_MAX = 2026
# Une quantité (« en 3000 ans ») ou une date avant J.-C. (« en 3000 av. J.-C. ») n'est pas une année du futur.
_UNITES = ("ans?|années?|jours?|mois|siècles?|heures?|minutes?|secondes?|mètres?|kilomètres?|km|kg|tonnes?|hommes?|soldats?|"
           "personnes?|habitants?|morts?|navires?|bateaux|fois|euros?|francs?|dollars?|pas|pieds?|lieues?|tours?|coups?|mots?|pièces?|"
           "chevaux|cavaliers?|marins?|ouvriers?|esclaves?|enfants?|familles?|villages?|maisons?|livres?|litres?|kilos?")
_NON_ANNEE = (r"(?!\s+(?:(?:" + _UNITES + r")\b|av\.?\s*J|avant\s+(?:J\b|notre\b)))")
_MOIS = "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre"
RE_ANNEE = re.compile(r"\b(?:en|vers|depuis|avant|après|jusqu['’]en|dès|l['’]an|" + _MOIS + r")\s+(\d{3,4})\b" + _NON_ANNEE, re.I)
LONG_MAX = 40  # caractères d'un repère de frise (date ou label) : au-delà, le texte déborde de la scène
RE_POLITIQUE = re.compile(r"\b(présidents?|présidentes?|premiers? ministres?|élections?|dirigeants?|gouvernements?|ministres?)\b", re.I)
RE_VIOLENCE = re.compile(r"génocide|massacre|extermin|torture|décapit|démembr|éventr|crucifi|holocauste|shoah", re.I)
RE_RELIGION = re.compile(r"\b(dieux?|religions?|églises?|islam|bible|coran|papes?|prophètes?|croisades?)\b", re.I)
RE_PRUDENCE = re.compile(r"légende|selon la tradition|on raconte|dit-on|on ne sait pas|peut-être|d['’]après", re.I)

CONSIGNES = """Chaîne HISTOIRE : un long de 8 à 12 minutes (4 à 8 chapitres), un récit « incroyable mais vrai », monde entier, toute époque avant 1945 pour les personnes au pouvoir.
Structure : chapitre 1 = accroche (la scène la plus étonnante, tout de suite) ; puis le contexte ; le tournant ; la conséquence ; ce qu'on en retient.
Écris comme à un enfant de dix ans : mots simples, phrases courtes (160 caractères au plus). Tu es un conteur, pas un professeur.
Vérité : chaque date, chaque nom, chaque chiffre a 2 sources de 2 sites différents dans faits.json. Mets "statut": "incertain" ou "legende" pour un fait discuté et dis-le à voix haute
(« selon la tradition », « on raconte », « on ne sait pas »). Une légende est annoncée comme légende. Jamais de jugement de valeur sur un peuple ou un groupe.
Interdit : violence décrite en détail, génocides et massacres, dirigeants après 1945, religion comme sujet, promesse de gain.
Visuel (thème "parchemin") : en plus des scènes habituelles, utilise `frise` (params {"reperes":[{"date","label","accent"?}] 2 à 6}), `carte` (params {"lieux":[{"nom","x","y"}] 2 à 5, x et y de 0 à 100, schéma sans échelle})
et `citation` (params {"texte","auteur","date"?}) : une citation doit avoir une source dans faits.json sur sa phrase. Pas de photo, pas d'image d'archive.
Format : propose UNIQUEMENT des sujets longs ("format": "long") pour cette chaîne ; les Shorts sont découpés du long, jamais proposés seuls.
Découpe : marque jusqu'à 3 segments `short` (les moments les plus forts) pour les Shorts."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def _offsets(ep: dict) -> list[int]:
    out, n = [], 0
    for ch in ep["chapitres"]:
        out.append(n)
        n += len(ch.get("phrases") or [])
    return out


def _vide(v) -> bool:
    return not isinstance(v, str) or not v.strip()


def _scenes(ep: dict, couvertes: set[int]) -> list[str]:
    err: list[str] = []
    for c, (off, ch) in enumerate(zip(_offsets(ep), ep["chapitres"]), 1):
        for s in ch.get("scenes") or []:
            t, p = s.get("type"), s.get("params") or {}
            nom = f"chapitre {c}, scène {t}"
            if t == "frise":
                r = p.get("reperes")
                if not isinstance(r, list) or not 2 <= len(r) <= 6 or any(not isinstance(x, dict) or _vide(x.get("date")) or _vide(x.get("label")) for x in r):
                    err.append(f"{nom} : « reperes » = 2 à 6 repères avec « date » et « label »")
                else:
                    for x in r:
                        for k in ("date", "label"):
                            if len(x[k].strip()) > LONG_MAX:
                                err.append(f"{nom} : « {k} » de {len(x[k].strip())} caractères, {LONG_MAX} au plus (« {x[k].strip()[:20]}… »)")
            elif t == "carte":
                l = p.get("lieux")
                ok = isinstance(l, list) and 2 <= len(l) <= 5 and all(
                    isinstance(x, dict) and not _vide(x.get("nom")) and all(isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool) and 0 <= x[k] <= 100 for k in ("x", "y")) for x in l)
                if not ok:
                    err.append(f"{nom} : « lieux » = 2 à 5 lieux avec « nom », « x » et « y » entre 0 et 100")
            elif t == "citation":
                if not isinstance(p.get("texte"), str) or not 10 <= len(p["texte"]) <= 220 or _vide(p.get("auteur")):
                    err.append(f"{nom} : « texte » de 10 à 220 caractères et « auteur » obligatoires")
                elif not isinstance(s.get("phrase"), int) or off + s["phrase"] not in couvertes:
                    err.append(f"{nom} : une citation doit avoir une source (un fait de faits.json sur sa phrase)")
    return err


def valider_episode(ep: dict, faits, pub, profil: dict) -> tuple[list[str], list[str]]:
    if not isinstance(ep, dict) or not isinstance(ep.get("chapitres"), list):
        return [], []
    try:
        offs = _offsets(ep)
        plat = longlib.flatten(ep)
    except (KeyError, TypeError):
        return [], []  # forme illisible : valider.py l'a déjà signalée
    err: list[str] = []
    faits = faits if isinstance(faits, list) else []
    couvertes = {f["phrase"] for f in faits if isinstance(f, dict) and isinstance(f.get("phrase"), int)}
    for c, (off, ch) in enumerate(zip(offs, ep["chapitres"]), 1):
        n = len(ch.get("phrases") or [])
        if not any(off < ph <= off + n for ph in couvertes):
            err.append(f"chapitre {c} : aucun fait sourcé (faits.json) ne couvre ce chapitre")
    titres = [("titre", str(ep.get("titre", "")))] + [(f"titre du chapitre {c}", str(ch.get("titre", ""))) for c, ch in enumerate(ep["chapitres"], 1)]
    for lieu, t in titres:
        if RE_RELIGION.search(t):
            err.append(f"{lieu} : la religion n'est pas un sujet de cette chaîne")
        if RE_VIOLENCE.search(t):
            err.append(f"{lieu} : violence ou crime de masse interdit")
    for i, p in enumerate(plat["phrases"], 1):
        for m in RE_ANNEE.finditer(p):
            a = int(m.group(1))
            if a > ANNEE_MAX:
                err.append(f"phrase {i} : l'année {a} est dans le futur")
            if a >= 1946 and RE_POLITIQUE.search(p):
                err.append(f"phrase {i} : dirigeants et politique après 1945 interdits")
        m = RE_VIOLENCE.search(p)
        if m:
            err.append(f"phrase {i} : « {m.group(0)} » (violence ou crime de masse) interdit")
    phrases = plat["phrases"]
    for k, f in enumerate(faits, 1):
        if isinstance(f, dict) and f.get("statut", "etabli") != "etabli":
            ph = f.get("phrase")
            if isinstance(ph, int) and 1 <= ph <= len(phrases) and not RE_PRUDENCE.search(phrases[ph - 1]):
                err.append(f"fait {k} ({f.get('statut')}) : la phrase {ph} doit dire la prudence à voix haute (« selon la tradition », « on raconte »…)")
    err += _scenes(ep, couvertes)
    return err, []
