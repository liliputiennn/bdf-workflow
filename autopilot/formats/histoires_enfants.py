"""Format « Histoires pour enfants » : petites histoires ORIGINALES (3 à 7 ans), lues d'une voix douce et claire, illustrées par des scènes dessinées par le code.

Un Short = une mini-histoire (30 à 55 s) ; un long (le week-end) = une histoire de 3 à 8 minutes.

Licences : voix = Qwen3-TTS CustomVoice (Apache-2.0, voix intégrée) ; images = formes géométriques dessinées ici (Pillow), aucune image externe, rien à créditer ;
fond sonore = boîte à musique synthétisée par le code (synth.py). Histoires écrites par le rédacteur : originales (aucun personnage, marque ou conte sous droits) ;
un conte traditionnel du domaine public n'est accepté qu'avec sa source (`origine`).

Crochets du moteur : `consignes`, `valider_episode`, `script_voix`, `rendre`, `miniature`. `CONTROLES_STANDARD = False`.
episode.json : {id, titre, chaine, theme, video: "short"|"long", format_contenu: "histoires_enfants", pour_enfants: true,
                origine: "originale" | {conte, source: https...}, lieu, situation, lecon,
                personnage: {nom, type, couleur}, ami?: {nom, type, couleur},
                scenes: [{decor, phrases: [...], mouvement?, avec?: ["perso","ami"]}], miniature: {texte_haut, gros}}
La dernière phrase de la dernière scène EST la petite leçon (`lecon`).
"""
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import commun, rendu, synth
from .musique_enfants import RE_MOT_INTERDIT, RE_URL

CONTROLES_STANDARD = False
LUFS = -16.0
DUREE_S = {"short": (30, 55), "long": (180, 480)}
MOTS = {"short": (60, 125), "long": (420, 1100)}
SCENES = {"short": (3, 6), "long": (6, 30)}
MAX_MOTS_PHRASE = 14
PAUSE_PHRASE_S = 0.4
PAUSE_SCENE_S = 0.9
VITESSE_VOIX = 0.95
FIN_S = 1.5
FONDU_S = 0.5

DECORS = ("jardin", "foret", "maison", "plage", "ferme", "montagne", "neige", "nuit")
ANIMAUX = ("lapin", "chat", "ours", "souris", "oiseau", "grenouille", "herisson", "escargot")
COULEURS = {"orange": "#F59B42", "brun": "#A8714A", "gris": "#A9B4C2", "blanc": "#F4F1EA", "jaune": "#F7D44A", "rose": "#F29BBB", "bleu": "#6FB6F2",
            "vert": "#6CC070", "beige": "#E4C79A"}
MOUVEMENTS = ("marche", "saute", "balance", "repose")

STYLE = {"encre": "#2F2A55", "accent": "#E8456F", "panneau": "#FFFDF5", "doux": "#7C77A8"}

RE_EFFRAYANT = re.compile(r"\bloups?\b|sorci[èe]r|\bogres?\b|dragon|orage|tonnerre|griffe|\bmord|\bcris?\b|hurl|poison|pi[èe]ge|enferm|disparu|abandonn|seul au monde|"
                          r"punition|gronde|bagar|monstr|squelette|araign|serpent|cachot|\bnoyer|se noie", re.I)
RE_SOUS_DROITS = re.compile(r"disney|pixar|dreamworks|marvel|pok[ée]mon|pikachu|mickey|minnie|winnie|peppa|pat.?patrouille|paw patrol|reine des neiges|frozen|elsa|"
                            r"nemo|simba|mario|sonic|bluey|baby shark|spiderman|batman|superman|harry potter|shrek|toy story|cars|tchoupi|trotro|petit ours brun|"
                            r"babar|ast[ée]rix|tintin|barbie|hello kitty|dora|peter pan|bambi|dumbo|la petite sir[èe]ne|cro[ée]e", re.I)
# Contes traditionnels (domaine public) : refusés comme histoire « originale », permis avec `origine` = {conte, source}.
RE_CONTE_CLASSIQUE = re.compile(r"cendrillon|blanche.?neige|petit chaperon|belle au bois|raiponce|pinocchio|trois petits cochons|boucle d.or|chat bott[ée]|petit poucet|"
                                r"barbe.?bleue|la belle et la b[êe]te|alice au pays", re.I)

