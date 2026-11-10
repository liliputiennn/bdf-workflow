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
from autopilot import seo  # noqa: E402
from autopilot.writer import gabarits  # noqa: E402
from autopilot.common import EPISODES, ep_dir, get_status, read_json, set_status, write_json  # noqa: E402
from autopilot.make_short import validate as valider_forme  # noqa: E402
from autopilot.long import longlib  # noqa: E402
from autopilot.writer.factcheck import domaine, url_valide, verifier  # noqa: E402
from autopilot import chaines  # noqa: E402
from autopilot import langues  # noqa: E402
from autopilot.traduction import controle as controle_traduction  # noqa: E402

BROUILLONS = EPISODES / "_brouillons"
MOTS_NOMBRE = set("zero deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente quarante cinquante soixante cent cents mille million millions milliard milliards pourcent pour-cent".split())
MIN_MOTS, MAX_MOTS = 55, 170  # environ 3 mots par seconde : 20 à 55 secondes
MIN_MOTS_LONG, MAX_MOTS_LONG = 1000, 2200  # 6 à 12 minutes
MAX_ESSAIS = 3
MAX_MOTS_PHRASE = 15
MAX_MOTS_PHRASE_LONG = 26  # sous-titres coupés en morceaux courts à l'écran : la phrase peut être plus longue qu'en Short
STYLES_MINIATURE = ("createur", "telephone", "pile", "chiffre", "question", "contraste")
ICONES = ("carte", "hotdog", "magasin", "pieces", "panier")


def a_un_nombre(phrase: str, langue: str = "fr") -> bool:
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœäöß0-9-]+", phrase.lower())
    nombres = MOTS_NOMBRE if langues.langue_de(langue) == "fr" else MOTS_NOMBRE | langues.infos(langue)["mots_nombre"]
    return any(re.search(r"\d", m) or m in nombres for m in mots)


def controles_faits(phrases: list, faits, reseau: bool, langue: str = "fr"):
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
        if a_un_nombre(p, langue) and i not in couvertes:
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


# Texte PARLÉ : jamais d'avertissement, de loi ni de mention d'IA (Cap éditorial du 4 novembre 2026). « IA » comme sujet d'un business reste permis.
RE_AVERTISSEMENT_PAROLE = re.compile(
    r"voix de synth[èe]se|voix synth[ée]tique|intelligence artificielle|g[ée]n[ée]r[ée]e? par (?:une? )?ia|cr[ée][ée]e? par (?:une? )?ia|"
    r"je ne garantis|ceci n.est pas un conseil|n.est pas un conseil|ne constitue pas un conseil|"
    r"(?:attention|fais attention|renseigne-toi) (?:à|aux?) (?:la |les )?(?:loi|lois|r[èe]gles|r[èe]glements?)|"
    r"la loi (?:impose|exige|oblige|interdit|dit)|selon la loi|d.apr[èe]s la loi|r[ée]sultats? non garantis?",
    re.IGNORECASE)
TITRE_SHORT_MAX = seo.TITRE_SHORT_MAX
TITRES_DE_CHAPITRE_VAGUES = re.compile(r"^\s*(?:business\s*)?(?:n\s*°\s*|num[ée]ro\s*|#)?\d+\s*$|^\s*(?:accroche|introduction|intro|conclusion|fin|suite|chapitre\s*\d*)\s*$", re.IGNORECASE)


def controles_texte_public(phrases: list, pub, langue: str = "fr") -> list[str]:
    """Aucun avertissement, aucune loi, aucune mention d'IA ni de voix de synthèse dans le texte parlé ni dans la description."""
    err: list[str] = []
    _, avertissement_langue = langues.motifs_interdits(langue)
    for i, p in enumerate(phrases or [], 1):
        m = RE_AVERTISSEMENT_PAROLE.search(p) or (avertissement_langue.search(p) if avertissement_langue else None)
        if m:
            err.append(f"phrase {i} : « {m.group(0)} » : pas d'avertissement, de loi ni de mention d'IA dans le texte parlé (tout est dans la bio de la chaîne)")
    if isinstance(pub, dict):
        texte = str(pub.get("description", "")) + "\n" + str(pub.get("titre", ""))
        m = RE_AVERTISSEMENT_PAROLE.search(texte) or seo.RE_MENTION_INTERDITE.search(texte) or (avertissement_langue.search(texte) if avertissement_langue else None)
        if m:
            err.append(f"publication : « {m.group(0)} » : pas d'avertissement, de loi ni de mention d'IA dans la description ni le titre")
    return err


