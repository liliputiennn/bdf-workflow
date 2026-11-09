"""Format « Quiz et devinettes » : Shorts de trois questions (9:16) et, le samedi, un quiz de dix questions (16:9).

Crochets du moteur (chaines.HOOKS_FORMAT) : `consignes`, `valider_episode`. `CONTROLES_STANDARD = False` : pas de scènes ni de faits au sens standard,
le fond est contrôlé ici (réponse juste ET sourcée, mauvaises réponses plausibles, questions qui ne périment pas).
Rendu : `rendre()` (Pillow + ffmpeg, voir rendu.py), appelé par `fabrique.py`. Aucune image externe, aucune musique : rien à créditer.

episode.json : {id, titre, chaine, theme, video: "short"|"long", format_contenu: "quiz",
                manches: [{question, options: [3 ou 4], bonne: index (0 = première), explication, sources: [2 urls], check: [mots]}],
                miniature: {texte_haut, gros}}
"""
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import commun, rendu, synth

CONTROLES_STANDARD = False
VIDEO_PAR_DEFAUT = "short"
LUFS = -14.0
DUREE_S = {"short": (20, 60), "long": (90, 900)}
MANCHES = {"short": (3, 4), "long": (8, 12)}
PAUSE_REFLEXION_S = {"short": 3.0, "long": 5.0}
LETTRES = "ABCD"

STYLE = {"haut": "#14123A", "bas": "#2B1166", "carte": "#241B5C", "bord": "#4B3BA8", "accent": "#FFD23F", "cyan": "#2EE6D6",
         "vert": "#35D07F", "rouge": "#FF5C7A", "encre": "#FFFFFF", "doux": "#B9B2F0"}

RE_PERIME = re.compile(r"actuel|en ce moment|aujourd.hui|r[ée]cent|dernier|nouveau|cette ann[ée]e|record|plus (?:grand|haut|long|rapide|cher) du monde", re.I)
RE_SUJET_INTERDIT = re.compile(r"\b(sexe|sexuel|porno|drogue|alcool|suicide|massacre|g[ée]nocide|terroris|pr[ée]sident|[ée]lections?|religion|dieu|maladie|m[ée]dicament|cancer)\b", re.I)

CONSIGNES = """Chaîne QUIZ : un Short = 3 questions de culture générale (ou un quiz de 10 questions le samedi, "video": "long").
Écris le JSON `manches` (voir le schéma ci-dessus dans le module) ; la voix lira : la question, les réponses A B C, un silence de réflexion, la réponse et UNE phrase d'explication.
Questions : 12 à 120 caractères, finissent par « ? », mots simples d'un enfant de dix ans. 3 réponses (ou 4) de 40 caractères au plus, toutes plausibles, une seule juste ; varie la place de la bonne réponse (jamais la même lettre partout).
Chaque question a 2 sources (2 sites différents) et `check` : les mots de la bonne réponse à retrouver dans les pages. Un second contrôle automatique relit la page : si elle ne dit pas la réponse, l'épisode est refusé.
Interdit : question qui vieillit (« actuellement », « le plus récent », « record », « cette année »), politique, religion, santé, violence, sexe, alcool, drogue. Pas de piège, pas de question à plusieurs réponses justes, pas de promesse de gain.
Un quiz doit rester varié : une seule thématique par épisode mais des questions qui n'ont aucun lien entre elles (pas de réponse donnée par la question d'avant).
Titre : le mot « quiz » + le thème, 60 caractères au plus. Description : le thème, « Réponds en commentaire : combien de bonnes réponses ? », puis les sources."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def type_video(ep: dict) -> str:
    return "long" if ep.get("video") == "long" else "short"


# ---------------------------------------------------------------- script de la voix
def script_voix(ep: dict) -> dict:
    """Texte lu par la voix, dans l'ordre, avec le silence de réflexion avant chaque réponse. `plan` relie chaque manche à ses phrases (indices de 0)."""
    v = type_video(ep)
    ms = ep["manches"]
    phrases: list[str] = []
    pauses: dict[int, float] = {}
    plan = []
    n = len(ms)
    phrases.append("Quiz du jour. " + ("Une question, trois réponses." if n == 1 else f"{_mot(n).capitalize()} questions. Prêt ?"))
    for k, m in enumerate(ms):
        lettre = LETTRES[m["bonne"]]
        deb = "Première question." if k == 0 else ("Dernière question." if k == n - 1 and n > 1 else "Question suivante.") if v == "short" else f"Question {_mot(k + 1)}."
        i_q = len(phrases)
        phrases.append(f"{deb} {m['question']}")
        i_o = len(phrases)
        phrases.append(" ".join(f"Réponse {LETTRES[i]} : {o.rstrip('.')}." for i, o in enumerate(m["options"])))
        i_r = len(phrases)
        phrases.append(f"La bonne réponse est la {lettre} : {m['options'][m['bonne']].rstrip('.')}.")
        pauses[i_r + 1] = PAUSE_REFLEXION_S[v]  # voice.py : silence avant la phrase n (1 = première)
        i_e = len(phrases)
        phrases.append(m["explication"].strip())
        plan.append({"q": i_q, "opts": i_o, "rep": i_r, "expl": i_e})
    phrases.append("Combien de bonnes réponses as-tu eues ? Dis-le en commentaire.")
    return {"phrases": phrases, "pauses": {str(k): s for k, s in pauses.items()}, "plan": plan}


