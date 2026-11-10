"""Format « Apprendre une langue » : petites leçons de phrases utiles pour francophones (anglais d'abord ; es, pt, de, it prêtes côté voix).

Crochets du moteur : `consignes`, `valider_episode`. `CONTROLES_STANDARD = False` : le fond est contrôlé ici, avec une SECONDE PASSE
automatique sur chaque traduction (voir `valider_episode`) : on préfère refuser une phrase douteuse que publier une erreur.
Rendu : `rendre()` (Pillow + ffmpeg). La voix lit la consigne en français puis la phrase dans la langue enseignée (voice.py, clé `langues` par phrase).

episode.json : {id, titre, chaine, theme, video: "short"|"long", format_contenu: "langues", langue_cible: "en", situation: "Au restaurant",
                lecons: [{fr, cible, phonetique?, retraduction, confiance: "sure", sources: [2 urls], check: [mots de `cible`]}],
                miniature: {texte_haut, gros}}
"""
import re
from pathlib import Path

from PIL import ImageDraw

from autopilot import langues

from . import commun, rendu, rendu_remotion

CONTROLES_STANDARD = False
LUFS = -14.0
DUREE_S = {"short": (25, 60), "long": (120, 900)}
LECONS = {"short": (3, 4), "long": (8, 12)}
CIBLES = {"en": "anglais", "es": "espagnol", "pt": "portugais", "de": "allemand", "it": "italien"}
ATTENTE_REPETITION_S = 2.0
VITESSE_LENTE = 0.85
SEUIL_RETRADUCTION = 0.34

STYLE = {"haut": "#FFF6E5", "bas": "#FFDDBF", "encre": "#2B2118", "doux": "#8A7A6A", "carte": "#FFFFFF", "bord": "#F0D2B4", "corail": "#FF6B4A",
         "sarcelle": "#1AA6A0", "jaune": "#FFC83D", "surbrillance": "#FF6B4A"}

RE_GROS_MOT = re.compile(r"\b(merde|putain|connard|salope|encul\w*|fuck\w*|shit\w*|bitch\w*|asshole|mierda|puta|scheisse|scheiße)\b", re.I)
RE_PROMESSE_LANGUE = re.compile(r"couramment|en (?:\w+ )?jours?|sans effort|m[ée]thode miracle|garanti|polyglotte en|parle[rz]? comme un natif", re.I)
RE_SUJET_INTERDIT = re.compile(r"\b(sexe|sexuel|porno|drogue|suicide|religion|pr[ée]sident|[ée]lections?|arme|terroris)\b", re.I)