def controles_publication(pub, court: bool = False) -> list[str]:
    """`court` = Short : titre de 60 caractères au plus (50 idéalement) avec le mot-clé en tête."""
    err: list[str] = []
    if not isinstance(pub, dict):
        return ["publication.json doit être un objet"]
    t = pub.get("titre", "")
    if not t or len(t) > 70:
        err.append(f"publication : titre vide ou trop long ({len(t)} caractères, 70 au plus)")
    elif court and len(t) > TITRE_SHORT_MAX:
        err.append(f"publication : titre de Short trop long ({len(t)} caractères, {TITRE_SHORT_MAX} au plus, {seo.TITRE_SHORT_IDEAL} idéalement) : mot-clé en tête, le reste coupé")
    if not str(pub.get("description", "")).strip():
        err.append("publication : description vide")
    elif len(str(pub["description"]).encode("utf-8")) > 4200:
        err.append(f"publication : description trop longue ({len(str(pub['description']).encode('utf-8'))} octets, 4200 au plus : YouTube coupe à 5000 avec les chapitres) : garde le résumé et les sources les plus importantes")
    else:
        n_hash = len(seo.hashtags_du_texte(str(pub["description"])))
        if n_hash > seo.HASHTAGS_MAX:
            err.append(f"publication : {n_hash} hashtags dans la description, {seo.HASHTAGS_MAX} au plus : au-delà, YouTube les ignore TOUS")
    tags = pub.get("tags", [])
    if not isinstance(tags, list) or not 3 <= len(tags) <= 15:
        err.append("publication : de 3 à 15 tags attendus")
    if pub.get("contenu_ia") is not True:
        err.append("publication : « contenu_ia » doit valoir true (voix synthétique)")
    return err


def avertissements_publication(pub, court: bool = False) -> list[str]:
    """Référencement : ce qui n'empêche pas la publication (le publieur complète hashtags et mots-clés) mais affaiblit la vidéo."""
    if not isinstance(pub, dict):
        return []
    av: list[str] = []
    desc, titre = str(pub.get("description", "")), str(pub.get("titre", ""))
    n_hash = len(seo.hashtags_du_texte(desc))
    if n_hash < 8:
        av.append(f"description : {n_hash} hashtag(s) : vise une dizaine de hashtags pertinents (15 au plus) ; le publieur complétera à partir des tags")
    if not seo.a_bloc_mots_cles(desc):
        av.append("description : pas de ligne « Mots-clés : … » (le publieur l'ajoutera à partir des tags)")
    if court and len(titre) > seo.TITRE_SHORT_IDEAL:
        av.append(f"titre de Short de {len(titre)} caractères : {seo.TITRE_SHORT_IDEAL} au plus se lit en entier")
    mots = [m for m in seo.mots_cles(titre, [], 4)]
    if mots and not any(m.lower() in desc[:240].lower() for m in mots):
        av.append("description : le mot-clé du titre manque dans les deux premières lignes")
    return av


CADEAU_MESSAGES_MIN, CADEAU_MESSAGE_MAX_CAR = 3, 450


def avertissements_chapitres(ep: dict) -> list[str]:
    """Les chapitres horodatés apparaissent dans la recherche Google et YouTube : des mots que les gens tapent, pas « Business n°3 » ni « Accroche »."""
    av = []
    for i, ch in enumerate(ep.get("chapitres") or [], 1):
        t = str(ch.get("titre", "")).strip() if isinstance(ch, dict) else ""
        if not t or TITRES_DE_CHAPITRE_VAGUES.match(t):
            av.append(f"chapitre {i} : titre « {t} » vague : nomme le business avec les mots que les gens tapent (« Vendre des bougies sur Vinted »)")
        elif len(t) > 60:
            av.append(f"chapitre {i} : titre de {len(t)} caractères : 60 au plus pour rester lisible dans la liste des chapitres")
    return av