_MOTS = "zéro une deux trois quatre cinq six sept huit neuf dix onze douze".split()


def _mot(n: int) -> str:
    return _MOTS[n] if 0 <= n < len(_MOTS) else str(n)


# ---------------------------------------------------------------- validation
def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    v = type_video(ep)
    ms = ep.get("manches")
    if ep.get("video") not in ("short", "long"):
        err.append("« video » doit valoir « short » ou « long »")
    if not isinstance(ms, list):
        return err + ["« manches » manque (liste de questions)"], av
    lo, hi = MANCHES[v]
    if not lo <= len(ms) <= hi:
        err.append(f"{len(ms)} question(s) : il en faut de {lo} à {hi} pour un {'Short' if v == 'short' else 'quiz long'}")
    if "quiz" not in commun.norm(str(ep.get("titre", ""))):
        err.append("titre : doit contenir le mot « quiz »")
    vues_q, bonnes, longs_bonnes = set(), [], 0
    for k, m in enumerate(ms, 1):
        nom = f"question {k}"
        if not isinstance(m, dict):
            err.append(f"{nom} : doit être un objet")
            continue
        q, opts, b, ex = m.get("question"), m.get("options"), m.get("bonne"), m.get("explication")
        if not isinstance(q, str) or not 12 <= len(q.strip()) <= 120 or not q.strip().endswith("?"):
            err.append(f"{nom} : 12 à 120 caractères et finit par « ? »")
        else:
            if RE_PERIME.search(q) or RE_PERIME.search(str(ex)):
                err.append(f"{nom} : la réponse peut vieillir (« actuel », « dernier », « record »…) : choisis une question vraie pour toujours")
            if commun.norm(q) in vues_q:
                err.append(f"{nom} : question en double")
            vues_q.add(commun.norm(q))
        if not isinstance(opts, list) or len(opts) not in (3, 4) or not all(isinstance(o, str) and 1 <= len(o.strip()) <= 40 for o in opts):
            err.append(f"{nom} : 3 ou 4 réponses de 1 à 40 caractères")
            continue
        if len({commun.norm(o) for o in opts}) != len(opts):
            err.append(f"{nom} : deux réponses identiques")
        if not isinstance(b, int) or isinstance(b, bool) or not 0 <= b < len(opts):
            err.append(f"{nom} : « bonne » doit être l'index (0 = première) de la bonne réponse")
            continue
        bonnes.append(b)
        if len(opts[b]) == max(len(o) for o in opts) and len(opts[b]) > min(len(o) for o in opts) + 8:
            longs_bonnes += 1
        if not isinstance(ex, str) or not 15 <= len(ex.strip()) <= 170:
            err.append(f"{nom} : « explication » de 15 à 170 caractères (une phrase)")
        txt = " ".join([str(q)] + [str(o) for o in opts] + [str(ex)])
        if RE_SUJET_INTERDIT.search(txt):
            err.append(f"{nom} : sujet interdit sur cette chaîne ({RE_SUJET_INTERDIT.search(txt).group(0)})")
        if commun.RE_PROMESSE.search(txt):
            err.append(f"{nom} : promesse de gain ou de résultat interdite")
        if any(re.search(r"toutes les|aucune de|les deux", o, re.I) for o in opts):
            err.append(f"{nom} : pas de réponse « toutes / aucune / les deux » (ambigu)")
        # second contrôle : les mots à retrouver dans la page doivent être ceux de la bonne réponse (ou de son explication), pas d'une mauvaise
        check = m.get("check") if isinstance(m.get("check"), list) else []
        bonne_txt = commun.norm(opts[b] + " " + str(ex))
        mauvaises = " ".join(commun.norm(o) for i, o in enumerate(opts) if i != b)
        for c in check:
            if isinstance(c, str) and commun.norm(c) and commun.norm(c) not in bonne_txt:
                err.append(f"{nom} : le mot à vérifier « {c} » n'est ni dans la bonne réponse ni dans l'explication")
        if check and all(isinstance(c, str) and commun.norm(c) in mauvaises and commun.norm(c) not in commun.norm(opts[b]) for c in check):
            err.append(f"{nom} : les mots à vérifier sont ceux d'une MAUVAISE réponse")
        e2, a2 = commun.controle_sources(m, nom, reseau)
        err += e2
        av += a2
    if len(bonnes) >= 3 and len(set(bonnes)) < 2:
        err.append("la bonne réponse est toujours à la même place : varie A, B et C")
    if bonnes and longs_bonnes * 2 > len(bonnes):
        av.append("la bonne réponse est souvent la plus longue : égalise la longueur des réponses")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not str(mini.get("gros", "")).strip():
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (le mot ou signe le plus frappant) obligatoires")
    if isinstance(pub, dict) and pub.get("langue") not in (None, "fr"):
        err.append("publication.langue doit valoir « fr »")
    return err, av


