"""Format « Finance perso pédagogique » : expliquer simplement l'argent du quotidien (budget, épargne, crédit, impôts, inflation…) en France.

ÉDUCATIF SEULEMENT, jamais de conseil personnalisé ni de promesse : aucune promesse de gain ou de rendement, aucun « achète / investis dans X », aucune
recommandation de produit, de plateforme ou de crypto. Chaque point est SOURCÉ (au moins deux sites différents dont une source officielle ou publique si
possible : service-public.fr, banque-france.fr, impots.gouv.fr, amf-france.org, insee.fr…), et chaque vidéo se termine par la mention
« Cette vidéo est éducative et ne constitue pas un conseil financier. », répétée dans la description (avec la liste des sources) et en bandeau à l'écran.

Rendu : Pillow + ffmpeg (comme les formats quiz / langues), Short vertical (25 à 90 s, 3 points) ou long 16:9 (3 à 12 min, 6 à 10 points).
Crochets du moteur : `consignes`, `valider_episode`. `CONTROLES_STANDARD = False` : le fond (sources, honnêteté) est contrôlé ici.

episode.json : {id, titre, chaine, theme, video: "short"|"long", format_contenu: "finance", sujet: "Le livret A",
                points: [{titre, texte: [1 à 3 phrases lues], chiffre?: {valeur: "3 %", legende: "taux au 1er août 2026"}, sources: [2 https], check: [mots]}],
                miniature: {texte_haut, gros}}
"""
import re
from pathlib import Path
from urllib.parse import urlparse

from PIL import ImageDraw

from . import commun, rendu

CONTROLES_STANDARD = False
LUFS = -14.0
SEUIL_VOIX = None
MENTIONS_PERMISES = True  # la mention « pas un conseil financier » est obligatoire (voir writer/valider.py)
DUREE_S = {"short": (25, 90), "long": (150, 780)}
POINTS = {"short": (3, 4), "long": (6, 10)}
MENTION = "Cette vidéo est éducative et ne constitue pas un conseil financier."
MENTION_NORM = "ne constitue pas un conseil financier"
SOURCES_PAR_POINT = 2

STYLE = {"haut": "#0B1F3A", "bas": "#12365F", "carte": "#F4F8FC", "encre": "#0B1F3A", "doux": "#8FA8C4", "vert": "#1FBF75", "or": "#F5B83D", "bandeau": "#061326"}

# promesses et conseils personnalisés refusés (en plus de ceux de commun.RE_PROMESSE)
RE_PROMESSE_FIN = re.compile(
    r"rendements? (?:garanti|assur)\w*|sans (?:aucun )?risque|devenir riche|devenez riche|libert[ée] financi[èe]re en|multiplie\w* (?:ton|votre|ta|vos) (?:argent|capital)|"
    r"\bx ?\d+ en|gagne\w* \d|(?:[0-9]+) ?% par (?:mois|semaine|jour)|argent facile|secret des riches|astuce infaillible|à coup sûr|a coup sur|investis? (?:dans|sur) |"
    r"ach[eè]te[zs]? |vends? (?:tes|ton|vos|votre) |tu dois (?:acheter|investir|vendre)|il faut (?:acheter|investir|vendre)", re.I)
RE_PRODUIT_MARQUE = re.compile(r"\b(?:binance|coinbase|trade ?republic|boursorama|revolut|degiro|etoro|bitpanda|nickel|n26|lydia)\b", re.I)

