"""Référencement YouTube : hashtags, bloc de mots-clés, description des Shorts, repères de variété des titres.

Règle du propriétaire (8 nov. 2026) : dans chaque description, le MAXIMUM de hashtags pertinents (une dizaine, 15 au plus : au-delà
YouTube les ignore TOUS) et un bloc de mots-clés. Le rédacteur les écrit (voir writer/CONSIGNES.md) ; ce module les COMPLÈTE à la
publication s'ils manquent, pour qu'aucune vidéo ne parte avec 3 hashtags et sans mots-clés.

Aucune mention d'IA, de loi ou d'avertissement n'est jamais ajoutée ici (Cap éditorial du 4 novembre 2026).
Bibliothèque standard seulement.
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langues  # noqa: E402  (libellés et mots vides par langue ; le français reste le comportement historique)

HASHTAGS_MAX = 15       # au-delà, YouTube ignore tous les hashtags de la description
HASHTAGS_CIBLE = 12     # on vise une dizaine
MOTS_CLES_MAX_CAR = 420
TITRE_SHORT_IDEAL = 50  # un titre de Short court se lit en entier
TITRE_SHORT_MAX = 60

# Hashtag = # puis lettres/chiffres, mais pas uniquement des chiffres (« #1 » n'en est pas un pour YouTube).
RE_HASHTAG = re.compile(r"(?<![\w&#/])#(?!\d+\b)\w+", re.UNICODE)
# Mentions interdites dans le texte public (cap éditorial) : voix de synthèse, IA, avertissements.
RE_MENTION_INTERDITE = re.compile(
    r"voix de synth[èe]se|synth[ée]tique|intelligence artificielle|g[ée]n[ée]r[ée]e? par (?:une? )?(?:ia|intelligence)|"
    r"contenu (?:r[ée]alis[ée]|cr[ée][ée]|assist[ée]) .{0,20}\bia\b|r[ée]alis[ée] avec l.aide d.une ia|\bcontenu ia\b|"
    r"ceci n.est pas un conseil|pas un conseil (?:financier|en investissement)|je ne garantis",
    re.IGNORECASE)

# Mots vides : ni dans les hashtags tirés d'un titre, ni dans les mots-clés.
_VIDES = set("le la les l un une des du de d et ou où a à au aux en dans sur sous par pour avec sans ce cet cette ces son sa ses leur leurs "
             "qui que quoi dont est sont être avoir fait comment pourquoi quand combien quel quelle pas plus très il elle ils elles on nous "
             "vous je tu y se s qu n m t c ne mais donc car si ton ta tes cest jai voici voila tout tous toute toutes faire".split())


# Mots trop banals pour faire un hashtag utile.
_GENERIQUES = set("calcul calculs exemple jours jour chose choses fois voici vraiment gagner argent-gagner idee idées idee".split())


def _sans_accent(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def hashtag(mot: str) -> str | None:
    """« petit boulot » -> #PetitBoulot ; None si le résultat n'est pas un hashtag valable (vide, que des chiffres, plus de 30 caractères)."""
    morceaux = [m for m in re.findall(r"[\w]+", mot.replace("’", " ").replace("'", " "), re.UNICODE) if len(m) > 1 or m.isdigit()]
    if not morceaux:
        return None
    h = "".join(m[:1].upper() + m[1:] for m in morceaux)
    if h.isdigit() or len(h) > 30 or len(h) < 3:
        return None
    return "#" + h


def hashtags_du_texte(texte: str) -> list[str]:
    """Hashtags du texte, sans doublon (casse et accents ignorés), dans l'ordre d'apparition."""
    vus, sortie = set(), []
    for m in RE_HASHTAG.findall(texte or ""):
        cle = _sans_accent(m).lower()
        if cle not in vus:
            vus.add(cle)
            sortie.append(m)
    return sortie


def limiter_hashtags(texte: str, maximum: int = HASHTAGS_MAX) -> str:
    """Supprime les hashtags au-delà du `maximum`-ième (distinct) : au-delà de 15, YouTube les ignorerait tous."""
    gardes: list[str] = []

    def ok(m: re.Match) -> str:
        cle = _sans_accent(m.group(0)).lower()
        if cle in gardes:
            return m.group(0)
        if len(gardes) < maximum:
            gardes.append(cle)
            return m.group(0)
        return ""
    return re.sub(r" {2,}", " ", RE_HASHTAG.sub(ok, texte or "")).replace(" \n", "\n")


def mots_cles(titre: str, tags: list[str], n: int = 12, langue: str = "fr") -> list[str]:
    """Mots-clés à afficher : les tags du rédacteur d'abord, puis les mots utiles du titre (mots vides de la langue de la chaîne)."""
    vides = _VIDES if langues.langue_de(langue) == "fr" else _VIDES | langues.mots_vides(langue)
    sortie: list[str] = []
    vus: set[str] = set()

    def ajouter(m: str) -> None:
        m = m.strip()
        cle = _sans_accent(m).lower()
        if m and cle not in vus and len(sortie) < n:
            vus.add(cle)
            sortie.append(m)
    for t in tags or []:
        ajouter(t)
    for w in re.findall(r"[\w]+", titre or "", re.UNICODE):
        if w.lower() not in vides and len(w) > 3 and not w.isdigit():
            ajouter(w.lower())
    return sortie


def bloc_mots_cles(titre: str, tags: list[str], langue: str = "fr") -> str:
    mots = mots_cles(titre, tags, langue=langue)
    etiquette = langues.libelle(langue, "mots_cles")
    sep = " : " if langues.langue_de(langue) == "fr" else ": "
    ligne = etiquette + sep + ", ".join(mots)
    while len(ligne) > MOTS_CLES_MAX_CAR and len(mots) > 3:
        mots.pop()
        ligne = etiquette + sep + ", ".join(mots)
    return ligne