def controles_cadeau(pub) -> list[str]:
    """Le cadeau gratuit d'un long : des messages tout faits à copier-coller pour décrocher un premier client.
    Ils sont dans `publication.json` (`cadeau`) ET recopiés mot pour mot dans la description, où les spectateurs les copient.
    `suite` annonce le cadeau de la prochaine vidéo : c'est ce qui donne une vraie raison de s'abonner."""
    if not isinstance(pub, dict):
        return []
    c = pub.get("cadeau")
    if not isinstance(c, dict) or not isinstance(c.get("messages"), list):
        return ["publication : « cadeau » manque ({\"titre\": \"...\", \"messages\": [\"message prêt à envoyer\", ...]}) : un message tout fait à copier par business"]
    err: list[str] = []
    msgs = [m for m in c["messages"] if isinstance(m, str) and m.strip()]
    if len(msgs) < CADEAU_MESSAGES_MIN:
        err.append(f"publication : cadeau : {len(msgs)} message(s), {CADEAU_MESSAGES_MIN} au moins (un par business)")
    desc = str(pub.get("description", ""))
    for i, m in enumerate(msgs, 1):
        if len(m) > CADEAU_MESSAGE_MAX_CAR:
            err.append(f"publication : cadeau, message {i} : {len(m)} caractères, {CADEAU_MESSAGE_MAX_CAR} au plus (court = on l'envoie vraiment)")
        if m.strip() not in desc:
            err.append(f"publication : cadeau, message {i} : à recopier mot pour mot dans la description (c'est là que les spectateurs le copient)")
    if not str(c.get("titre", "")).strip():
        err.append("publication : cadeau : « titre » manque (ex. « Messages prêts à envoyer »)")
    suite = str(c.get("suite", "")).strip()
    if not 15 <= len(suite) <= 160:
        err.append("publication : cadeau : « suite » manque ou hors de 15 à 160 caractères (annonce le cadeau de la prochaine vidéo : c'est la raison de s'abonner)")
    elif suite not in desc:
        err.append("publication : cadeau : « suite » doit être recopiée mot pour mot dans la description (avec l'invitation à s'abonner)")
    return err


def controles_langue(phrases: list, pub, langue: str) -> list[str]:
    """Langue autre que le français : aucun chiffre dans le texte PARLÉ (la voix lit des mots), texte et description bien dans la langue de la chaîne,
    `publication.langue` cohérente. Le français garde ses contrôles historiques (liste vide)."""
    if langues.langue_de(langue) == "fr":
        return []
    err: list[str] = []
    for i, p in enumerate(phrases or [], 1):
        if langues.a_des_chiffres(p):
            err.append(f"phrase {i} : chiffres dans le texte parlé ({langue}) : écris les nombres en toutes lettres (« twelve thousand dollars », pas « $12,000 »)")
    if phrases and not langues.langue_plausible(" ".join(phrases), langue):
        err.append(f"texte parlé : ne ressemble pas à la langue « {langue} » de la chaîne (resté dans la langue source ?)")
    if isinstance(pub, dict):
        if pub.get("langue") != langues.langue_de(langue):
            err.append(f"publication : « langue » doit valoir « {langues.langue_de(langue)} » (trouvé « {pub.get('langue')} »)")
        desc = str(pub.get("description", ""))
        if len(desc.split()) >= 25 and not langues.langue_plausible(desc, langue):
            err.append(f"publication : la description ne ressemble pas à la langue « {langue} »")
    return err


def bornes_mots(langue: str, mini: int, maxi: int) -> tuple[int, int]:
    """Bornes de mots ajustées à la langue (l'anglais dit la même chose avec environ 12 % de mots en moins)."""
    r = langues.infos(langue)["ratio_mots"]
    return int(mini * r * 0.95), int(maxi * r * 1.05) if r != 1.0 else maxi


