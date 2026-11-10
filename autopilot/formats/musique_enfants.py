"""Format « Musique pour enfants » : petites chansons ORIGINALES à chanter (karaoké), mélodie jouée par un instrument synthétisé par du code.

Choix de licence (relu sur les fiches officielles le 2026-11-09) :
- le son est produit ici même (synth.py : boîte à musique, xylophone, flûte douce ; accompagnement de basse) : aucune licence tierce, rien à créditer ;
- MusicGen (Meta) : poids sous CC-BY-NC 4.0 = INTERDIT (non commercial) ; Stable Audio Open : licence communautaire de Stability AI (conditions, inscription)
  = écarté ; ACE-Step v1 (Apache-2.0) et YuE (Apache-2.0) seraient admissibles mais ne sont PAS branchés : GPU lourd, voix chantée française d'enfants non
  vérifiable ici, et une voix chantée générée sur une chaîne pour enfants est le risque le plus élevé de la politique de YouTube. Voir la spec.
- les paroles sont écrites par le rédacteur (originales, jamais copiées) ; aucune comptine ni chanson existante : un garde-fou refuse les mélodies qui
  ressemblent à des airs connus.

Crochets du moteur : `consignes`, `valider_episode`. `CONTROLES_STANDARD = False`. Pas de voix (script_voix vide) : les paroles s'affichent, syllabe par syllabe.
episode.json : {id, titre, chaine, theme, video: "short"|"long", format_contenu: "musique_enfants", pour_enfants: true,
                chanson: {tempo, tonalite, instrument, strophes: {"c1": {lignes: [{paroles: "Le pe|tit chat dort", notes: [degrés], rythme: [temps]}]}, "r": {...}},
                          ordre: ["c1", "r", ...]}, miniature: {texte_haut, gros}}
Syllabes séparées par « | » dans un mot, mots par des espaces ; une note par syllabe ; chaque ligne dure 4 ou 8 temps.
"""
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import commun, rendu, synth

CONTROLES_STANDARD = False
LUFS = -16.0
DUREE_S = {"short": (20, 60), "long": (90, 900)}
TONIQUES = {"do": 261.63, "re": 293.66, "fa": 349.23, "sol": 392.00}
INSTRUMENTS = ("boite", "xylophone", "flute")
TEMPO = (60, 110)
TEMPS_VALIDES = (0.5, 1, 1.5, 2, 3, 4)
INTRO_TEMPS = 4
FIN_S = 2.5

STYLE = {"ciel_haut": "#9ADBFF", "ciel_bas": "#FFF3D6", "colline1": "#7ED87A", "colline2": "#4FBF6A", "soleil": "#FFD84A", "encre": "#2F2A55", "doux": "#7C77A8",
         "accent": "#FF5E8A", "carte": "#FFFFFF", "cyan": "#38C6E0"}

RE_MOT_INTERDIT = re.compile(r"peur|mort|tuer|tue\b|sang|monstre|arme|guerre|fant[ôo]me|m[ée]chant|bagarre|alcool|\bvin\b|bi[èe]re|cigarette|drogue|argent|ach[èe]te|"
                             r"gagner|disney|pok[ée]mon|mickey|coca|mcdonald|nintendo|youtube|tiktok|netflix|lego|abonne|likez?|clique|promo|dangereu|pleure|cauchemar", re.I)
RE_URL = re.compile(r"https?://|www\.|\.com\b|\.fr\b", re.I)

# Airs connus (intervalles en degrés d'une gamme) : une suite de 5 intervalles identique = trop ressemblant, refusé.
AIRS_CONNUS = {
    "Ah ! vous dirai-je, maman (Brille, petite étoile)": [0, 4, 0, 1, 0, -1, -2, 0, -1, 0, -1, 0, -1, 0],
    "Frère Jacques": [1, 1, -2, 0, 1, 1, -2, 2, 1, 1, -2, 1, 1],
    "Au clair de la lune": [0, 0, 1, 1, -1, -1, 2, -1, 0, -1],
    "Joyeux anniversaire": [0, 1, -1, 3, -1],
    "Sur le pont d'Avignon": [0, 1, 1, 1, -1, 0, 0],
    "Do, ré, mi (La mélodie du bonheur)": [1, 1, -2, 1, 1, 1, -1],
}