CONSIGNES = """Chaîne LANGUES (francophones qui apprennent l'ANGLAIS ; `langue_cible` = "en", jamais une autre langue sans que le profil le dise) : un Short = 3 ou 4 phrases utiles pour UNE situation
(au café, à l'aéroport, se présenter…). Un long le vendredi (`"video": "long"`) = 8 à 12 phrases.
Chaque leçon : `fr` (la phrase en français, 90 caractères au plus), `cible` (la phrase dans la langue enseignée, 80 caractères au plus, courante, naturelle, que dirait un natif ; sans chiffres : écris les nombres en lettres),
`phonetique` (facultatif : comment un francophone peut la lire, approximatif), `retraduction`, `confiance`, `sources`, `check`.
SECONDE PASSE OBLIGATOIRE : une fois `cible` écrite, retraduis-la en français SANS regarder `fr`, de façon littérale, et écris le résultat dans `retraduction` ; le contrôle automatique compare les deux et refuse si le sens s'éloigne.
`confiance` = "sure" seulement si tu es certain que la phrase est correcte ET naturelle ; sinon "incertain" (l'épisode sera refusé : remplace la phrase par une dont tu es sûr). Ne devine jamais.
`sources` = 2 pages de 2 sites différents (dictionnaire, Wiktionnaire, Tatoeba, Cambridge…) qui contiennent les mots-clés ; `check` = 1 à 4 mots de `cible` à retrouver dans ces pages.
Mots simples, pas d'argot, pas de gros mots, pas de politique ni de religion. Aucune promesse (« parle couramment en trente jours », « sans effort »). Dis « on apprend » et jamais « tu seras bilingue ».
Titre : le nom de la langue + la situation (« Anglais : commander au café »). Description : la situation, la liste des phrases avec leur traduction, la mention « prononciation approximative », les sources."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def type_video(ep: dict) -> str:
    return "long" if ep.get("video") == "long" else "short"


def langue_cible(ep: dict, profil: dict | None = None) -> str:
    return str(ep.get("langue_cible") or ((profil or {}).get("format_options") or {}).get("langue_cible") or "en")


# ---------------------------------------------------------------- script de la voix
def script_voix(ep: dict) -> dict:
    """Voix : consigne en français, phrase étrangère, phrase étrangère plus lente ; un silence pour répéter avant la leçon suivante."""
    cible = langue_cible(ep)
    ls = ep["lecons"]
    phrases: list[str] = []
    pauses: dict[str, float] = {}
    vitesses: dict[str, float] = {}
    lg: dict[str, str] = {}
    plan = []
    phrases.append(f"Bienvenue ! Aujourd'hui, {ep['situation'].rstrip('.').strip()[:1].lower() + ep['situation'].rstrip('.').strip()[1:]}. {_mot(len(ls)).capitalize()} phrases à retenir.")
    for k, l in enumerate(ls):
        i_f = len(phrases)
        if k:
            pauses[str(i_f + 1)] = ATTENTE_REPETITION_S  # temps pour répéter la leçon précédente
        phrases.append(f"Pour dire : {l['fr'].rstrip('.').strip()}, on dit :")
        i_c = len(phrases)
        phrases.append(l["cible"].strip())
        lg[str(i_c + 1)] = cible
        i_l = len(phrases)
        phrases.append(l["cible"].strip())
        lg[str(i_l + 1)] = cible
        vitesses[str(i_l + 1)] = VITESSE_LENTE
        pauses[str(i_l + 1)] = 0.5
        plan.append({"fr": i_f, "cible": i_c, "lent": i_l})
    phrases.append("Répète-les à voix haute : c'est comme ça qu'on retient. À bientôt !")
    pauses[str(len(phrases))] = ATTENTE_REPETITION_S
    return {"phrases": phrases, "pauses": pauses, "vitesses": vitesses, "langues": lg, "plan": plan}


_MOTS = "zéro une deux trois quatre cinq six sept huit neuf dix onze douze".split()


def _mot(n: int) -> str:
    return _MOTS[n] if 0 <= n < len(_MOTS) else str(n)


# ---------------------------------------------------------------- validation
def _contenu(t: str) -> set[str]:
    vides = langues.mots_vides("fr")
    return {m for m in commun.norm(t).split() if len(m) > 2 and m not in vides}


def similitude(a: str, b: str) -> float:
    """Part de mots porteurs de sens communs entre deux phrases françaises (0 à 1, rapport à la plus courte)."""
    x, y = _contenu(a), _contenu(b)
    if not x or not y:
        return 0.0
    return len(x & y) / min(len(x), len(y))


def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    v = type_video(ep)
    if ep.get("video") not in ("short", "long"):
        err.append("« video » doit valoir « short » ou « long »")
    cible = langue_cible(ep, profil)
    attendue = str(((profil or {}).get("format_options") or {}).get("langue_cible", "en"))
    if cible not in CIBLES:
        err.append(f"langue_cible « {cible} » non prise en charge ({', '.join(CIBLES)})")
    elif cible != attendue:
        err.append(f"langue_cible « {cible} » : cette chaîne enseigne « {attendue} » (format_options du profil)")
    if not isinstance(ep.get("situation"), str) or not 6 <= len(ep["situation"].strip()) <= 70:
        err.append("« situation » (6 à 70 caractères, ex. « Au restaurant ») manque")
    ls = ep.get("lecons")
    if not isinstance(ls, list):
        return err + ["« lecons » manque (liste de phrases)"], av
    lo, hi = LECONS[v]
    if not lo <= len(ls) <= hi:
        err.append(f"{len(ls)} leçon(s) : il en faut de {lo} à {hi} pour un {'Short' if v == 'short' else 'long'}")
    nom_langue = CIBLES.get(cible, "")
    if nom_langue and nom_langue not in commun.norm(str(ep.get("titre", ""))):
        err.append(f"titre : doit contenir le nom de la langue (« {nom_langue} »)")
    vues, cibles_txt = set(), []
    for k, l in enumerate(ls, 1):
        nom = f"leçon {k}"
        if not isinstance(l, dict):
            err.append(f"{nom} : doit être un objet")
            continue
        fr, ci = l.get("fr"), l.get("cible")
        if not isinstance(fr, str) or not 3 <= len(fr.strip()) <= 90:
            err.append(f"{nom} : « fr » de 3 à 90 caractères")
            continue
        if not isinstance(ci, str) or not 2 <= len(ci.strip()) <= 80:
            err.append(f"{nom} : « cible » de 2 à 80 caractères")
            continue
        cibles_txt.append(ci)
        if commun.chiffres(ci) or commun.chiffres(fr):
            err.append(f"{nom} : pas de chiffres (la voix lit des mots : écris les nombres en lettres)")
        if commun.norm(ci) in vues:
            err.append(f"{nom} : phrase en double")
        vues.add(commun.norm(ci))
        txt = fr + " " + ci + " " + str(l.get("phonetique", ""))
        if RE_GROS_MOT.search(txt):
            err.append(f"{nom} : gros mot interdit")
        if RE_SUJET_INTERDIT.search(txt):
            err.append(f"{nom} : sujet interdit sur cette chaîne ({RE_SUJET_INTERDIT.search(txt).group(0)})")
        if RE_PROMESSE_LANGUE.search(txt) or commun.RE_PROMESSE.search(txt):
            err.append(f"{nom} : promesse interdite (« couramment », « sans effort »…)")
        if l.get("phonetique") is not None and (not isinstance(l["phonetique"], str) or len(l["phonetique"]) > 90):
            err.append(f"{nom} : « phonetique » de 90 caractères au plus")
        # ---- seconde passe : le sens de la phrase étrangère doit retomber sur le français ----
        if l.get("confiance") != "sure":
            err.append(f"{nom} : confiance « {l.get('confiance')} » : remplace cette phrase par une dont tu es certain (un doute = pas de publication)")
        rt = l.get("retraduction")
        if not isinstance(rt, str) or not rt.strip():
            err.append(f"{nom} : « retraduction » manque (seconde passe : retraduis `cible` sans regarder `fr`)")
        elif commun.norm(rt) == commun.norm(ci):
            err.append(f"{nom} : la retraduction est la phrase étrangère recopiée, pas une retraduction en français")
        elif similitude(fr, rt) < SEUIL_RETRADUCTION:
            err.append(f"{nom} : la retraduction « {rt.strip()[:50]} » ne correspond pas à « {fr.strip()[:50]} » : traduction douteuse, refais la phrase")
        check = l.get("check")
        if isinstance(check, list) and check:
            mots = set(commun.norm(ci).split())
            for c in check:
                if isinstance(c, str) and commun.norm(c) and not set(commun.norm(c).split()) <= mots:
                    err.append(f"{nom} : le mot à vérifier « {c} » n'est pas dans la phrase étrangère")
        e2, a2 = commun.controle_sources(l, nom, reseau)
        err += e2
        av += a2
    if cibles_txt and cible in CIBLES and cible in langues.LANGUES and not langues.langue_plausible(" ".join(cibles_txt), cible):
        err.append(f"les phrases ne ressemblent pas à la langue « {cible} » (restées en français ?)")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not str(mini.get("gros", "")).strip():
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (un mot de la langue enseignée, ex. « Hello ») obligatoires")
    if isinstance(pub, dict) and pub.get("langue") not in (None, "fr"):
        err.append("publication.langue doit valoir « fr » (le public parle français)")
    if isinstance(pub, dict) and "approximative" not in commun.norm(str(pub.get("description", ""))) and any(l.get("phonetique") for l in ls if isinstance(l, dict)):
        av.append("description : ajoute « prononciation approximative » quand tu donnes une transcription phonétique")
    return err, av


# ---------------------------------------------------------------- rendu
def _taille(v: str) -> tuple[int, int]:
    return (1080, 1920) if v == "short" else (1280, 720)


def _chronologie(timings: dict, plan: list[dict]) -> dict:
    lg = timings["lines"]
    out = []
    for k, p in enumerate(plan):
        suite = lg[plan[k + 1]["fr"]]["start"] if k + 1 < len(plan) else lg[-1]["start"]
        out.append({"t_f": lg[p["fr"]]["start"], "t_c": lg[p["cible"]]["start"], "t_l": lg[p["lent"]]["start"], "fin_l": lg[p["lent"]]["end"], "suite": suite,
                    "mots_c": lg[p["cible"]]["words"], "mots_l": lg[p["lent"]]["words"]})
    return {"lecons": out, "t_outro": lg[-1]["start"], "total": float(timings["total"])}


def _mot_actif(mots: list[dict], n: int, t: float) -> int:
    """Index du mot dit à l'instant t (le dernier commencé), recalé si le nombre de mots entendus diffère du texte."""
    if not mots:
        return -1
    i = max([j for j, m in enumerate(mots) if t >= m["start"] - 0.02] or [-1])
    if i < 0:
        return -1
    return min(n - 1, round(i * (n - 1) / max(1, len(mots) - 1))) if len(mots) != n else i