CONSIGNES = """Chaîne FINANCE PERSO PÉDAGOGIQUE (France) : tu EXPLIQUES, tu ne conseilles pas. Un Short (`"video": "short"`) = 3 ou 4 points sur UNE notion (le livret A, les intérêts composés, la règle 50/30/20…), durée 25 à 90 s. Un long (`"video": "long"`) = 6 à 10 points, 3 à 12 minutes.
Champ `sujet` = la notion. `points` = liste de {titre (court), texte (liste de 1 à 3 phrases lues à voix haute, 22 mots au plus chacune, sans chiffres : écris les nombres en lettres), chiffre (facultatif, AFFICHÉ à l'écran : {valeur: « 3 % », legende: « taux du livret A en vigueur, à vérifier »}), sources (2 pages https de 2 sites différents, de préférence officiels : service-public.fr, banque-france.fr, impots.gouv.fr, amf-france.org, insee.fr), check (1 à 4 mots ou nombres à retrouver dans ces pages)}.
Exemples chiffrés pédagogiques : toujours « par exemple » et jamais une prévision (« si on place cent euros à deux pour cent, au bout d'un an cela fait cent deux euros »). Dis que les taux et les règles changent et renvoie aux sources.
INTERDIT : promesse de gain ou de rendement, « sans risque », « devenir riche », conseil personnalisé (« achète », « investis dans »), recommandation d'une banque, d'une application, d'une plateforme ou d'une cryptomonnaie, urgence artificielle. Parle de principes, de mécanismes, de risques et de frais.
Dernière idée de chaque vidéo : « Cette vidéo est éducative et ne constitue pas un conseil financier. » (elle est lue et affichée automatiquement : ne l'écris pas dans les points).
Titre : la notion et ce qu'on y comprend (« Le livret A expliqué simplement »), 70 caractères au plus, sans promesse. Description : le résumé, la phrase « Cette vidéo est éducative et ne constitue pas un conseil financier. », puis « Sources : » et toutes les adresses utilisées.
Chaque vidéo traite une notion DIFFÉRENTE des précédentes (angle, exemple, public) : pas de répétition d'un même texte."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def type_video(ep: dict) -> str:
    return "long" if ep.get("video") == "long" else "short"


def _mot(n: int) -> str:
    return "zéro une deux trois quatre cinq six sept huit neuf dix onze douze".split()[n] if 0 <= n <= 12 else str(n)


# ---------------------------------------------------------------- script de la voix
def script_voix(ep: dict) -> dict:
    """Une ligne pour l'accroche, une pour le titre de chaque point puis ses phrases, une pour la mention finale. `plan` retrouve les lignes de chaque point."""
    pts = ep["points"]
    phrases = [f"{ep['sujet'].rstrip('.').strip()} : {_mot(len(pts))} idées à retenir."]
    pauses: dict[str, float] = {}
    plan = []
    for k, p in enumerate(pts):
        debut = len(phrases)
        pauses[str(debut + 1)] = 0.45
        phrases.append(p["titre"].rstrip(".").strip() + ".")
        for s in p["texte"]:
            phrases.append(s.strip())
        plan.append({"debut": debut, "fin": len(phrases) - 1})
    pauses[str(len(phrases) + 1)] = 0.6
    phrases.append(MENTION)
    return {"phrases": phrases, "pauses": pauses, "plan": plan}


# ---------------------------------------------------------------- validation
def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    v = type_video(ep)
    if not isinstance(ep.get("sujet"), str) or not ep["sujet"].strip():
        err.append("« sujet » manque (la notion expliquée)")
    pts = ep.get("points")
    if not isinstance(pts, list) or not pts:
        return err + ["« points » manque : liste de points expliqués et sourcés"], av
    lo, hi = POINTS[v]
    if not lo <= len(pts) <= hi:
        err.append(f"{len(pts)} points : il en faut de {lo} à {hi} pour un {v}")
    mots = 0
    titres_vus = set()
    for i, p in enumerate(pts, 1):
        nom = f"point {i}"
        if not isinstance(p, dict) or not isinstance(p.get("titre"), str) or not p["titre"].strip():
            err.append(f"{nom} : « titre » manque")
            continue
        titres_vus.add(commun.norm(p["titre"]))
        tx = p.get("texte")
        if not isinstance(tx, list) or not 1 <= len(tx) <= 3 or not all(isinstance(s, str) and s.strip() for s in tx):
            err.append(f"{nom} : « texte » = liste de 1 à 3 phrases")
            continue
        for s in tx + [p["titre"]]:
            mots += len(s.split())
            if len(s.split()) > 22:
                err.append(f"{nom} : phrase de {len(s.split())} mots, 22 au plus")
            if commun.chiffres(s):
                err.append(f"{nom} : pas de chiffres dans le texte lu (écris les nombres en lettres ; le chiffre à l'écran va dans « chiffre »)")
            if "!" in s:
                err.append(f"{nom} : pas de point d'exclamation (ton sérieux)")
            for rx, msg in ((RE_PROMESSE_FIN, "promesse ou conseil personnalisé refusé"), (commun.RE_PROMESSE, "promesse refusée"), (RE_PRODUIT_MARQUE, "pas de recommandation de marque ou de plateforme")):
                m = rx.search(s)
                if m:
                    err.append(f"{nom} : « {m.group(0).strip()} » : {msg}")
        ch = p.get("chiffre")
        if ch is not None and (not isinstance(ch, dict) or not str(ch.get("valeur", "")).strip() or not str(ch.get("legende", "")).strip()):
            err.append(f"{nom} : « chiffre » = {{valeur, legende}} (la légende dit d'où vient le chiffre)")
        e_s, a_s = commun.controle_sources(p, nom, reseau=reseau, minimum=SOURCES_PAR_POINT)
        err += e_s
        av += a_s
    if len(titres_vus) < len(pts):
        err.append("deux points ont le même titre")
    duree = (mots + len(MENTION.split())) / 2.6 + len(pts) * 1.2
    bornes = DUREE_S[v]
    if not bornes[0] * 0.8 <= duree <= bornes[1] * 1.2:
        err.append(f"environ {duree:.0f} s de voix : un {v} dure de {bornes[0]} à {bornes[1]} s")
    titre = str(ep.get("titre", ""))
    for rx in (RE_PROMESSE_FIN, commun.RE_PROMESSE):
        m = rx.search(titre)
        if m:
            err.append(f"titre : « {m.group(0).strip()} » : aucune promesse")
    if not isinstance(pub, dict):
        err.append("publication.json illisible")
    else:
        desc = str(pub.get("description", ""))
        d = commun.norm(desc)
        if MENTION_NORM not in d:
            err.append(f"description : la phrase « {MENTION} » est obligatoire")
        if "sources" not in d:
            err.append("description : ajoute « Sources : » et la liste des adresses utilisées")
        else:
            manque = [u for p in pts if isinstance(p, dict) for u in (p.get("sources") or []) if isinstance(u, str) and urlparse(u).netloc and urlparse(u).netloc not in desc]
            if manque:
                av.append(f"description : {len(manque)} source(s) des points ne figurent pas dans la liste (ex. {manque[0]})")
        m = RE_PROMESSE_FIN.search(desc) or commun.RE_PROMESSE.search(desc)
        if m:
            err.append(f"description : « {m.group(0).strip()} » : aucune promesse")
        if pub.get("langue") not in (None, "fr"):
            err.append("publication.langue doit valoir « fr »")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not str(mini.get("gros", "")).strip():
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (la notion en 1 à 3 mots) obligatoires")
    elif len(str(mini["gros"]).split()) > 3:
        av.append("miniature : « gros » trop long, 3 mots au plus")
    return err, av