def controles(ep: dict, faits, pub, reseau: bool = True, langue: str = "fr"):
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
    mn, mx = bornes_mots(langue, MIN_MOTS, MAX_MOTS) if langues.langue_de(langue) != "fr" else (MIN_MOTS, MAX_MOTS)
    if not mn <= mots <= mx:
        err.append(f"{mots} mots au total : il en faut de {mn} à {mx} (environ 20 à 55 secondes)")
    e2, a2, faits = controles_faits(phrases, faits, reseau, langue)
    err += e2
    avert += a2
    err += [f"episode.json : {e}" if e.startswith("« miniature »") else e for e in controles_miniature(ep.get("miniature"))]
    err += controles_publication(pub, court=True)
    err += controles_texte_public(phrases, pub, langue)
    err += controles_langue(phrases, pub, langue)
    e3, a3 = gabarits.controler(ep)
    err += e3
    avert += a3 + avertissements_publication(pub, court=True)
    return err, avert, faits


def controles_long(ep: dict, faits, pub, reseau: bool = True, langue: str = "fr"):
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
    mn, mx = bornes_mots(langue, MIN_MOTS_LONG, MAX_MOTS_LONG) if langues.langue_de(langue) != "fr" else (MIN_MOTS_LONG, MAX_MOTS_LONG)
    if not mn <= mots <= mx:
        err.append(f"{mots} mots au total : il en faut de {mn} à {mx} (6 à 12 minutes)")
    e2, a2, faits = controles_faits(phrases, faits, reseau, langue)
    err += e2
    avert += a2
    err += [f"episode-long.json : {e}" if e.startswith("« miniature »") else e for e in controles_miniature(ep.get("miniature"))]
    err += controles_publication(pub)
    err += controles_texte_public(phrases, pub, langue)
    err += controles_langue(phrases, pub, langue)
    err += controles_cadeau(pub)
    avert += avertissements_publication(pub) + avertissements_chapitres(ep)
    return err, avert, faits


def vue_a_plat(ep: dict) -> dict:
    """`episode.json` d'un long : phrases et scènes bout à bout (numérotation globale). Sert à la miniature et à la publication, jamais au rendu."""
    plat = longlib.flatten(ep)
    out = {"id": ep["id"], "format": "long", "titre": ep["titre"], "theme": ep["theme"], "chaine": ep["chaine"],
           "phrases": plat["phrases"], "scenes": plat["scenes"], "miniature": ep.get("miniature")}
    if ep.get("langue"):
        out["langue"] = ep["langue"]
    if ep.get("theme_accent"):
        out["theme_accent"] = ep["theme_accent"]
    return out