# ---------------------------------------------------------------- rendu
def _taille(v: str) -> tuple[int, int]:
    return (1080, 1920) if v == "short" else (1280, 720)


def _chronologie(ep: dict, timings: dict, plan: list[dict]) -> dict:
    lg = timings["lines"]
    manches = []
    for k, p in enumerate(plan):
        suite = lg[plan[k + 1]["q"]]["start"] if k + 1 < len(plan) else lg[-1]["start"]
        manches.append({"t_q": lg[p["q"]]["start"], "t_o": lg[p["opts"]]["start"], "fin_o": lg[p["opts"]]["end"], "t_r": lg[p["rep"]]["start"],
                        "t_e": lg[p["expl"]]["start"], "fin": min(suite, lg[p["expl"]]["end"] + 1.0)})
    return {"manches": manches, "t_outro": lg[-1]["start"], "total": float(timings["total"])}


class _Fond:
    def __init__(self, w: int, h: int):
        self.img = rendu.degrade(w, h, STYLE["haut"], STYLE["bas"])
        rng = np.random.default_rng(7)
        d = ImageDraw.Draw(self.img)
        for _ in range(60):
            x, y, r = int(rng.integers(0, w)), int(rng.integers(0, h)), int(rng.integers(2, 6))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(60, 50, 140))


def _bouton(d, x0, y0, x1, y1, lettre, texte, etat, fonte_l, fonte_t):
    """etat : normal | bonne | faux."""
    fond = {"normal": STYLE["carte"], "bonne": STYLE["vert"], "faux": "#1B1546"}[etat]
    bord = {"normal": STYLE["bord"], "bonne": "#FFFFFF", "faux": "#2A2260"}[etat]
    d.rounded_rectangle((x0, y0, x1, y1), radius=36, fill=fond, outline=bord, width=5)
    h = y1 - y0
    cx, cy = x0 + h / 2, y0 + h / 2
    d.ellipse((cx - h * 0.32, cy - h * 0.32, cx + h * 0.32, cy + h * 0.32), fill=STYLE["accent"] if etat != "faux" else "#3A3080")
    d.text((cx - d.textlength(lettre, font=fonte_l) / 2, cy - fonte_l.size * 0.6), lettre, font=fonte_l, fill="#14123A" if etat != "faux" else "#7A70C0")
    couleur = STYLE["encre"] if etat != "faux" else "#7A70C0"
    if etat == "bonne":
        couleur = "#06301A"
    lg = rendu.lignes(d, texte, fonte_t, int(x1 - x0 - h - 30))
    y = cy - len(lg) * fonte_t.size * 1.1 / 2
    for ln in lg:
        d.text((x0 + h + 8, y), ln, font=fonte_t, fill=couleur)
        y += fonte_t.size * 1.1