CONSIGNES = """Chaîne HISTOIRES POUR ENFANTS (3 à 7 ans) : tu écris de petites histoires ORIGINALES, lues d'une voix douce et claire, illustrées par des scènes dessinées par le code (personnages simples, décors colorés, sous-titres). Un Short (`video`: "short") = une mini-histoire de 60 à 125 mots, 3 à 6 scènes ; un long (`video`: "long", pour le week-end) = une histoire de 420 à 1100 mots, 6 à 30 scènes.
Une histoire = un petit personnage (animal), un lieu, une petite situation, un problème tout simple qui se règle gentiment, puis une PETITE LEÇON DOUCE (partager, aider, essayer encore, dire merci, ranger, attendre son tour, être poli, aimer la nature…). La leçon est la DERNIÈRE phrase de l'histoire, recopiée à l'identique dans le champ `lecon`.
Écris comme on parle à un enfant : mots simples et courts, phrases courtes (14 mots au plus), sujet-verbe-complément, une idée par phrase, peu d'adjectifs. Pas de chiffres (écris « trois » en lettres). Au plus trois points d'exclamation dans toute l'histoire. Une phrase est lue d'une traite : pas de parenthèses ni de tirets.
Jamais de peur : aucun loup, sorcière, ogre, monstre, orage, noir menaçant, danger, cri, bagarre, mort, punition, objet dangereux, personne perdue ou abandonnée. Le « problème » est doux (un ami a faim, un jouet est cassé, la chambre est en désordre, il pleut et on veut sortir) et tout finit bien.
ORIGINALE : aucun personnage, aucune marque, aucune chanson ni aucun conte sous droits (pas de Disney, de Pokémon, de Peppa…). `origine` vaut "originale". Seul un conte traditionnel du DOMAINE PUBLIC peut être raconté avec tes mots, et alors `origine` = {"conte": "le titre", "source": "https://… page qui le publie"}.
Chaque histoire est DIFFÉRENTE des précédentes : un autre animal (`personnage.type`), un autre `lieu`, une autre `situation` (une phrase de 6 à 25 mots qui résume), une autre leçon. Deux histoires qui se ressemblent sont refusées.
Format des champs : `lieu` et `scenes[].decor` : jardin, foret, maison, plage, ferme, montagne, neige ou nuit (décor calme) ; `personnage` / `ami` (facultatif, d'un autre animal) : {"nom": "Lila", "type": lapin, chat, ours, souris, oiseau, grenouille, herisson ou escargot, "couleur": orange, brun, gris, blanc, jaune, rose, bleu, vert ou beige} ; chaque scène : `phrases` (1 à 5), `mouvement` facultatif (marche, saute, balance, repose), `avec` facultatif (["perso"], ["ami"] ou les deux) ; au moins une scène se passe dans le `lieu`. Une scène = un petit groupe de phrases qui vont ensemble (un moment de l'histoire).
Titre : « Histoire pour enfants : … » ou « Conte … » (70 caractères au plus). Description : de quoi parle l'histoire, la phrase « Histoire originale pour les enfants de 3 à 7 ans. » (sans la changer), une ligne disant que la voix et les images sont créées avec des outils informatiques ; AUCUN lien, aucun appel à s'abonner. `publication.json` : `contenu_ia` vrai. La chaîne est déclarée « conçue pour les enfants » : les commentaires sont désactivés par YouTube, ne cherche pas à en provoquer."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def type_video(ep: dict) -> str:
    return "long" if ep.get("video") == "long" else "short"


# ---------------------------------------------------------------- texte
def _phrases(ep: dict) -> list[str]:
    return [str(p).strip() for s in ep["scenes"] for p in s["phrases"]]


def _debuts_scenes(ep: dict) -> list[int]:
    """Indice (0 = première) de la première phrase de chaque scène."""
    out, n = [], 0
    for s in ep["scenes"]:
        out.append(n)
        n += len(s["phrases"])
    return out


def script_voix(ep: dict) -> dict:
    ph = _phrases(ep)
    debuts = set(_debuts_scenes(ep))
    return {"phrases": ph, "pauses": {str(i + 1): (PAUSE_SCENE_S if i in debuts else PAUSE_PHRASE_S) for i in range(1, len(ph))},
            "vitesses": {str(i + 1): VITESSE_VOIX for i in range(len(ph))}}


# ---------------------------------------------------------------- ressemblance entre histoires
def _mots_utiles(s: str) -> set[str]:
    return {m for m in commun.norm(s).split() if len(m) > 3}


def ressemble(a: dict, b: dict) -> str | None:
    """Raison pour laquelle deux histoires se ressemblent trop, ou None."""
    pa, pb = a.get("personnage") or {}, b.get("personnage") or {}
    if pa.get("type") and pa.get("type") == pb.get("type") and a.get("lieu") and a.get("lieu") == b.get("lieu"):
        return f"même personnage ({pa['type']}) et même lieu ({a['lieu']})"
    if pa.get("nom") and commun.norm(pa["nom"]) == commun.norm(pb.get("nom", "")) and pa.get("type") == pb.get("type"):
        return f"même personnage ({pa['nom']} le {pa['type']})"
    sa, sb = _mots_utiles(str(a.get("situation", ""))), _mots_utiles(str(b.get("situation", "")))
    if sa and sb and len(sa & sb) / len(sa | sb) >= 0.5:
        return "situation presque identique"
    la, lb = commun.norm(str(a.get("lecon", ""))), commun.norm(str(b.get("lecon", "")))
    if la and la == lb:
        return "même leçon, mot pour mot"
    return None


def _autres_episodes(ep: dict, profil: dict) -> list[dict]:
    """Histoires déjà écrites de la même chaîne (hors celle-ci), pour comparer. Silencieux si le dossier est illisible."""
    out = []
    try:
        from autopilot import common
        for i in common.list_episodes(chaine=profil.get("id") or None):
            if i == ep.get("id"):
                continue
            o = common.read_json(common.ep_dir(i) / "episode.json", None)
            if isinstance(o, dict) and o.get("format_contenu") == "histoires_enfants":
                out.append(o)
    except Exception:
        return []
    return out


# ---------------------------------------------------------------- validation
def _perso_err(p, nom: str, err: list[str]) -> None:
    if not isinstance(p, dict):
        err.append(f"« {nom} » : {{nom, type, couleur}} obligatoire")
        return
    if not re.fullmatch(r"[A-ZÉÈÀ][a-zéèêëàâîïôùûç-]{1,11}", str(p.get("nom", ""))):
        err.append(f"« {nom}.nom » : un prénom simple (une majuscule, 12 lettres au plus)")
    if p.get("type") not in ANIMAUX:
        err.append(f"« {nom}.type » doit être l'un de : {', '.join(ANIMAUX)}")
    if p.get("couleur") not in COULEURS:
        err.append(f"« {nom}.couleur » doit être l'une de : {', '.join(COULEURS)}")


def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True, autres: list | None = None) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    v = type_video(ep)
    if ep.get("video") not in ("short", "long"):
        err.append("« video » doit valoir « short » ou « long »")
    if ep.get("pour_enfants") is not True:
        err.append("« pour_enfants » doit valoir true (chaîne déclarée « conçue pour les enfants »)")
    # --- origine : originale, ou conte du domaine public avec sa source
    o = ep.get("origine")
    if o == "originale":
        pass
    elif isinstance(o, dict) and str(o.get("conte", "")).strip():
        r = commun.url_valide(o.get("source")) if isinstance(o.get("source"), str) else "pas une adresse"
        if r:
            err.append(f"origine : conte traditionnel sans source valable ({r}) ; cite la page qui publie ce conte du domaine public")
        else:
            av.append("origine : conte traditionnel du domaine public, raconte-le avec tes mots et vérifie que sa version n'est pas protégée")
    else:
        err.append("« origine » doit valoir « originale » (ou {conte, source} pour un conte du domaine public)")
    # --- personnages, lieu, situation
    _perso_err(ep.get("personnage"), "personnage", err)
    pers, ami = ep.get("personnage"), ep.get("ami")
    if ami is not None:
        _perso_err(ami, "ami", err)
        if isinstance(ami, dict) and isinstance(pers, dict) and (ami.get("type") == pers.get("type") or ami.get("nom") == pers.get("nom")):
            err.append("« ami » doit être un autre animal, avec un autre prénom")
    if ep.get("lieu") not in DECORS:
        err.append(f"« lieu » doit être l'un de : {', '.join(DECORS)}")
    sit = str(ep.get("situation", ""))
    if not 6 <= len(sit.split()) <= 25:
        err.append("« situation » : une phrase de 6 à 25 mots qui résume l'histoire")
    # --- scènes
    sc = ep.get("scenes")
    if not isinstance(sc, list) or not sc:
        return err + ["« scenes » manque : liste de scènes {decor, phrases}"], av
    bon = True
    for k, s in enumerate(sc, 1):
        n = f"scène {k}"
        if not isinstance(s, dict) or s.get("decor") not in DECORS:
            err.append(f"{n} : « decor » doit être l'un de : {', '.join(DECORS)}")
            bon = False
            continue
        ph = s.get("phrases")
        if not isinstance(ph, list) or not 1 <= len(ph) <= 5 or not all(isinstance(p, str) and p.strip() for p in ph):
            err.append(f"{n} : 1 à 5 phrases (textes non vides)")
            bon = False
        if s.get("mouvement") not in (None, *MOUVEMENTS):
            err.append(f"{n} : « mouvement » parmi {', '.join(MOUVEMENTS)}")
        av_ = s.get("avec")
        if av_ is not None and (not isinstance(av_, list) or not av_ or any(x not in ("perso", "ami") for x in av_) or ("ami" in av_ and not isinstance(ami, dict))):
            err.append(f"{n} : « avec » = [\"perso\"], [\"ami\"] (si un ami existe) ou les deux")
    if not bon:
        return err, av
    if not SCENES[v][0] <= len(sc) <= SCENES[v][1]:
        err.append(f"{len(sc)} scène(s) : il en faut de {SCENES[v][0]} à {SCENES[v][1]} pour un {'Short' if v == 'short' else 'long'}")
    if ep.get("lieu") in DECORS and not any(s["decor"] == ep["lieu"] for s in sc):
        err.append("au moins une scène doit se passer dans le « lieu » de l'histoire")
    phrases = _phrases(ep)
    texte = " ".join(phrases)
    mots = len(texte.split())
    if not MOTS[v][0] <= mots <= MOTS[v][1]:
        err.append(f"{mots} mots : il en faut de {MOTS[v][0]} à {MOTS[v][1]} pour un {'Short' if v == 'short' else 'long'}")
    for i, p in enumerate(phrases, 1):
        if len(p.split()) > MAX_MOTS_PHRASE:
            err.append(f"phrase {i} : {len(p.split())} mots, {MAX_MOTS_PHRASE} au plus (phrases courtes pour les enfants)")
        if re.search(r"[()\[\]«»—–]", p):
            err.append(f"phrase {i} : ni parenthèses ni tirets ni guillemets (la voix lit d'une traite)")
        if max(len(w) for w in re.findall(r"[^\W\d_]+", p) or ["a"]) > 14:
            err.append(f"phrase {i} : un mot de plus de 14 lettres, choisis un mot plus simple")
    if texte.count("!") > 3:
        err.append("trois points d'exclamation au plus dans toute l'histoire (voix douce)")
    longs = [w for w in re.findall(r"[^\W\d_]+", texte) if len(w) > 11]
    if len(longs) > max(3, mots // 40):
        av.append(f"{len(longs)} mots longs ({', '.join(sorted(set(longs))[:5])}…) : simplifie pour des enfants de 3 à 7 ans")
    # --- leçon : dernière phrase
    lecon = str(ep.get("lecon", ""))
    if not 3 <= len(lecon.split()) <= 20:
        err.append("« lecon » : une petite phrase (3 à 20 mots) qui dit ce qu'on retient")
    elif commun.norm(lecon) != commun.norm(phrases[-1]):
        err.append("la dernière phrase de l'histoire doit être la leçon (« lecon »), recopiée à l'identique")
    # --- contenu : mots interdits, peur, droits, promesses
    tout = texte + " " + str(ep.get("titre", "")) + " " + sit + " " + lecon
    for rx, msg in ((RE_MOT_INTERDIT, "interdit sur une chaîne pour enfants (peur, violence, argent, marque, appel à s'abonner…)"),
                    (RE_EFFRAYANT, "peut effrayer un enfant : l'histoire doit rester douce"),
                    (RE_SOUS_DROITS, "personnage, marque ou conte sous droits : l'histoire doit être originale")):
        m = rx.search(tout)
        if m:
            err.append(f"histoire ou titre : « {m.group(0)} » {msg}")
    if o == "originale":
        m = RE_CONTE_CLASSIQUE.search(tout)
        if m:
            err.append(f"histoire ou titre : « {m.group(0)} » est un conte traditionnel : mets `origine` = {{conte, source}} avec la page qui le publie, ou invente une histoire")
    if commun.RE_PROMESSE.search(tout):
        err.append("promesse interdite")
    if commun.chiffres(texte + " " + str(ep.get("titre", "")) + " " + str(ep.get("miniature", ""))):
        err.append("pas de chiffres dans l'histoire, le titre ni la miniature (écris les nombres en lettres)")
    if isinstance(pers, dict) and pers.get("nom") and pers["nom"] not in texte:
        av.append(f"le prénom « {pers['nom']} » n'apparaît jamais dans l'histoire")
    titre = str(ep.get("titre", ""))
    if not re.search(r"histoire|conte", commun.norm(titre)):
        err.append("titre : doit contenir « histoire » ou « conte »")
    if len(titre) > 70:
        err.append("titre : 70 caractères au plus")
    # --- publication
    if isinstance(pub, dict):
        desc = str(pub.get("description", ""))
        if RE_URL.search(desc):
            err.append("description : aucun lien sur une chaîne pour enfants")
        m = RE_MOT_INTERDIT.search(desc)
        if m:
            err.append(f"description : « {m.group(0)} » interdit (appel à s'abonner, marque, argent…)")
        if "histoire originale" not in commun.norm(desc) and "conte" not in commun.norm(desc):
            err.append("description : la mention « Histoire originale pour les enfants de 3 à 7 ans. » est obligatoire")
        if pub.get("contenu_ia") is not True:
            err.append("publication.contenu_ia doit valoir true (voix et images créées par des outils informatiques)")
        if pub.get("langue") not in (None, "fr"):
            err.append("publication.langue doit valoir « fr »")
    else:
        err.append("publication.json illisible")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not 1 <= len(str(mini.get("gros", "")).split()) <= 3:
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (1 à 3 mots) obligatoires")
    # --- deux histoires ne doivent pas se ressembler
    if not err:
        for o2 in (autres if autres is not None else _autres_episodes(ep, profil or {})):
            r = ressemble(ep, o2)
            if r:
                err.append(f"cette histoire ressemble trop à « {o2.get('titre', o2.get('id', '?'))} » : {r} ; change de personnage, de lieu et de situation")
                break
    return err, av


# ---------------------------------------------------------------- dessin : couleurs et personnages
def _mix(c: str, vers: tuple[int, int, int], a: float) -> str:
    r = rendu.hex_rgb(c)
    return "#%02X%02X%02X" % tuple(int(r[i] * (1 - a) + vers[i] * a) for i in range(3))


def _clair(c: str, a: float = 0.45) -> str:
    return _mix(c, (255, 255, 255), a)


def _sombre(c: str, a: float = 0.25) -> str:
    return _mix(c, (40, 30, 60), a)


_cache_sprites: dict = {}


def _sprite(type_: str, couleur: str, s: int, clignement: bool, miroir: bool = False) -> Image.Image:
    """Personnage de face dessiné en formes simples (supersampling x2). Canvas carré de 5 s x 5 s, pieds sur le bas (à 0,25 s du bord)."""
    cle = (type_, couleur, s, clignement, miroir)
    if cle in _cache_sprites:
        return _cache_sprites[cle]
    k = 2
    u = s * k
    taille = int(5 * u)
    cx, by = taille / 2, taille - 0.25 * u
    im = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = COULEURS[couleur]
    cl, cd, encre, rose = _clair(c), _sombre(c), STYLE["encre"], "#FF9DB8"

    def el(a, b, c2, d2, fill, outline=None, w=0):
        d.ellipse((cx + a * u, by + b * u, cx + c2 * u, by + d2 * u), fill=fill, outline=outline, width=w)

    def poly(pts, fill):
        d.polygon([(cx + x * u, by + y * u) for x, y in pts], fill=fill)

    def ligne(pts, fill, w):
        d.line([(cx + x * u, by + y * u) for x, y in pts], fill=fill, width=max(1, int(w * u)), joint="curve")

    if type_ == "escargot":
        el(-1.5, -0.75, 1.0, 0.0, cl)  # pied long
        el(0.45, -1.75, 1.45, -0.45, cl)  # tête
        ligne([(0.85, -1.6), (0.75, -2.5)], cl, 0.12)
        ligne([(1.15, -1.55), (1.3, -2.4)], cl, 0.12)
        el(0.62, -2.7, 0.9, -2.4, encre)
        el(1.16, -2.6, 1.44, -2.3, encre)
        el(-1.35, -2.3, 0.35, -0.55, c)  # coquille et spirale
        el(-1.0, -1.95, 0.0, -0.9, _clair(c, 0.3), cd, int(0.07 * u))
        el(-0.72, -1.65, -0.28, -1.2, cd)
        yeux = [(0.82, -1.15), (1.18, -1.15)]
        for ex, ey in yeux:
            if clignement:
                ligne([(ex - 0.08, ey), (ex + 0.08, ey)], encre, 0.05)
            else:
                el(ex - 0.07, ey - 0.07, ex + 0.07, ey + 0.07, encre)
        d.arc((cx + 0.78 * u, by - 1.2 * u, cx + 1.22 * u, by - 0.78 * u), 20, 160, fill=encre, width=max(2, int(0.05 * u)))
    else:
        # --- éléments derrière le corps
        if type_ == "herisson":
            for i in range(15):
                a = math.pi * (0.95 + 1.1 * i / 14)
                px, py = 0.95 * math.cos(a) * 1.15, -1.0 + 1.1 * math.sin(a)
                poly([(px - 0.28 * math.sin(a), py + 0.28 * math.cos(a)), (px * 1.3, py * 1.0 + (py + 1.0) * 0.35), (px + 0.28 * math.sin(a), py - 0.28 * math.cos(a))], cd)
            el(-1.15, -2.2, 1.15, 0.0, c)
        if type_ == "lapin":
            el(0.8, -0.9, 1.35, -0.35, "#FFFFFF")  # queue
            for sx in (-1, 1):
                el(sx * 0.4 - 0.25, -4.3, sx * 0.4 + 0.25, -2.3, c)
                el(sx * 0.4 - 0.13, -3.95, sx * 0.4 + 0.13, -2.5, "#FFC1D6")
        if type_ == "chat":
            ligne([(0.8, -0.5), (1.5, -0.7), (1.8, -1.4), (1.6, -2.0)], c, 0.28)
            for sx in (-1, 1):
                poly([(sx * 0.78, -2.45), (sx * 0.72, -3.55), (sx * 0.12, -2.85)], c)
                poly([(sx * 0.62, -2.65), (sx * 0.6, -3.2), (sx * 0.3, -2.8)], "#FFC1D6")
        if type_ == "ours":
            for sx in (-1, 1):
                el(sx * 0.85 - 0.28, -3.1, sx * 0.85 + 0.28, -2.55, c)
                el(sx * 0.85 - 0.14, -2.98, sx * 0.85 + 0.14, -2.7, cl)
        if type_ == "souris":
            ligne([(-0.9, -0.3), (-1.6, -0.1), (-2.0, -0.7), (-2.3, -0.6)], "#F7B6C8", 0.1)
            for sx in (-1, 1):
                el(sx * 0.7 - 0.45, -3.4, sx * 0.7 + 0.45, -2.5, c)
                el(sx * 0.7 - 0.3, -3.25, sx * 0.7 + 0.3, -2.65, "#F7B6C8")
        if type_ == "grenouille":
            for sx in (-1, 1):
                el(sx * 0.45 - 0.35, -3.1, sx * 0.45 + 0.35, -2.4, c)
        if type_ == "oiseau":
            for dx, h in ((-0.2, 0.6), (0.0, 0.8), (0.2, 0.55)):
                el(dx - 0.1, -2.85 - h * 0.35, dx + 0.1, -2.7, cd)
        # --- corps, ventre, pieds, bras
        if type_ != "herisson":
            el(-0.95, -1.7, 0.95, 0.0, c)
        el(-0.55, -1.4, 0.55, -0.05, "#F2D3A5" if type_ == "herisson" else cl)
        for sx in (-1, 1):
            el(sx * 0.5 - 0.35, -0.25, sx * 0.5 + 0.35, 0.12, cd)
            el(sx * 1.0 - 0.22, -1.5, sx * 1.0 + 0.22, -0.75, c)
        # --- tête
        el(-0.85, -2.95, 0.85, -1.25, "#F2D3A5" if type_ == "herisson" else c)
        if type_ == "herisson":
            el(-0.7, -2.2, 0.7, -1.3, "#F2D3A5")
            el(-0.25, -1.95, 0.25, -1.65, encre)
        if type_ == "ours":
            el(-0.4, -2.0, 0.4, -1.4, cl)
        # --- visage
        yeux = [(-0.4, -2.2), (0.4, -2.2)]
        for ex, ey in yeux:
            if clignement:
                ligne([(ex - 0.13, ey + 0.1), (ex + 0.13, ey + 0.1)], encre, 0.06)
            else:
                el(ex - 0.13, ey - 0.05, ex + 0.13, ey + 0.27, encre)
                el(ex - 0.06, ey - 0.0, ex + 0.04, ey + 0.1, "#FFFFFF")
        for sx in (-1, 1):
            el(sx * 0.62 - 0.17, -1.95, sx * 0.62 + 0.17, -1.72, rose)
        if type_ not in ("oiseau", "herisson"):
            el(-0.1, -1.95, 0.1, -1.78, rose if type_ in ("lapin", "souris") else encre)
        if type_ == "oiseau":
            poly([(-0.22, -1.95), (0.22, -1.95), (0.0, -1.55)], "#F5A524")
            el(-0.75, -1.5, -0.2, -0.7, cd)
        else:
            d.arc((cx - 0.3 * u, by - 1.95 * u, cx + 0.3 * u, by - 1.45 * u), 20, 160, fill=encre, width=max(2, int(0.06 * u)))
        if type_ == "chat":
            for sx in (-1, 1):
                for dy in (-0.05, 0.1):
                    ligne([(sx * 0.35, -1.8 + dy), (sx * 1.15, -1.85 + dy * 2)], encre, 0.025)
    im = im.resize((int(5 * s), int(5 * s)), Image.LANCZOS)
    if miroir:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    _cache_sprites[cle] = im
    return im


# ---------------------------------------------------------------- dessin : décors
CIEL = {"jardin": ("#8FD3FF", "#E8F7FF"), "foret": ("#A9E0F5", "#F1FBEA"), "maison": ("#FBE3C8", "#FFF4E6"), "plage": ("#7CCBFF", "#E0F6FF"), "ferme": ("#92D5FF", "#F3FBFF"),
        "montagne": ("#7FC4F5", "#E9F6FF"), "neige": ("#C5DFF5", "#F5FAFF"), "nuit": ("#2B3A7A", "#6F7FC0")}


def _collines(d: ImageDraw.ImageDraw, w: int, y0: float, amp: float, graine: float, couleur: str, h: int) -> None:
    pts = [(x, y0 - amp * (0.5 + 0.5 * math.sin(x / w * 4.2 + graine))) for x in range(0, w + 12, 12)]
    d.polygon(pts + [(w, h), (0, h)], fill=couleur)


def _arbre(d, x: float, base: float, hauteur: float, couleur_feuilles: str, pin: bool = False) -> None:
    larg = hauteur * 0.12
    d.rectangle((x - larg / 2, base - hauteur * 0.35, x + larg / 2, base), fill="#9A6B45")
    if pin:
        for i in range(3):
            y = base - hauteur * (0.3 + 0.25 * i)
            d.polygon([(x - hauteur * (0.3 - 0.07 * i), y), (x + hauteur * (0.3 - 0.07 * i), y), (x, y - hauteur * 0.4)], fill=couleur_feuilles)
    else:
        for dx, dy, r in ((0, -0.55, 0.3), (-0.2, -0.42, 0.22), (0.2, -0.42, 0.22)):
            d.ellipse((x + dx * hauteur - r * hauteur, base + dy * hauteur - r * hauteur, x + dx * hauteur + r * hauteur, base + dy * hauteur + r * hauteur), fill=couleur_feuilles)


def _fond(type_: str, w: int, h: int, gy: float, graine: int = 0) -> Image.Image:
    """Décor fixe (sans nuages ni étoiles) ; le sol commence à `gy` (fraction de la hauteur), là où se tiennent les personnages."""
    r = np.random.default_rng(graine + sum(ord(c) for c in type_))
    ciel = CIEL[type_]
    img = rendu.degrade(w, h, ciel[0], ciel[1])
    d = ImageDraw.Draw(img)
    sol = h * gy
    if type_ == "jardin":
        _collines(d, w, sol - h * 0.07, h * 0.05, 0.5, "#8EDB86", h)
        _collines(d, w, sol, h * 0.03, 2.0, "#6CC070", h)
        for _ in range(26):
            x, y = float(r.uniform(0, w)), float(r.uniform(sol + 8, h * 0.99))
            c = ("#FF6F91", "#FFD84A", "#FFFFFF", "#B38BFF")[int(r.integers(0, 4))]
            d.line((x, y, x, y + h * 0.03), fill="#3E9E57", width=4)
            for a in range(5):
                an = a * 2 * math.pi / 5
                d.ellipse((x + math.cos(an) * 12 - 8, y + math.sin(an) * 12 - 8, x + math.cos(an) * 12 + 8, y + math.sin(an) * 12 + 8), fill=c)
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill="#FFE27A")
    elif type_ == "foret":
        _collines(d, w, sol - h * 0.1, h * 0.04, 1.0, "#9ED98D", h)
        for i in range(9):
            _arbre(d, w * (i + 0.5) / 9 + float(r.uniform(-20, 20)), sol - h * 0.07, h * float(r.uniform(0.28, 0.36)), "#7CC47A")
        _collines(d, w, sol, h * 0.03, 3.0, "#5FB46A", h)
        for _ in range(7):
            x = float(r.uniform(0.05, 0.95)) * w
            y = float(r.uniform(sol + 20, h * 0.97))
            d.rectangle((x - 5, y, x + 5, y + 22), fill="#F6EBDD")
            d.ellipse((x - 26, y - 20, x + 26, y + 8), fill="#E8564E")
            d.ellipse((x - 9, y - 12, x - 3, y - 6), fill="#FFFFFF")
            d.ellipse((x + 6, y - 14, x + 12, y - 8), fill="#FFFFFF")
    elif type_ == "maison":
        d.rectangle((0, 0, w, sol), fill="#FCE9CF")
        d.rectangle((0, sol, w, h), fill="#D9A877")
        fw, fh = w * 0.3, h * 0.2
        fx, fy = w * 0.5 - fw / 2, h * 0.08
        d.rectangle((fx - 12, fy - 12, fx + fw + 12, fy + fh + 12), fill="#FFFFFF")
        d.rectangle((fx, fy, fx + fw, fy + fh), fill="#9ED8FF")
        d.line((fx + fw / 2, fy, fx + fw / 2, fy + fh), fill="#FFFFFF", width=10)
        d.polygon([(fx, fy), (fx + fw * 0.2, fy), (fx, fy + fh * 0.7)], fill="#FF9DB8")
        d.polygon([(fx + fw, fy), (fx + fw * 0.8, fy), (fx + fw, fy + fh * 0.7)], fill="#FF9DB8")
        d.ellipse((w * 0.12, sol + h * 0.02, w * 0.88, sol + h * 0.13), fill="#F29BBB")
        d.ellipse((w * 0.2, sol + h * 0.04, w * 0.8, sol + h * 0.11), fill="#F7B8CF")
        for i, c in enumerate(("#6FB6F2", "#F7D44A", "#6CC070")):  # cubes de jeu
            x = w * (0.08 + 0.07 * i)
            d.rectangle((x, sol - h * 0.05, x + h * 0.05, sol), fill=c)
    elif type_ == "plage":
        mer = sol - h * 0.1
        d.rectangle((0, mer, w, sol), fill="#4FB8E8")
        for i in range(5):
            y = mer + (sol - mer) * i / 5
            d.line([(x, y + 4 * math.sin(x / 40 + i)) for x in range(0, w, 12)], fill="#BDEBFF", width=4)
        d.polygon([(0, sol - h * 0.02), (w, sol - h * 0.06), (w, h), (0, h)], fill="#F7E2A8")
        for _ in range(8):
            x, y = float(r.uniform(0, w)), float(r.uniform(sol + 20, h * 0.97))
            d.ellipse((x - 14, y - 9, x + 14, y + 9), fill="#FFD0DC")
        d.line((w * 0.84, sol + h * 0.04, w * 0.84, sol - h * 0.22), fill="#9A6B45", width=10)
        d.pieslice((w * 0.84 - w * 0.15, sol - h * 0.3, w * 0.84 + w * 0.15, sol - h * 0.12), 180, 360, fill="#FF6F91")
    elif type_ == "ferme":
        _collines(d, w, sol - h * 0.06, h * 0.04, 0.2, "#CBE58A", h)
        bw, bh = w * 0.34, h * 0.22
        bx, bb = w * 0.62, sol - h * 0.05
        d.rectangle((bx, bb - bh, bx + bw, bb), fill="#E0504A")
        d.polygon([(bx - 14, bb - bh), (bx + bw / 2, bb - bh - h * 0.09), (bx + bw + 14, bb - bh)], fill="#A83A36")
        d.rectangle((bx + bw * 0.36, bb - bh * 0.6, bx + bw * 0.64, bb), fill="#FFFFFF")
        d.line((bx + bw * 0.36, bb - bh * 0.6, bx + bw * 0.64, bb), fill="#E0504A", width=6)
        d.line((bx + bw * 0.64, bb - bh * 0.6, bx + bw * 0.36, bb), fill="#E0504A", width=6)
        _collines(d, w, sol, h * 0.03, 2.5, "#8ED06B", h)
        for i in range(8):
            x = w * (0.02 + 0.12 * i)
            d.rectangle((x, sol + h * 0.03, x + 14, sol + h * 0.12), fill="#F6EBDD")
        d.line((0, sol + h * 0.055, w, sol + h * 0.055), fill="#F6EBDD", width=12)
    elif type_ == "montagne":
        for x0, hh, c in ((0.15, 0.4, "#9BB4D8"), (0.55, 0.5, "#8AA5CF"), (0.9, 0.34, "#A8BFDF")):
            cx, top = w * x0, sol - h * hh
            d.polygon([(cx - w * 0.3, sol), (cx, top), (cx + w * 0.3, sol)], fill=c)
            d.polygon([(cx - w * 0.07, top + (sol - top) * 0.22), (cx, top), (cx + w * 0.07, top + (sol - top) * 0.22)], fill="#FFFFFF")
        _collines(d, w, sol, h * 0.04, 1.3, "#7FD16F", h)
    elif type_ == "neige":
        _collines(d, w, sol - h * 0.08, h * 0.04, 0.4, "#E2EEF9", h)
        for i in range(5):
            _arbre(d, w * (0.1 + 0.2 * i) + float(r.uniform(-15, 15)), sol - h * 0.05, h * float(r.uniform(0.22, 0.3)), "#5E9F7E", pin=True)
        _collines(d, w, sol, h * 0.035, 2.6, "#FFFFFF", h)
    elif type_ == "nuit":
        for _ in range(60):
            x, y = float(r.uniform(0, w)), float(r.uniform(0, sol * 0.8))
            rr = float(r.uniform(1.5, 3.5))
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill="#F4F0C8")
        d.ellipse((w * 0.78 - 60, h * 0.08, w * 0.78 + 60, h * 0.08 + 120), fill="#FFF3B0")
        d.ellipse((w * 0.78 - 20, h * 0.08 - 10, w * 0.78 + 100, h * 0.08 + 110), fill=ciel[0])
        _collines(d, w, sol - h * 0.06, h * 0.04, 0.9, "#34508F", h)
        _collines(d, w, sol, h * 0.03, 2.2, "#3E7A74", h)
    if type_ not in ("nuit", "maison", "neige"):  # soleil
        d.ellipse((w * 0.84 - 55, h * 0.06, w * 0.84 + 55, h * 0.06 + 110), fill="#FFE066")
    return img


def _extras(img: Image.Image, type_: str, t: float, w: int, h: int, gy: float) -> None:
    """Petits mouvements doux : nuages qui dérivent, flocons, lucioles."""
    d = ImageDraw.Draw(img)
    if type_ in ("jardin", "foret", "plage", "ferme", "montagne"):
        for i, (y, taille, vit) in enumerate(((0.07, 46, 0.012), (0.15, 36, 0.008), (0.1, 56, 0.005))):
            x = ((0.2 + 0.37 * i + vit * t) % 1.3 - 0.15) * w
            yy = h * y
            d.ellipse((x - taille * 1.7, yy - taille * 0.6, x + taille * 1.7, yy + taille * 0.6), fill="#FFFFFF")
            d.ellipse((x - taille * 0.7, yy - taille, x + taille * 0.9, yy + taille * 0.2), fill="#FFFFFF")
    elif type_ == "neige":
        for i in range(34):
            x = ((i * 0.6180339) % 1.0) * w + 18 * math.sin(t * 0.8 + i)
            y = ((i * 0.37 + t * (0.04 + 0.01 * (i % 4))) % 1.0) * h * 0.95
            rr = 5 + (i % 3) * 2
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill="#FFFFFF")
    elif type_ == "nuit":
        for i in range(10):
            x = ((i * 0.713) % 1.0) * w + 40 * math.sin(t * 0.5 + i * 2)
            y = h * gy + h * 0.06 + 30 * math.sin(t * 0.7 + i) + (i % 3) * h * 0.04
            a = 0.5 + 0.5 * math.sin(t * 2 + i)
            c = tuple(int(v * (0.5 + 0.5 * a)) for v in (255, 238, 120))
            d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=c)


# ---------------------------------------------------------------- calendrier et images
def _taille(v: str) -> tuple[int, int]:
    return (1080, 1920) if v == "short" else (1280, 720)


def _calendrier(ep: dict, timings: dict, total: float) -> dict:
    """Début/fin de chaque phrase (et de ses mots), début de chaque scène, d'après timings.json (à défaut : répartition selon le nombre de mots)."""
    ph = _phrases(ep)
    lg = timings.get("lines") or []
    if len(lg) == len(ph):
        ph_t = [{"txt": p, "start": float(l["start"]), "end": float(l["end"]), "mots": [(float(m["start"]) if isinstance(m, dict) else None) for m in (l.get("words") or [])]} for p, l in zip(ph, lg)]
    else:
        nb = sum(len(p.split()) for p in ph) or 1
        t, ph_t = 0.15, []
        for p in ph:
            dur = (total - 0.3 - FIN_S) * len(p.split()) / nb
            ph_t.append({"txt": p, "start": t, "end": t + dur, "mots": []})
            t += dur
    debuts = [0.0] + [ph_t[i]["start"] for i in _debuts_scenes(ep)[1:]]
    return {"phrases": ph_t, "scenes": debuts}