_RE_BLOC_MOTS_CLES = re.compile(r"^\s*(?:🔎\s*)?(?:mots[- ]cl[ée]s|keywords?|palabras clave|palavras[- ]chave|stichw[öo]rter)\s*:", re.IGNORECASE | re.MULTILINE)


def a_bloc_mots_cles(texte: str) -> bool:
    return bool(_RE_BLOC_MOTS_CLES.search(texte or ""))


def hashtags_a_ajouter(deja: list[str], tags: list[str], titre: str, chaine: list[str], cible: int, maximum: int,
                       reserves: list[str] | None = None) -> list[str]:
    """Hashtags à ajouter pour atteindre `cible` au total, sans dépasser `maximum`. Priorité : tags du rédacteur, mots du titre, hashtags de la chaîne.
    `reserves` (ex. #Shorts) sont comptés dans le total mais ajoutés en dernier."""
    vus = {_sans_accent(h).lower() for h in deja}
    reserves = [h for h in (reserves or []) if _sans_accent(h).lower() not in vus]
    place = min(cible, maximum) - len(deja) - len(reserves)
    sortie: list[str] = []
    mots_titre = [w for w in mots_cles(titre, [], 8) if len(w) >= 5 and w not in _GENERIQUES]
    candidats = [hashtag(t) for t in (tags or [])] + [hashtag(w) for w in mots_titre] + list(chaine or [])
    for h in candidats:
        if not h or len(sortie) >= place:
            continue
        cle = _sans_accent(h).lower()
        if cle in vus:
            continue
        vus.add(cle)
        sortie.append(h)
    return sortie + reserves


def completer_hashtags(texte: str, tags: list[str], titre: str, *, chaine: list[str] | None = None, reserves: list[str] | None = None,
                       cible: int = HASHTAGS_CIBLE, maximum: int = HASHTAGS_MAX) -> str:
    """Ligne de hashtags à poser en fin de description ('' si le texte en a déjà assez)."""
    deja = hashtags_du_texte(texte)
    ajout = hashtags_a_ajouter(deja, tags, titre, chaine or [], cible, maximum, reserves)
    return " ".join(ajout)


def description_short(accroche: str, titre_long: str, url_long: str | None, question: str, tags: list[str], hashtags_long: list[str], langue: str = "fr") -> str:
    """Description d'un Short extrait d'un long : accroche (mot-clé en tête), lien vers le long, question, mots-clés, hashtags du long."""
    lien = url_long or titre_long
    lignes = [accroche.strip(), "", f"▶ {langues.libelle(langue, 'video_complete')} : {lien}"]
    if question and question.strip():
        lignes += ["", question.strip()]
    mots = bloc_mots_cles(accroche + " " + titre_long, tags, langue)
    lignes += ["", mots]
    base = "\n".join(lignes)
    nouveaux = completer_hashtags(base + "\n" + " ".join(hashtags_long), tags, accroche + " " + titre_long,
                                  chaine=[], reserves=["#Shorts"])
    ligne_h = " ".join(hashtags_long + ([nouveaux] if nouveaux else []))
    return base + ("\n\n" + limiter_hashtags(ligne_h, HASHTAGS_MAX) if ligne_h.strip() else "")


def relier_au_long(desc: str, url_long: str | None) -> str:
    """Quand le long a été envoyé, remplace son titre par son adresse dans la ligne « ▶ Vidéo complète : … » d'un Short (sans effet si déjà fait)."""
    if not url_long:
        return desc
    return re.sub(r"(▶ (?:Vidéo complète|Full video|Vídeo completo|Ganzes Video) : )[^\n]*", lambda m: m.group(1) + url_long, desc, count=1)


def tags_du_short(tags_long: list[str], accroche: str, n: int = 15) -> list[str]:
    """Tags d'un Short : ceux du long, puis les mots utiles de l'accroche (500 caractères au plus pour YouTube : géré par le publieur)."""
    return mots_cles(accroche, tags_long, n)


def forme_du_titre(titre: str) -> str:
    """Famille de forme d'un titre, pour ne jamais enchaîner deux titres identiques : nombre-liste, question, comparaison, négation, citation, affirmation…"""
    t = (titre or "").strip().lower()
    if re.match(r"^\d+\s", t):
        return "liste"
    if t.endswith("?") or re.match(r"^(comment|pourquoi|combien|est-ce|qui|quel|quelle|que|et si|how|why|what|who|which|can|is|are|do|does|should|would)\b", t):
        return "question"
    if re.search(r"\b(vs|contre|ou)\b", t) or " plutôt que " in t:
        return "comparaison"
    if re.match(r"^(arr[êe]te|ne |n'|jamais|stop|fini)", t):
        return "interdit"
    if re.match(r"^(le |la |les |l'|un |une |ce |cette |ton |ta |tes |du |des )", t):
        return "affirmation"
    if re.search(r"\d", t):
        return "chiffre"
    return "autre"


def forme_identique_de_suite(titres: list[str], maximum: int = 1) -> list[tuple[int, str]]:
    """Positions où plus de `maximum` titres consécutifs ont la même forme (liste vide = OK)."""
    mauvais, serie, prec = [], 0, None
    for i, t in enumerate(titres):
        f = forme_du_titre(t)
        serie = serie + 1 if f == prec else 1
        prec = f
        if serie > maximum:
            mauvais.append((i, f))
    return mauvais