def _image(t: float, ep: dict, chrono: dict, fond: _Fond, w: int, h: int, nom_chaine: str) -> Image.Image:
    img = fond.img.copy()
    d = ImageDraw.Draw(img)
    portrait = h > w
    echelle = w / 1080 if portrait else w / 1280
    f_titre, f_q, f_o, f_l, f_pt = (rendu.police(int(s * echelle)) for s in ((110, 66, 52, 54, 34) if portrait else (120, 54, 42, 44, 30)))
    ms = ep["manches"]
    n = len(ms)
    cx = w / 2
    # points de progression
    for k in range(n):
        r = 14 * echelle
        x = cx + (k - (n - 1) / 2) * 50 * echelle
        actif = [i for i, c in enumerate(chrono["manches"]) if t >= c["t_q"] - 0.3]
        cur = actif[-1] if actif else -1
        d.ellipse((x - r, 60 * echelle - r, x + r, 60 * echelle + r), fill=STYLE["accent"] if k == cur else (STYLE["cyan"] if k < cur else STYLE["bord"]))
    d.text((cx - d.textlength(nom_chaine, font=f_pt) / 2, h - 90 * echelle), nom_chaine, font=f_pt, fill=STYLE["doux"])
    premiere = chrono["manches"][0]["t_q"] - 0.3
    if t < premiere:  # carte d'ouverture
        a = rendu.facilite(t / 0.5)
        rendu.texte_centre(d, cx, h * 0.30 + (1 - a) * 80, "QUIZ", rendu.police(int(210 * echelle)), STYLE["accent"], w - 100, ombre="#0A0830")
        rendu.texte_centre(d, cx, h * 0.30 + 250 * echelle, str(ep.get("miniature", {}).get("texte_haut", "")), f_q, STYLE["encre"], w - 140)
        return img
    if t >= chrono["t_outro"] - 0.2:
        a = rendu.facilite((t - chrono["t_outro"] + 0.2) / 0.5)
        rendu.texte_centre(d, cx, h * 0.34 + (1 - a) * 60, "Ton score ?", rendu.police(int(130 * echelle)), STYLE["accent"], w - 100, ombre="#0A0830")
        rendu.texte_centre(d, cx, h * 0.34 + 190 * echelle, "Dis-le en commentaire", f_q, STYLE["encre"], w - 140)
        return img
    k = max(i for i, c in enumerate(chrono["manches"]) if t >= c["t_q"] - 0.3)
    c, m = chrono["manches"][k], ms[k]
    a = rendu.facilite((t - c["t_q"] + 0.3) / 0.45)
    y_q = (h * 0.07 if portrait else h * 0.10) + (1 - a) * 70
    haut = rendu.hauteur_texte(d, m["question"], f_q, w - 140)
    d.rounded_rectangle((50, y_q - 25, w - 50, y_q + haut + 35), radius=40, fill=STYLE["carte"], outline=STYLE["bord"], width=5)
    rendu.texte_centre(d, cx, y_q, m["question"], f_q, STYLE["encre"], w - 140)
    nb = len(m["options"])
    if portrait:
        y0 = y_q + haut + 90 * echelle
        hb, ecart = 170 * echelle, 34 * echelle
        zones = [(60, y0 + i * (hb + ecart), w - 60, y0 + i * (hb + ecart) + hb) for i in range(nb)]
        y_timer = y0 + nb * (hb + ecart) + 20
    else:
        y0 = y_q + haut + 50
        hb, lb = 120, (w - 3 * 50) / 2
        zones = [(50 + (i % 2) * (lb + 50), y0 + (i // 2) * (hb + 30), 50 + (i % 2) * (lb + 50) + lb, y0 + (i // 2) * (hb + 30) + hb) for i in range(nb)]
        y_timer = y0 + 2 * (hb + 30) + 10
    revele = t >= c["t_r"]
    for i, z in enumerate(zones):
        if t < c["t_o"] + 0.18 * i:
            continue
        etat = "normal" if not revele else ("bonne" if i == m["bonne"] else "faux")
        s = rendu.facilite((t - c["t_o"] - 0.18 * i) / 0.3)
        _bouton(d, z[0] + (1 - s) * 120, z[1], z[2] + (1 - s) * 120, z[3], LETTRES[i], m["options"][i], etat, f_l, f_o)
    if c["fin_o"] <= t < c["t_r"]:  # compte à rebours dans le silence de réflexion
        reste = c["t_r"] - t
        total = max(0.5, c["t_r"] - c["fin_o"])
        r = 80 * echelle
        cy = min(y_timer + r + 10, h - 220 * echelle) if portrait else min(y_timer + r, h - 100)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=STYLE["bord"], width=14)
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * (reste / total), fill=STYLE["accent"], width=14)
        s = str(math.ceil(reste))
        d.text((cx - d.textlength(s, font=f_q) / 2, cy - f_q.size * 0.6), s, font=f_q, fill=STYLE["encre"])
    if t >= c["t_e"]:
        a = rendu.facilite((t - c["t_e"]) / 0.4)
        haut_e = rendu.hauteur_texte(d, m["explication"], f_o, w - 200)
        y_e = (min(y_timer, h - 260 * echelle - haut_e) if portrait else h - haut_e - 100) + (1 - a) * 40
        d.rounded_rectangle((60, y_e - 22, w - 60, y_e + haut_e + 22), radius=30, fill="#1B1546", outline=STYLE["cyan"], width=4)
        rendu.texte_centre(d, cx, y_e, m["explication"], f_o, STYLE["encre"], w - 200)
    return img


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = 30) -> Path:
    """Vidéo finale du quiz à partir de `voice.wav` et `timings.json` de l'épisode. Retourne le chemin du mp4."""
    v = type_video(ep)
    w, h = _taille(v)
    script = script_voix(ep)
    timings = rendu_json(ep_dir / "timings.json")
    if len(timings["lines"]) != len(script["phrases"]):
        raise ValueError(f"voix incohérente : {len(timings['lines'])} lignes pour {len(script['phrases'])} phrases")
    chrono = _chronologie(ep, timings, script["plan"])
    voix = rendu.lire_audio(ep_dir / "voice.wav")
    total = max(chrono["total"], len(voix) / rendu.SR) + 0.8
    fond = _Fond(w, h)
    nom = str(profil.get("nom", "")).replace(" (nom à choisir)", "")
    muet = out_dir / "rendu.mp4"
    with rendu.Encodeur(muet, w, h, fps) as enc:
        for i in range(int(total * fps)):
            enc.ecrire(_image(i / fps, ep, chrono, fond, w, h, nom))
    # bruitages : tic-tac dans le silence de réflexion, « ding » à la réponse
    piste = np.zeros(int(total * rendu.SR) + rendu.SR, dtype=np.float32)
    piste[: len(voix)] += voix
    for c in chrono["manches"]:
        for s in range(int(max(0, c["t_r"] - c["fin_o"]))):
            _poser(piste, synth.note(660, 0.12, "xylophone"), c["t_r"] - 1 - s, 0.22)
        _poser(piste, synth.note(880, 0.6, "boite") + synth.note(1320, 0.6, "boite") * 0.5, c["t_r"], 0.35)
    audio = out_dir / "mixage.wav"
    rendu.ecrire_wav(audio, piste[: int(total * rendu.SR)])
    final = out_dir / f"{ep['id']}.mp4"
    mes = rendu.muxer(muet, audio, final, LUFS)
    muet.unlink(missing_ok=True)
    audio.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), questions=len(ep["manches"]))
    return final