def _scene_de(cal: dict, t: float) -> int:
    k = 0
    for i, d in enumerate(cal["scenes"]):
        if t >= d - 1e-6:
            k = i
    return k


class _Rendu:
    def __init__(self, ep: dict, cal: dict, w: int, h: int, total: float):
        self.ep, self.cal, self.w, self.h, self.total = ep, cal, w, h, total
        self.portrait = h > w
        self.gy = 0.66 if self.portrait else 0.73
        self.s = int(w * 0.157) if self.portrait else int(h * 0.145)
        graine = sum(ord(c) for c in ep["id"])
        self.fonds = {t: _fond(t, w, h, self.gy, graine) for t in {s["decor"] for s in ep["scenes"]}}
        e = w / 1080 if self.portrait else w / 1280
        self.police = rendu.police(int((66 if self.portrait else 40) * e))
        self.police_fin = rendu.police(int((150 if self.portrait else 100) * e))
        self.ami = ep.get("ami")

    def _perso(self, img: Image.Image, p: dict, x: float, t: float, mouv: str, miroir: bool, dec: float) -> None:
        clign = (t * 1.0 + dec) % 3.4 < 0.14
        sp = _sprite(p["type"], p["couleur"], self.s, clign, miroir)
        if mouv == "saute":
            dy = -abs(math.sin(t * 3.2 + dec)) * self.s * 0.55
        elif mouv == "marche":
            dy = -abs(math.sin(t * 5 + dec)) * self.s * 0.12
        elif mouv == "balance":
            dy, x = 0, x + math.sin(t * 1.6 + dec) * self.s * 0.12
        else:
            dy = math.sin(t * 1.8 + dec) * self.s * 0.03
        base = self.h * self.gy + self.s * 0.28
        img.paste(sp, (int(x - sp.width / 2), int(base - sp.height + self.s * 0.25 + dy)), sp)

    def scene(self, k: int, t: float) -> Image.Image:
        sc = self.ep["scenes"][k]
        img = self.fonds[sc["decor"]].copy()
        _extras(img, sc["decor"], t, self.w, self.h, self.gy)
        avec = sc.get("avec") or (["perso", "ami"] if self.ami else ["perso"])
        mouv = sc.get("mouvement") or "repose"
        if avec == ["perso", "ami"]:
            xs = {"perso": self.w * 0.3, "ami": self.w * 0.7}
        else:
            xs = {a: self.w * 0.5 for a in avec}
        if "perso" in avec:
            self._perso(img, self.ep["personnage"], xs["perso"], t, mouv, False, 0.0)
        if "ami" in avec and self.ami:
            self._perso(img, self.ami, xs["ami"], t, "repose" if mouv != "balance" else "balance", True, 1.3)
        return img

    def sous_titre(self, img: Image.Image, t: float) -> None:
        ph = self.cal["phrases"]
        cur = max([i for i, p in enumerate(ph) if t >= p["start"] - 0.05] or [-1])
        d = ImageDraw.Draw(img)
        if cur < 0:
            return
        if t >= ph[-1]["end"] + 0.5:
            rendu.texte_centre(d, self.w / 2, self.h * (0.78 if self.portrait else 0.78), "Fin", self.police_fin, STYLE["accent"], self.w - 100, ombre="#FFFFFF")
            return
        p = ph[cur]
        mots = p["txt"].split()
        debuts = p["mots"] if len(p["mots"]) == len(mots) and all(x is not None for x in p["mots"]) else [p["start"] + (p["end"] - p["start"]) * i / max(1, len(mots)) for i in range(len(mots))]
        lignes = rendu.lignes(d, p["txt"], self.police, int(self.w * 0.86))
        hl = self.police.size * 1.3
        haut = hl * len(lignes) + 44
        bas = self.h * 0.955
        y0 = bas - haut
        d.rounded_rectangle((self.w * 0.04, y0, self.w * 0.96, bas), radius=36, fill=STYLE["panneau"], outline="#E9DFC8", width=5)
        i, y = 0, y0 + 22
        for ln in lignes:
            ws = ln.split()
            x = self.w / 2 - d.textlength(ln, font=self.police) / 2
            for w_ in ws:
                d.text((x, y), w_, font=self.police, fill=STYLE["accent"] if t >= debuts[min(i, len(debuts) - 1)] else STYLE["encre"])
                x += d.textlength(w_ + " ", font=self.police)
                i += 1
            y += hl

    def image(self, t: float) -> Image.Image:
        k = _scene_de(self.cal, t)
        img = self.scene(k, t)
        dt = t - self.cal["scenes"][k]
        if k > 0 and dt < FONDU_S:  # fondu enchaîné doux depuis la scène précédente
            img = Image.blend(self.scene(k - 1, t), img, rendu.facilite(dt / FONDU_S))
        self.sous_titre(img, t)
        return img