def _image(t, ep, chrono, fond, w, h, nom_chaine):
    img = fond.copy()
    d = ImageDraw.Draw(img)
    portrait = h > w
    e = w / 1080 if portrait else w / 1280
    f_chip, f_fr, f_cible, f_ph, f_pt, f_gros = (rendu.police(int(s * e)) for s in ((46, 54, 96, 44, 34, 150) if portrait else (34, 40, 74, 34, 28, 120)))
    cx = w / 2
    cible = langue_cible(ep)
    ls = ep["lecons"]
    n = len(ls)
    # en-tête : langue + situation
    chip = f"{CIBLES.get(cible, cible).upper()} · {ep['situation']}"
    cw = d.textlength(chip, font=f_chip) + 70 * e
    d.rounded_rectangle((cx - cw / 2, 40 * e, cx + cw / 2, 40 * e + 84 * e), radius=int(42 * e), fill=STYLE["corail"])
    d.text((cx - d.textlength(chip, font=f_chip) / 2, 40 * e + 16 * e), chip, font=f_chip, fill="#FFFFFF")
    cur = max([i for i, c in enumerate(chrono["lecons"]) if t >= c["t_f"] - 0.2] or [-1])
    for k in range(n):
        r = 11 * e
        x = cx + (k - (n - 1) / 2) * 40 * e
        d.ellipse((x - r, 160 * e - r, x + r, 160 * e + r), fill=STYLE["corail"] if k == cur else (STYLE["sarcelle"] if k < cur else STYLE["bord"]))
    d.text((cx - d.textlength(nom_chaine, font=f_pt) / 2, h - 80 * e), nom_chaine, font=f_pt, fill=STYLE["doux"])
    if cur < 0:
        a = rendu.facilite(t / 0.5)
        rendu.texte_centre(d, cx, h * 0.38 + (1 - a) * 60, ep["situation"], rendu.police(int(100 * e)), STYLE["encre"], w - 120)
        rendu.texte_centre(d, cx, h * 0.38 + 330 * e, f"{n} phrases pour {CIBLES.get(cible, cible)}", f_fr, STYLE["corail"], w - 120)
        return img
    if t >= chrono["t_outro"] - 0.2:
        rendu.texte_centre(d, cx, h * 0.36, "À toi !", f_gros, STYLE["corail"], w - 100)
        rendu.texte_centre(d, cx, h * 0.36 + 200 * e, "Répète à voix haute", f_fr, STYLE["encre"], w - 140)
        return img
    c, l = chrono["lecons"][cur], ls[cur]
    # carte française
    a = rendu.facilite((t - c["t_f"] + 0.2) / 0.4)
    txt_fr = l["fr"]
    hf = rendu.hauteur_texte(d, txt_fr, f_fr, w - 200)
    y_fr = h * (0.17 if portrait else 0.22) + (1 - a) * 60
    d.rounded_rectangle((60, y_fr - 22, w - 60, y_fr + hf + 70 * e), radius=int(36 * e), fill=STYLE["carte"], outline=STYLE["bord"], width=4)
    d.text((90, y_fr - 6), "EN FRANÇAIS", font=f_pt, fill=STYLE["doux"])
    rendu.texte_centre(d, cx, y_fr + 44 * e, txt_fr, f_fr, STYLE["encre"], w - 200)
    # carte de la langue enseignée, mot par mot
    if t >= c["t_c"] - 0.05:
        a2 = rendu.facilite((t - c["t_c"] + 0.05) / 0.4)
        lent = t >= c["t_l"] - 0.05
        mots_t = c["mots_l"] if lent else c["mots_c"]
        mots = l["cible"].split()
        actif = _mot_actif(mots_t, len(mots), t) if t < (c["fin_l"] if lent else c["t_l"]) else len(mots)
        y0 = y_fr + hf + 70 * e + 70 * e + (1 - a2) * 70
        lignes_c = rendu.lignes(d, l["cible"], f_cible, w - 200)
        hc = len(lignes_c) * f_cible.size * 1.2
        d.rounded_rectangle((60, y0 - 26, w - 60, y0 + hc + (150 * e if l.get("phonetique") else 80 * e)), radius=int(40 * e), fill=STYLE["carte"], outline=STYLE["jaune"], width=8)
        d.text((90, y0 - 10), CIBLES.get(cible, cible).upper() + (" · plus lentement" if lent else ""), font=f_pt, fill=STYLE["sarcelle"])
        y = y0 + 44 * e
        idx = 0
        for ln in lignes_c:
            x = cx - d.textlength(ln, font=f_cible) / 2
            for mot in ln.split():
                couleur = STYLE["surbrillance"] if idx == actif else STYLE["encre"]
                d.text((x, y), mot, font=f_cible, fill=couleur)
                x += d.textlength(mot + " ", font=f_cible)
                idx += 1
            y += f_cible.size * 1.2
        if l.get("phonetique"):
            d.text((cx - d.textlength("« " + l["phonetique"] + " »", font=f_ph) / 2, y + 10 * e), "« " + l["phonetique"] + " »", font=f_ph, fill=STYLE["doux"])
        # silence de répétition : « Répète ! »
        if t >= c["fin_l"] + 0.1 and t < c["suite"]:
            pulse = 1 + 0.06 * (0.5 + 0.5 * __import__("math").sin(t * 8))
            txt = "Répète !"
            fr_ = rendu.police(int(84 * e * pulse))
            yy = min(h - 330 * e, y + 170 * e)
            d.rounded_rectangle((cx - 250 * e, yy, cx + 250 * e, yy + 130 * e), radius=int(65 * e), fill=STYLE["sarcelle"])
            d.text((cx - d.textlength(txt, font=fr_) / 2, yy + 14 * e), txt, font=fr_, fill="#FFFFFF")
    return img


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = 30) -> Path:
    """Vidéo finale de la leçon : voix + images ; retourne le chemin du mp4."""
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
    moteur = "pillow"
    if rendu_remotion.disponible():
        try:  # rendu « créateur » (Remotion) ; le long passe en 720p / 24 i/s pour tenir dans le temps de GitHub Actions
            wr, hr, fr = (w, h, fps) if v == "short" else (1280, 720, 24)
            props = rendu_remotion.props_langue(ep, timings, script["plan"], chrono, wr, hr, fr, total, nom, CIBLES.get(langue_cible(ep, profil), ""))
            rendu_remotion.rendre_video("Fmt-Langue", props, muet)
            moteur = "remotion"
        except Exception as ex:  # noqa: BLE001 - on retombe sur le rendu léger plutôt que de perdre l'épisode
            qa.setdefault("alertes_rendu", []).append(f"remotion indisponible, rendu Pillow : {str(ex)[:200]}")
            muet.unlink(missing_ok=True)
    if moteur == "pillow":
        with rendu.Encodeur(muet, w, h, fps) as enc:
            for i in range(int(total * fps)):
                enc.ecrire(_image(i / fps, ep, chrono, fond, w, h, nom))
    qa["moteur_rendu"] = moteur
    audio = out_dir / "mixage.wav"
    rendu.ecrire_wav(audio, voix)
    final = out_dir / f"{ep['id']}.mp4"
    mes = rendu.muxer(muet, audio, final, LUFS)
    muet.unlink(missing_ok=True)
    audio.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), lecons=len(ep["lecons"]), langue_cible=langue_cible(ep, profil))
    return final


def miniature(ep: dict, profil: dict):
    w, h = 1280, 720
    img = rendu.degrade(w, h, STYLE["haut"], STYLE["bas"])
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    cible = langue_cible(ep, profil)
    d.ellipse((860, -160, 1440, 420), fill="#FFD2B8")
    d.rounded_rectangle((60, 60, 60 + d.textlength(CIBLES.get(cible, cible).upper(), font=rendu.police(54)) + 70, 150), radius=45, fill=STYLE["corail"])
    d.text((95, 72), CIBLES.get(cible, cible).upper(), font=rendu.police(54), fill="#FFFFFF")
    g = str(mini.get("gros", "Hello"))
    fonte = rendu.police(220 if len(g) <= 6 else 150)
    rendu.texte_centre(d, 640, 210, g, fonte, STYLE["corail"], 1100, ombre="#FFFFFF")
    rendu.texte_centre(d, 640, 520, str(mini.get("texte_haut", "")), rendu.police(80), STYLE["encre"], 1100)
    return img