# ---------------------------------------------------------------- rendu
def _taille(v: str) -> tuple[int, int]:
    return (1080, 1920) if v == "short" else (1280, 720)


def _chronologie(timings: dict, plan: list[dict]) -> dict:
    lg = timings["lines"]
    pts = [{"t0": lg[p["debut"]]["start"], "t1": lg[p["fin"]]["end"]} for p in plan]
    return {"points": pts, "t_fin": lg[-1]["start"], "total": float(timings["total"])}


def _domaine(u: str) -> str:
    return urlparse(u).netloc.removeprefix("www.")


def _image(t, ep, chrono, fond, w, h, nom_chaine):
    img = fond.copy()
    d = ImageDraw.Draw(img)
    portrait = h > w
    e = w / 1080 if portrait else w / 1280
    f_chip, f_titre, f_texte, f_gros, f_pt = (rendu.police(int(s * e)) for s in ((44, 84, 52, 200, 32) if portrait else (32, 62, 40, 150, 26)))
    cx, pts = w / 2, ep["points"]
    n = len(pts)
    chip = f"FINANCE PERSO · {ep['sujet']}"[:46]
    cw = d.textlength(chip, font=f_chip) + 70 * e
    d.rounded_rectangle((cx - cw / 2, 40 * e, cx + cw / 2, 40 * e + 84 * e), radius=int(42 * e), fill=STYLE["vert"])
    d.text((cx - d.textlength(chip, font=f_chip) / 2, 40 * e + 16 * e), chip, font=f_chip, fill=STYLE["bandeau"])
    cur = max([i for i, c in enumerate(chrono["points"]) if t >= c["t0"] - 0.25] or [-1])
    for k in range(n):
        r = 10 * e
        x = cx + (k - (n - 1) / 2) * 36 * e
        d.ellipse((x - r, 160 * e - r, x + r, 160 * e + r), fill=STYLE["or"] if k == cur else (STYLE["vert"] if k < cur else STYLE["doux"]))
    # bandeau permanent : mention d'honnêteté
    bh = 74 * e
    d.rectangle((0, h - bh, w, h), fill=STYLE["bandeau"])
    rendu.texte_centre(d, cx, h - bh + 18 * e, "Éducatif · pas un conseil financier", f_pt, STYLE["doux"], w - 80)
    if cur < 0:
        a = rendu.facilite(t / 0.5)
        rendu.texte_centre(d, cx, h * 0.34 + (1 - a) * 60, ep["sujet"], rendu.police(int(110 * e)), "#FFFFFF", w - 120)
        rendu.texte_centre(d, cx, h * 0.34 + 360 * e, f"{n} idées à retenir", f_texte, STYLE["or"], w - 120)
        return img
    if t >= chrono["t_fin"] - 0.25:
        rendu.texte_centre(d, cx, h * 0.22, "À retenir", f_titre, STYLE["or"], w - 100)
        rendu.texte_centre(d, cx, h * 0.22 + 150 * e, "Éducatif, pas un conseil financier.", f_texte, "#FFFFFF", w - 140)
        doms = []
        for p in pts:
            for u in p["sources"]:
                dm = _domaine(u)
                if dm not in doms:
                    doms.append(dm)
        rendu.texte_centre(d, cx, h * 0.22 + 330 * e, "Sources : " + " · ".join(doms[:5]), f_pt, STYLE["doux"], w - 140)
        return img
    c, p = chrono["points"][cur], pts[cur]
    a = rendu.facilite((t - c["t0"] + 0.25) / 0.4)
    y = h * (0.20 if portrait else 0.25) + (1 - a) * 60
    hh = rendu.hauteur_texte(d, p["titre"], f_titre, w - 220)
    d.rounded_rectangle((50, y - 24, w - 50, y + hh + 70 * e), radius=int(34 * e), fill=STYLE["carte"])
    rendu.texte_centre(d, cx, y + 20 * e, p["titre"], f_titre, STYLE["encre"], w - 220)
    ch = p.get("chiffre")
    y2 = y + hh + 130 * e
    if ch:
        a2 = rendu.facilite((t - c["t0"] - 0.6) / 0.4)
        if a2 > 0:
            rendu.texte_centre(d, cx, y2 + (1 - a2) * 40, str(ch["valeur"]), f_gros, STYLE["or"], w - 100)
            rendu.texte_centre(d, cx, y2 + 200 * e, str(ch["legende"]), f_pt, STYLE["doux"], w - 160)
    y3 = h - bh - 150 * e
    rendu.texte_centre(d, cx, y3, "Source : " + _domaine(p["sources"][0]), f_pt, STYLE["doux"], w - 120)
    return img


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = 30) -> Path:
    import json
    v = type_video(ep)
    w, h = _taille(v)
    script = script_voix(ep)
    timings = json.loads((ep_dir / "timings.json").read_text(encoding="utf-8"))
    if len(timings["lines"]) != len(script["phrases"]):
        raise ValueError(f"voix incohérente : {len(timings['lines'])} lignes pour {len(script['phrases'])} phrases")
    chrono = _chronologie(timings, script["plan"])
    voix = rendu.lire_audio(ep_dir / "voice.wav")
    total = max(chrono["total"], len(voix) / rendu.SR) + 0.8
    fond = rendu.degrade(w, h, STYLE["haut"], STYLE["bas"])
    nom = str(profil.get("nom", "")).replace(" (nom à choisir)", "")
    muet = out_dir / "rendu.mp4"
    with rendu.Encodeur(muet, w, h, fps) as enc:
        for i in range(int(total * fps)):
            enc.ecrire(_image(i / fps, ep, chrono, fond, w, h, nom))
    audio = out_dir / "mixage.wav"
    rendu.ecrire_wav(audio, voix)
    final = out_dir / f"{ep['id']}.mp4"
    mes = rendu.muxer(muet, audio, final, LUFS)
    muet.unlink(missing_ok=True)
    audio.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), points=len(pts_ := ep["points"]),
              sources=sorted({u for p in pts_ for u in p["sources"]}))
    return final


def miniature(ep: dict, profil: dict):
    img = rendu.degrade(1280, 720, STYLE["haut"], STYLE["bas"])
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    d.rounded_rectangle((60, 60, 60 + d.textlength("FINANCE PERSO", font=rendu.police(54)) + 70, 150), radius=45, fill=STYLE["vert"])
    d.text((95, 72), "FINANCE PERSO", font=rendu.police(54), fill=STYLE["bandeau"])
    g = str(mini.get("gros", ""))
    rendu.texte_centre(d, 640, 230, g, rendu.police(200 if len(g) <= 8 else 140), STYLE["or"], 1150, ombre="#030A14")
    rendu.texte_centre(d, 640, 540, str(mini.get("texte_haut", "")), rendu.police(70), "#FFFFFF", 1150)
    d.rectangle((0, 668, 1280, 720), fill=STYLE["bandeau"])
    rendu.texte_centre(d, 640, 678, "Éducatif · pas un conseil financier", rendu.police(30), STYLE["doux"], 1200)
    return img