# ---------------------------------------------------------------- audio
def _fond_sonore(ep: dict, total: float) -> np.ndarray:
    """Boîte à musique très douce (gamme pentatonique, notes espacées), propre à l'épisode (graine = identifiant)."""
    r = np.random.default_rng(sum(ord(c) for c in ep["id"]))
    degres = (1, 2, 3, 5, 6, 8)
    ev, t = [], 0.4
    while t < total - 1.5:
        ev.append((t, 1.4, synth.frequence(int(r.choice(degres)), 261.63)))
        t += float(r.choice((1.2, 1.8, 2.4)))
    return synth.melodie(ev, total, "boite")[: int(total * rendu.SR)]


def _mixer(ep: dict, voix: np.ndarray) -> np.ndarray:
    total = len(voix) / rendu.SR + FIN_S
    v = np.concatenate([voix, np.zeros(int(FIN_S * rendu.SR), dtype=np.float32)])
    bed = _fond_sonore(ep, total)
    bed = np.concatenate([bed, np.zeros(max(0, len(v) - len(bed)), dtype=np.float32)])[: len(v)]
    rms = lambda x: float(np.sqrt(np.mean(np.square(x))) + 1e-9)  # noqa: E731
    bed = bed * (rms(v) * 10 ** (-21 / 20) / rms(bed))
    fondu = np.minimum(1.0, np.minimum(np.arange(len(v)) / (2 * rendu.SR), (len(v) - np.arange(len(v))) / (2 * rendu.SR))).astype(np.float32)
    x = v + bed * fondu
    pic = float(np.max(np.abs(x))) + 1e-9
    return (x * (0.85 / pic) if pic > 0.85 else x).astype(np.float32)


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = 15) -> Path:
    v = type_video(ep)
    w, h = _taille(v)
    voix = rendu.lire_audio(ep_dir / "voice.wav")
    audio = _mixer(ep, voix)
    total = len(audio) / rendu.SR
    timings = commun_json(ep_dir / "timings.json")
    cal = _calendrier(ep, timings, total)
    r = _Rendu(ep, cal, w, h, total)
    muet = out_dir / "rendu.mp4"
    with rendu.Encodeur(muet, w, h, fps) as enc:
        for i in range(int(total * fps)):
            enc.ecrire(r.image(i / fps))
    wav = out_dir / "mixage.wav"
    rendu.ecrire_wav(wav, audio)
    final = out_dir / f"{ep['id']}.mp4"
    mes = rendu.muxer(muet, wav, final, LUFS)
    muet.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), scenes=len(ep["scenes"]),
              mots=sum(len(p.split()) for p in _phrases(ep)), pour_enfants=True)
    return final


def commun_json(chemin: Path) -> dict:
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def miniature(ep: dict, profil: dict) -> Image.Image:
    w, h = 1280, 720
    graine = sum(ord(c) for c in ep["id"])
    img = _fond(ep["scenes"][0]["decor"] if ep.get("lieu") not in DECORS else ep["lieu"], w, h, 0.78, graine)
    s = 150
    p = ep["personnage"]
    x_perso = 0.3 * w if ep.get("ami") else 0.5 * w
    for q, x, mir in ((p, x_perso, False), (ep.get("ami"), 0.7 * w, True)):
        if q:
            sp = _sprite(q["type"], q["couleur"], s, False, mir)
            img.paste(sp, (int(x - sp.width / 2), int(h * 0.78 + s * 0.28 - sp.height + s * 0.25)), sp)
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    rendu.texte_centre(d, 640, 28, str(mini.get("texte_haut", "")).upper(), rendu.police(60), STYLE["encre"], 1150, ombre="#FFFFFF")
    gros = str(mini.get("gros", ""))
    rendu.texte_centre(d, 640, 105, gros, rendu.police(170 if len(gros) <= 10 else 120), STYLE["accent"], 1180, ombre="#FFFFFF")
    return img