def valider_brouillon(ep_id: str, chaine: str | None = None, sans_reseau: bool = False) -> tuple[int, dict]:
    """Valide `episodes-b/_brouillons/<ep_id>/` ; (code, bilan). Code 0 = accepté, 1 = à corriger, 2 = mis en quarantaine. Sert au rédacteur (CLI)
    comme à la file de traduction (repli gratuit), qui passent donc exactement par les mêmes contrôles."""
    a = argparse.Namespace(id=ep_id, chaine=chaine, sans_reseau=sans_reseau)
    d = BROUILLONS / a.id
    long = (d / "episode-long.json").exists()
    nom = "episode-long.json" if long else "episode.json"
    ep = read_json(d / nom)
    if ep is None:
        return 1, {"ok": False, "erreurs": [f"{d}\\{nom} introuvable ou illisible (JSON invalide ?)"]}
    faits, pub = read_json(d / "faits.json"), read_json(d / "publication.json")
    if ep.get("id") != a.id:
        ep["id"] = a.id
    chaine = a.chaine or (pub or {}).get("chaine_id") or chaines.CHAINE_DEFAUT
    if chaine not in chaines.charger_profils():
        return 1, {"ok": False, "erreurs": [f"chaîne « {chaine} » inconnue : profils dans autopilot/chaines/ ({', '.join(chaines.charger_profils())})"]}
    langue = langues.langue_de(chaines.charger_profils()[chaine]["langue"])
    if langue != "fr":
        ep["langue"] = langue  # les sous-titres et les textes d'écran de Remotion suivent la langue de la chaîne
    profil_chaine = chaines.charger_profils()[chaine]
    module_format = chaines.charger_format(profil_chaine)
    if module_format is not None and getattr(module_format, "CONTROLES_STANDARD", True) is False:
        # format sans scènes ni faits au sens standard (quiz, leçons, sommeil, chansons) : le module porte le fond ; la forme de la publication reste contrôlée ici
        phrases_f = ep.get("phrases") if isinstance(ep.get("phrases"), list) else []
        court = ep.get("video") != "long"
        err = list(controles_publication(pub, court=court)) + controles_texte_public([p for p in phrases_f if isinstance(p, str)], pub, langue)
        avert = list(avertissements_publication(pub, court=court))
        if getattr(module_format, "MENTIONS_PERMISES", False):  # format qui DOIT afficher une mention (finance : « pas un conseil financier » ; ASMR : voix de synthèse) : décision de l'utilisateur
            err = [e for e in err if not (e.startswith("publication : «") and "pas d'avertissement, de loi" in e)]
    else:
        err, avert, faits = (controles_long if long else controles)(ep, faits, pub, reseau=not a.sans_reseau, langue=langue)
    if profil_chaine.get("format_module") and chaines.charger_format(profil_chaine) is None:
        err.append(f"module de format « {profil_chaine['format_module']} » introuvable ou cassé : épisode refusé")
    e_f, a_f = chaines.appeler_hook(profil_chaine, "valider_episode", ep, faits, pub, profil_chaine, defaut=([], []),
                                    sur_erreur=(["contrôle du format : le crochet valider_episode a planté (voir le module de format)"], []),
                                    options={"reseau": not a.sans_reseau})
    err += list(e_f)
    avert += list(a_f)
    traduction = controle_traduction.demande_de(a.id)  # adaptation d'un épisode d'une autre chaîne : contrôles propres (parité, différenciation)
    if traduction is not None:
        e_t, a_t = controle_traduction.controles_traduction(ep, faits, pub, traduction, langue, long=long, brouillon=d)
        err += e_t
        avert += a_t
    if not err:
        write_json(d / "faits.json", faits)
        write_json(d / nom, ep)
        if long:
            write_json(d / "episode.json", vue_a_plat(ep))
        os.replace(d, EPISODES / a.id)
        set_status(a.id, "ecrit", tentatives=0, chaine_id=chaine)
        if traduction is not None:
            controle_traduction.finaliser(a.id, traduction, avert)
        return 0, {"ok": True, "chaine": chaine, "format": "long" if long else "short", "avertissements": avert, "dossier": str(EPISODES / a.id)}
    essais_f = d / ".essais"
    essais = int(essais_f.read_text()) + 1 if essais_f.exists() else 1
    essais_f.write_text(str(essais))
    if essais >= MAX_ESSAIS:
        raison = f"validation échouée {essais} fois : " + " | ".join(err[:4])
        write_json(d / "erreurs.json", {"erreurs": err, "avertissements": avert})
        os.replace(d, EPISODES / a.id)
        set_status(a.id, "quarantaine", raison, tentatives=essais, chaine_id=chaine)
        if traduction is not None:
            controle_traduction.finaliser(a.id, traduction, avert, accepte=False)
        return 2, {"ok": False, "quarantaine": True, "erreurs": err}
    return 1, {"ok": False, "essai": essais, "essais_max": MAX_ESSAIS, "erreurs": err, "avertissements": avert}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--sans-reseau", action="store_true")
    ap.add_argument("--chaine", help="chaîne de l'épisode (sinon `chaine_id` de publication.json, sinon la chaîne par défaut)")
    a = ap.parse_args()
    code, bilan = valider_brouillon(a.id, a.chaine, a.sans_reseau)
    print(json.dumps(bilan, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