CONSIGNES = """Chaîne MUSIQUE POUR ENFANTS (3 à 8 ans) : tu composes de petites chansons ORIGINALES à chanter (karaoké : la mélodie est jouée, les paroles s'affichent syllabe par syllabe). Un Short = un couplet et un refrain (20 à 60 secondes) ; un long = la chanson entière (1 min 30 à 15 min).
Contenu pour enfants : mots simples, phrases courtes, des animaux, des saisons, des gestes (taper des mains, sauter), les couleurs, les nombres, se laver les mains, ranger ses jouets. Gentil, joyeux, jamais effrayant.
Interdit : peur, mort, violence, monstre, arme, alcool, argent, achats, marques, personnages ou chansons existants, appel à s'abonner ou à liker, promesse de résultat, tout lien dans la description. Pas de comptine connue ni de mélodie qui y ressemble : tout est original (un contrôle compare ta mélodie à des airs connus et refuse).
Format du champ `chanson` (voir le module) : `tempo` 60 à 110, `tonalite` do, re, fa ou sol, `instrument` boite, xylophone ou flute, `strophes` (un couplet "c1", un refrain "r"…), `ordre` (ex. ["c1","r","c2","r"]).
Chaque ligne : `paroles` avec les syllabes séparées par « | » (« Le pe|tit chat dort ») ; `notes` : UN degré de gamme par syllabe (1 = tonique, 5 = quinte, 8 = octave ; maximum 5 degrés d'écart entre deux notes, tessiture d'une octave ; reste facile à chanter pour un enfant) ; `rythme` : une durée en temps par note (0.5, 1, 1.5, 2, 3 ou 4) ; une ligne dure 4 ou 8 temps. Le refrain répète les mêmes paroles et la même mélodie à chaque passage.
Titre : « Chanson … pour enfants » ou « Comptine … » (70 caractères au plus). Description : de quoi parle la chanson, « Chanson originale à chanter avec les paroles à l'écran. », une ligne sur la voix et la musique créées avec des outils informatiques ; AUCUN lien. La chaîne est déclarée « conçue pour les enfants » : les commentaires sont désactivés par YouTube, ne cherche pas à en provoquer."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def type_video(ep: dict) -> str:
    return "long" if ep.get("video") == "long" else "short"


def script_voix(ep: dict) -> dict:
    return {"phrases": []}  # pas de voix : la mélodie est jouée, les paroles s'affichent


# ---------------------------------------------------------------- partition
def syllabes(paroles: str) -> list[tuple[str, int]]:
    """[(syllabe, index du mot)] pour « Le pe|tit chat dort »."""
    out = []
    for m, mot in enumerate(str(paroles).split()):
        for s in mot.split("|"):
            out.append((s, m))
    return out


def lignes_dans_l_ordre(chanson: dict) -> list[dict]:
    return [l for cle in chanson["ordre"] for l in chanson["strophes"][cle]["lignes"]]


def duree_chanson_s(chanson: dict) -> float:
    temps = sum(sum(l["rythme"]) for l in lignes_dans_l_ordre(chanson))
    return (INTRO_TEMPS + temps) * 60.0 / chanson["tempo"] + FIN_S


def partition(chanson: dict) -> dict:
    """Calendrier : notes (début, durée, degré), lignes (début, fin, syllabes avec leur début/fin) en secondes."""
    beat = 60.0 / chanson["tempo"]
    t = INTRO_TEMPS * beat
    notes, lignes = [], []
    for k, l in enumerate(lignes_dans_l_ordre(chanson)):
        debut, syl = t, []
        for (s, m), deg, r in zip(syllabes(l["paroles"]), l["notes"], l["rythme"]):
            notes.append((t, r * beat, deg, k))
            syl.append({"s": s, "mot": m, "debut": t, "fin": t + r * beat})
            t += r * beat
        lignes.append({"debut": debut, "fin": t, "syl": syl, "paroles": l["paroles"]})
    return {"notes": notes, "lignes": lignes, "fin": t + FIN_S, "beat": beat}


# ---------------------------------------------------------------- validation
def _intervalles(notes: list) -> list[int]:
    return [b - a for a, b in zip(notes, notes[1:])]


def _contient(grand: list[int], motif: list[int], n: int = 5) -> bool:
    for i in range(len(motif) - n + 1):
        m = motif[i:i + n]
        if any(grand[j:j + n] == m for j in range(len(grand) - n + 1)):
            return True
    return False


def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    v = type_video(ep)
    if ep.get("video") not in ("short", "long"):
        err.append("« video » doit valoir « short » ou « long »")
    if ep.get("pour_enfants") is not True:
        err.append("« pour_enfants » doit valoir true (chaîne déclarée « conçue pour les enfants »)")
    ch = ep.get("chanson")
    if not isinstance(ch, dict):
        return err + ["« chanson » manque"], av
    if isinstance(ch.get("tempo"), bool) or not isinstance(ch.get("tempo"), int) or not TEMPO[0] <= ch["tempo"] <= TEMPO[1]:
        err.append(f"« tempo » : entier de {TEMPO[0]} à {TEMPO[1]}")
    if ch.get("tonalite") not in TONIQUES:
        err.append(f"« tonalite » doit être l'une de : {', '.join(TONIQUES)}")
    if ch.get("instrument") not in INSTRUMENTS:
        err.append(f"« instrument » doit être l'un de : {', '.join(INSTRUMENTS)}")
    st, ordre = ch.get("strophes"), ch.get("ordre")
    if not isinstance(st, dict) or not st or not isinstance(ordre, list) or not ordre or any(o not in st for o in ordre):
        return err + ["« strophes » (dictionnaire) et « ordre » (liste de noms de strophes existantes) obligatoires"], av
    toutes: list[int] = []
    paroles_all: list[str] = []
    for nom, s in st.items():
        ls = s.get("lignes") if isinstance(s, dict) else None
        if not isinstance(ls, list) or not 2 <= len(ls) <= 6:
            err.append(f"strophe {nom} : 2 à 6 lignes")
            continue
        for i, l in enumerate(ls, 1):
            n = f"strophe {nom}, ligne {i}"
            if not isinstance(l, dict) or not isinstance(l.get("paroles"), str) or not isinstance(l.get("notes"), list) or not isinstance(l.get("rythme"), list):
                err.append(f"{n} : paroles, notes et rythme obligatoires")
                continue
            syl = syllabes(l["paroles"])
            paroles_all.append(l["paroles"].replace("|", ""))
            if not syl or any(not x or len(x) > 12 for x, _ in syl):
                err.append(f"{n} : syllabes vides ou de plus de 12 caractères")
            if not len(syl) == len(l["notes"]) == len(l["rythme"]):
                err.append(f"{n} : {len(syl)} syllabe(s), {len(l['notes'])} note(s), {len(l['rythme'])} durée(s) : une note et une durée par syllabe")
                continue
            if any(isinstance(x, bool) or not isinstance(x, int) or not -2 <= x <= 12 for x in l["notes"]):
                err.append(f"{n} : notes = degrés entiers de -2 à 12 (1 = tonique)")
                continue
            if any(x not in TEMPS_VALIDES for x in l["rythme"]):
                err.append(f"{n} : durées autorisées : {', '.join(map(str, TEMPS_VALIDES))}")
                continue
            if sum(l["rythme"]) not in (4, 8):
                err.append(f"{n} : la ligne dure {sum(l['rythme'])} temps, il en faut 4 ou 8")
            if max(l["notes"]) - min(l["notes"]) > 7:
                err.append(f"{n} : tessiture de plus d'une octave : trop difficile à chanter")
            if any(abs(b - a) > 5 for a, b in zip(l["notes"], l["notes"][1:])):
                err.append(f"{n} : saut de plus de 5 degrés entre deux notes")
            if max(len(m.split("|")) for m in l["paroles"].split()) > 3:
                err.append(f"{n} : un mot de plus de 3 syllabes (reste simple pour des enfants)")
            toutes += l["notes"]
            for air, motif in AIRS_CONNUS.items():
                if _contient(_intervalles(l["notes"]), motif):
                    err.append(f"{n} : la mélodie ressemble à « {air} » : compose un air original")
    texte = " ".join(paroles_all) + " " + str(ep.get("titre", ""))
    m = RE_MOT_INTERDIT.search(texte)
    if m:
        err.append(f"paroles ou titre : « {m.group(0)} » interdit sur une chaîne pour enfants (peur, violence, argent, marque, appel à s'abonner…)")
    if commun.RE_PROMESSE.search(texte):
        err.append("promesse interdite")
    if commun.chiffres(texte):
        err.append("pas de chiffres dans les paroles ni le titre (écris les nombres en lettres)")
    if not err:
        d = duree_chanson_s(ch)
        bornes = DUREE_S[v]
        if not bornes[0] <= d <= bornes[1]:
            err.append(f"la chanson dure {d:.0f} s : il faut de {bornes[0]} à {bornes[1]} s pour un {'Short' if v == 'short' else 'long'}")
        if len(set(toutes)) < 3:
            err.append("mélodie trop pauvre : au moins trois notes différentes")
    if not re.search(r"chanson|comptine", commun.norm(str(ep.get("titre", "")))):
        err.append("titre : doit contenir « chanson » ou « comptine »")
    if isinstance(pub, dict):
        desc = str(pub.get("description", ""))
        if RE_URL.search(desc):
            err.append("description : aucun lien sur une chaîne pour enfants")
        if RE_MOT_INTERDIT.search(desc):
            err.append(f"description : « {RE_MOT_INTERDIT.search(desc).group(0)} » interdit (appel à s'abonner, marque, argent…)")
        if "originale" not in commun.norm(desc):
            err.append("description : la mention « Chanson originale à chanter avec les paroles à l'écran. » est obligatoire")
        if pub.get("langue") not in (None, "fr"):
            err.append("publication.langue doit valoir « fr »")
    else:
        err.append("publication.json illisible")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not str(mini.get("gros", "")).strip():
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (1 à 3 mots) obligatoires")
    return err, av


# ---------------------------------------------------------------- audio
def piste_audio(ep: dict, graine: int = 0) -> np.ndarray:
    ch = ep["chanson"]
    p = partition(ch)
    tonique = TONIQUES[ch["tonalite"]]
    total = p["fin"]
    ev = [(t, d * 0.97, synth.frequence(deg, tonique)) for t, d, deg, _ in p["notes"]]
    melodie = synth.melodie(ev, total, ch["instrument"])
    # accompagnement : basse douce sur chaque temps fort (accords 1, 4, 5, 1), petit arpège d'introduction
    beat = p["beat"]
    basse = []
    racines = (1, 4, 5, 1)
    for i in range(INTRO_TEMPS):
        basse.append((i * beat, beat * 0.9, synth.frequence((1, 3, 5, 3)[i] + 7, tonique)))
    for k, l in enumerate(p["lignes"]):
        r = racines[k % 4]
        n_temps = round((l["fin"] - l["debut"]) / beat)
        for b in range(0, n_temps, 2):
            basse.append((l["debut"] + b * beat, beat * 1.8, synth.frequence(r - 7, tonique)))
    accomp = synth.melodie(basse, total, "boite")
    x = melodie * 0.8 + accomp * 0.45
    return (0.8 * x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)


# ---------------------------------------------------------------- images
def _taille(v: str) -> tuple[int, int]:
    return (1080, 1920) if v == "short" else (1280, 720)


class _Decor:
    def __init__(self, w: int, h: int, graine: int):
        self.w, self.h = w, h
        self.fond = rendu.degrade(w, h, STYLE["ciel_haut"], STYLE["ciel_bas"])
        d = ImageDraw.Draw(self.fond)
        for c, y, a in ((STYLE["colline1"], 0.86, 0.10), (STYLE["colline2"], 0.94, 0.07)):
            pts = [(x, h * y - h * a * (0.5 + 0.5 * math.sin(x / w * 4 + graine))) for x in range(0, w + 10, 10)]
            d.polygon(pts + [(w, h), (0, h)], fill=c)
        r = np.random.default_rng(graine)
        self.formes = [(float(r.uniform(0, 1)), float(r.uniform(0.05, 0.6)), float(r.uniform(18, 46)), float(r.uniform(0.2, 0.6)), ("#FFFFFF", "#FFD1E3", "#C8F0FF", "#FFF2A8")[int(r.integers(0, 4))]) for _ in range(9)]

    def image(self, t: float) -> Image.Image:
        img = self.fond.copy()
        d = ImageDraw.Draw(img)
        cx, cy = self.w * 0.14, self.h * 0.09
        for i in range(12):  # soleil : rayons qui tournent doucement
            a = t * 0.3 + i * math.pi / 6
            d.line((cx + math.cos(a) * 70, cy + math.sin(a) * 70, cx + math.cos(a) * 112, cy + math.sin(a) * 112), fill=STYLE["soleil"], width=10)
        d.ellipse((cx - 62, cy - 62, cx + 62, cy + 62), fill=STYLE["soleil"])
        for (x0, y0, r, vit, c) in self.formes:  # nuages et bulles qui dérivent
            x = ((x0 + vit * t / 40) % 1.2 - 0.1) * self.w
            y = self.h * y0 + 12 * math.sin(t * 0.8 + x0 * 9)
            d.ellipse((x - r * 1.6, y - r, x + r * 1.6, y + r), fill=c)
            d.ellipse((x - r * 0.4, y - r * 1.5, x + r * 1.1, y + r * 0.4), fill=c)
        return img


def _image(t: float, ep: dict, p: dict, decor: _Decor, w: int, h: int, nom: str) -> Image.Image:
    img = decor.image(t)
    d = ImageDraw.Draw(img)
    portrait = h > w
    e = w / 1080 if portrait else w / 1280
    f_l, f_p, f_n = rendu.police(int((92 if portrait else 70) * e)), rendu.police(int((54 if portrait else 40) * e)), rendu.police(int(34 * e))
    cx = w / 2
    lignes = p["lignes"]
    cur = max([i for i, l in enumerate(lignes) if t >= l["debut"] - 0.5] or [-1])
    if cur < 0 or t >= lignes[-1]["fin"] + 0.3:
        titre = ep["miniature"]["gros"] if cur < 0 else "Bravo !"
        a = rendu.facilite(t / 0.6) if cur < 0 else 1.0
        rendu.texte_centre(d, cx, h * 0.34 + (1 - a) * 80, titre, rendu.police(int(130 * e)), STYLE["accent"], w - 100, ombre="#FFFFFF")
        if cur < 0:
            rendu.texte_centre(d, cx, h * 0.34 + 300 * e, "Chante avec nous !", f_p, STYLE["encre"], w - 120)
    else:
        l = lignes[cur]
        y = h * (0.40 if portrait else 0.36)
        if cur + 1 < len(lignes):  # ligne suivante, en petit, pour préparer l'enfant
            rendu.texte_centre(d, cx, h * (0.70 if portrait else 0.74), lignes[cur + 1]["paroles"].replace("|", ""), f_p, STYLE["doux"], w - 140)
        mots: dict[int, list] = {}
        for s in l["syl"]:
            mots.setdefault(s["mot"], []).append(s)
        # mise en ligne mot par mot, syllabe par syllabe : la syllabe chantée se colore et grossit un peu
        espace = d.textlength(" ", font=f_l)
        largeurs = [sum(d.textlength(s["s"], font=f_l) for s in ms) for ms in mots.values()]
        lignes_mots, cur_l, wcur = [], [], 0.0
        for ms, lw in zip(mots.values(), largeurs):
            if cur_l and wcur + lw > w - 140:
                lignes_mots.append((cur_l, wcur - espace))
                cur_l, wcur = [], 0.0
            cur_l.append(ms)
            wcur += lw + espace
        lignes_mots.append((cur_l, wcur - espace))
        for ligne, lw in lignes_mots:
            x = cx - lw / 2
            for ms in ligne:
                for s in ms:
                    chantee = t >= s["debut"]
                    en_cours = s["debut"] <= t < s["fin"]
                    couleur = STYLE["accent"] if chantee else STYLE["encre"]
                    dy = -14 * e * math.sin(math.pi * (t - s["debut"]) / max(0.2, s["fin"] - s["debut"])) if en_cours else 0
                    d.text((x + 3, y + dy + 3), s["s"], font=f_l, fill="#FFFFFF")
                    d.text((x, y + dy), s["s"], font=f_l, fill=couleur)
                    x += d.textlength(s["s"], font=f_l)
                x += espace
            y += f_l.size * 1.3
    d.text((cx - d.textlength(nom, font=f_n) / 2, h - 70 * e), nom, font=f_n, fill=STYLE["encre"])
    return img


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = 24) -> Path:
    v = type_video(ep)
    w, h = _taille(v)
    p = partition(ep["chanson"])
    graine = sum(ord(c) for c in ep["id"])
    audio_x = piste_audio(ep, graine)
    total = len(audio_x) / rendu.SR
    decor = _Decor(w, h, graine % 17)
    nom = str(profil.get("nom", "")).replace(" (nom à choisir)", "")
    muet = out_dir / "rendu.mp4"
    with rendu.Encodeur(muet, w, h, fps) as enc:
        for i in range(int(total * fps)):
            enc.ecrire(_image(i / fps, ep, p, decor, w, h, nom))
    wav = out_dir / "mixage.wav"
    rendu.ecrire_wav(wav, audio_x)
    final = out_dir / f"{ep['id']}.mp4"
    mes = rendu.muxer(muet, wav, final, LUFS)
    muet.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), lignes=len(p["lignes"]), tempo=ep["chanson"]["tempo"],
              instrument=ep["chanson"]["instrument"], pour_enfants=True)
    return final


def miniature(ep: dict, profil: dict) -> Image.Image:
    w, h = 1280, 720
    decor = _Decor(w, h, sum(ord(c) for c in ep["id"]) % 17)
    img = decor.image(3.0)
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    rendu.texte_centre(d, 640, 90, str(mini.get("texte_haut", "")).upper(), rendu.police(70), STYLE["encre"], 1100)
    rendu.texte_centre(d, 640, 230, str(mini.get("gros", "")), rendu.police(190 if len(str(mini.get("gros", ""))) <= 10 else 130), STYLE["accent"], 1150, ombre="#FFFFFF")
    for i in range(5):  # notes de musique dessinées (disque + hampe)
        x, y = 200 + i * 220, 560 + 20 * math.sin(i * 1.7)
        d.ellipse((x, y, x + 56, y + 42), fill=STYLE["encre"])
        d.line((x + 52, y + 20, x + 52, y - 90), fill=STYLE["encre"], width=9)
        d.line((x + 52, y - 90, x + 96, y - 60), fill=STYLE["encre"], width=9)
    return img