def _poser(piste: np.ndarray, son: np.ndarray, t: float, gain: float) -> None:
    i = int(max(0.0, t) * rendu.SR)
    piste[i:i + len(son)] += son[: max(0, len(piste) - i)] * gain


def rendu_json(chemin: Path) -> dict:
    import json
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- miniature
def miniature(ep: dict, profil: dict) -> Image.Image:
    w, h = 1280, 720
    img = rendu.degrade(w, h, STYLE["haut"], STYLE["bas"])
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    for i, c in enumerate((STYLE["bord"], "#3A2C8A")):
        d.ellipse((900 + i * 120, -200 + i * 60, 1500 + i * 120, 400 + i * 60), fill=c)
    rendu.texte_centre(d, 400, 70, str(mini.get("texte_haut", "")).upper(), rendu.police(74), STYLE["cyan"], 700, ombre="#0A0830")
    rendu.texte_centre(d, 400, 230, "QUIZ", rendu.police(250), STYLE["accent"], 760, ombre="#0A0830")
    # trois pastilles de réponse + point d'interrogation géant
    for i, lettre in enumerate("ABC"):
        x, y = 70 + i * 250, 560
        d.rounded_rectangle((x, y, x + 220, y + 100), radius=28, fill=STYLE["carte"], outline=STYLE["bord"], width=4)
        d.ellipse((x + 14, y + 16, x + 82, y + 84), fill=STYLE["accent"])
        d.text((x + 48 - d.textlength(lettre, font=rendu.police(46)) / 2, y + 22), lettre, font=rendu.police(46), fill="#14123A")
    g = str(mini.get("gros", "?"))[:3]
    d.text((1010 - d.textlength(g, font=rendu.police(420)) / 2, 120), g, font=rendu.police(420), fill=STYLE["encre"])
    return img
