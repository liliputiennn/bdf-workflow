"""Format « Musique pour enfants » (chaîne PomPikoBoo) : VRAIES chansons chantées (ACE-Step 1.5, licence MIT) + clip animé façon comptines 3D colorées
avec les deux personnages de la chaîne (petit éléphant rose, cactus vert à fleur rose), paroles à l'écran mot par mot.

Chaîne de fabrication :
 1. le rédacteur écrit les PAROLES (originales) et choisit un style musical dans une liste fermée (aucun nom d'artiste, de chanson ni de personnage connu) ;
 2. `generer_audio` envoie les paroles à un noyau Kaggle GPU (autopilot/cloud/kaggle/lancer_musique.py) : ACE-Step chante, Whisper retranscrit le chant,
    `alignement.py` cale les paroles sur le chant (taux d'appariement = contrôle de qualité : chant intelligible ou non) ;
 3. `rendre` anime les personnages (rebond sur le tempo, bouche pilotée par l'énergie de la voix, bras, clignements), affiche les paroles et normalise le son.

Licences (relues sur les fichiers officiels le 2026-11-10) : ACE-Step 1.5 = MIT (fichier LICENSE du dépôt + fiche Hugging Face, « usage commercial autorisé ») ;
Whisper (faster-whisper) = MIT ; MusicGen (CC-BY-NC) et Stable Audio Open (licence communautaire) restent exclus. Personnages et décor : dessinés par code (pompikoboo.py).

Garde-fous conservés : mots interdits pour enfants, `pour_enfants` obligatoire, pas de chiffres, pas d'appel à s'abonner, pas de comptine ni chanson connue
(liste de titres et de premiers vers refusés ; la ressemblance MÉLODIQUE d'un chant généré ne se vérifie pas par code : écoute humaine avant activation, voir le bilan).
Crochets du moteur : `consignes`, `valider_episode`, `generer_audio`, `rendre`, `miniature`. `CONTROLES_STANDARD = False`.

episode.json : {id, titre, chaine, theme, video: "short"|"long", format_contenu: "musique_enfants", pour_enfants: true,
                chanson: {style: <STYLES>, tempo: 70-130, strophes: {"c1": {"lignes": ["Le petit éléphant danse", ...]}, "r": {...}}, ordre: ["c1","r",...]},
                miniature: {texte_haut, gros}}
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import alignement, commun, pompikoboo, rendu

CONTROLES_STANDARD = False
LUFS = -16.0
DUREE_S = {"short": (25, 80), "long": (90, 480)}
TEMPO = (70, 130)
S_PAR_LIGNE = 5.2  # durée moyenne d'une ligne chantée (estimation pour demander la bonne durée au modèle)
INTRO_S, FIN_S = 6.0, 5.0
MIN_APPARIEMENT = alignement.MIN_APPARIEMENT

# Styles : liste fermée (le texte envoyé au modèle est écrit ici, jamais par le rédacteur : pas de nom d'artiste ni de marque).
STYLES = {
    "comptine_joyeuse": "cheerful children's pop song, nursery rhyme feel, bouncy ukulele, xylophone, glockenspiel, hand claps, bright and happy, simple singalong chorus, warm friendly female vocal, clear diction",
    "danse": "upbeat children's dance song, playful bass, handclaps, bells, energetic and joyful, catchy singalong chorus, warm friendly female vocal, clear diction",
    "berceuse": "gentle children's lullaby, soft music box, warm piano, slow and soothing, tender female vocal, clear diction",
    "balade": "sweet children's folk song, acoustic guitar, light percussion, whistling, cheerful walking rhythm, warm friendly female vocal, clear diction",
}
PERSONNAGES = {"elephant": "Pompi", "cactus": "Piko"}  # à confirmer par l'utilisateur : assets-persos/pompikoboo/persos.json

RE_MOT_INTERDIT = re.compile(r"peur|mort|tuer|tue\b|sang|monstre|arme|guerre|fant[ôo]me|m[ée]chant|bagarre|alcool|\bvin\b|bi[èe]re|cigarette|drogue|argent|ach[èe]te|"
                             r"gagner|disney|pok[ée]mon|mickey|coca|mcdonald|nintendo|youtube|tiktok|netflix|lego|abonne|likez?|clique|promo|dangereu|pleure|cauchemar|cocomelon", re.I)
RE_URL = re.compile(r"https?://|www\.|\.com\b|\.fr\b", re.I)
# Titres et premiers vers de comptines/chansons existantes : refusés tels quels dans les paroles et le titre.
RE_AIR_CONNU = re.compile(r"fr[èe]re jacques|clair de la lune|petite [ée]toile|vous dirai.?je|pont d.avignon|petit navire|souris verte|alouette|meunier|claire fontaine|"
                          r"ainsi font|savez.vous planter|joyeux anniversaire|promenons.nous|baby shark|let it go|roues du bus|wheels on the bus|do r[ée] mi|"
                          r"fais dodo|j.ai du bon tabac|il pleut,? il mouille|dans la ferme|vieux macdonald|marinier|cadet rousselle|ah ! ?vous", re.I)
CONSIGNES = """Chaîne MUSIQUE POUR ENFANTS « PomPikoBoo » (3 à 8 ans) : tu écris les PAROLES de petites chansons ORIGINALES, qu'une IA chantera. Les deux héros de la chaîne sont un petit éléphant rose (Pompi) et un cactus vert à fleur rose (Piko) : ils peuvent apparaître dans les paroles (leurs prénoms, simples).
Un Short = un couplet et un refrain (6 à 10 lignes en tout, 30 à 60 s) ; un long = une chanson entière (couplets et refrains, 2 à 6 minutes).
Contenu : mots très simples, phrases courtes (3 à 8 mots), rimes faciles, beaucoup de répétitions dans le refrain (les enfants chantent avec), des gestes à imiter (taper des mains, sauter, tourner), les animaux, les couleurs, les saisons, se laver les mains, ranger ses jouets. Gentil, joyeux, jamais effrayant.
Interdit : peur, mort, violence, monstre, arme, alcool, argent, achats, marques, personnages ou chansons existants (aucune comptine connue, aucun air connu, rien qui ressemble aux chansons d'autres chaînes), appel à s'abonner ou à liker, promesse de résultat, chiffres (écris les nombres en lettres), tout lien.
Format du champ `chanson` : `style` parmi comptine_joyeuse, danse, berceuse, balade ; `tempo` 70 à 130 ; `strophes` : {"c1": {"lignes": ["…", "…"]}, "r": {"lignes": [...]}} (couplets "c1", "c2"…, refrain "r") de 2 à 8 lignes ; `ordre` (ex. ["c1","r","c2","r"]). Une ligne = un vers chanté sur environ 5 secondes. Le refrain reprend exactement les mêmes paroles à chaque passage.
Titre : « Chanson … pour enfants » ou « Comptine … » (70 caractères au plus). Description : de quoi parle la chanson, « Chanson originale à chanter avec les paroles à l'écran. », une ligne disant que la voix, la musique et les images sont créées avec des outils informatiques ; AUCUN lien. La chaîne est déclarée « conçue pour les enfants » : les commentaires sont désactivés par YouTube, ne cherche pas à en provoquer."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def type_video(ep: dict) -> str:
    return "long" if ep.get("video") == "long" else "short"


def script_voix(ep: dict) -> dict:
    return {"phrases": []}  # la voix est CHANTÉE par le modèle de musique (generer_audio), pas lue par le moteur de voix


# ---------------------------------------------------------------- paroles
def lignes_dans_l_ordre(chanson: dict) -> list[dict]:
    """[{texte, strophe, refrain}] dans l'ordre chanté."""
    out = []
    for cle in chanson["ordre"]:
        for t in chanson["strophes"][cle]["lignes"]:
            out.append({"texte": str(t).replace("|", ""), "strophe": cle, "refrain": cle.lower().startswith("r")})
    return out


def duree_estimee_s(chanson: dict) -> float:
    return INTRO_S + S_PAR_LIGNE * len(lignes_dans_l_ordre(chanson)) + FIN_S


def paroles_balisees(chanson: dict) -> str:
    """Paroles avec balises de structure comprises par ACE-Step ([Verse], [Chorus]…)."""
    blocs, couplets = [], {}
    for cle in chanson["ordre"]:
        if cle.lower().startswith("r"):
            tete = "[Chorus]"
        else:
            couplets.setdefault(cle, len(couplets) + 1)
            tete = f"[Verse {couplets[cle]}]"
        blocs.append(tete + chr(10) + chr(10).join(str(t).replace("|", "") for t in chanson["strophes"][cle]["lignes"]))
    return "[Intro]\n\n" + "\n\n".join(blocs) + "\n\n[Outro]"


def entree_musique(ep: dict) -> dict:
    ch = ep["chanson"]
    return {"caption": STYLES[ch["style"]] + f", {ch['tempo']} bpm, original melody", "paroles": paroles_balisees(ch), "duree": round(duree_estimee_s(ch)),
            "bpm": ch["tempo"], "langue": "fr", "lignes": [l["texte"] for l in lignes_dans_l_ordre(ch)]}


# ---------------------------------------------------------------- validation
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
    if ch.get("style") not in STYLES:
        err.append(f"« style » doit être l'un de : {', '.join(STYLES)}")
    st, ordre = ch.get("strophes"), ch.get("ordre")
    if not isinstance(st, dict) or not st or not isinstance(ordre, list) or not ordre or any(o not in st for o in ordre):
        return err + ["« strophes » (dictionnaire) et « ordre » (liste de noms de strophes existantes) obligatoires"], av
    paroles_all: list[str] = []
    for nom, s in st.items():
        ls = s.get("lignes") if isinstance(s, dict) else None
        if not isinstance(ls, list) or not 2 <= len(ls) <= 8:
            err.append(f"strophe {nom} : 2 à 8 lignes")
            continue
        for i, l in enumerate(ls, 1):
            n = f"strophe {nom}, ligne {i}"
            if not isinstance(l, str) or not l.strip():
                err.append(f"{n} : une ligne de paroles est un texte non vide")
                continue
            mots = l.replace("|", "").split()
            paroles_all.append(" ".join(mots))
            if not 2 <= len(mots) <= 9 or len(" ".join(mots)) > 60:
                err.append(f"{n} : 2 à 9 mots et 60 caractères au plus (phrase courte, chantée sur environ 5 secondes)")
            if any(len(m) > 18 for m in mots):
                err.append(f"{n} : mot de plus de 18 caractères (reste simple pour des enfants)")
    texte = " ".join(paroles_all) + " " + str(ep.get("titre", ""))
    m = RE_MOT_INTERDIT.search(texte)
    if m:
        err.append(f"paroles ou titre : « {m.group(0)} » interdit sur une chaîne pour enfants (peur, violence, argent, marque, appel à s'abonner…)")
    m = RE_AIR_CONNU.search(texte)
    if m:
        err.append(f"paroles ou titre : « {m.group(0)} » ressemble à une chanson ou comptine existante : écris des paroles originales")
    if commun.RE_PROMESSE.search(texte):
        err.append("promesse interdite")
    if commun.chiffres(texte):
        err.append("pas de chiffres dans les paroles ni le titre (écris les nombres en lettres)")
    if not err:
        bornes = DUREE_S[v]
        d = duree_estimee_s(ch)
        if not bornes[0] <= d <= bornes[1]:
            err.append(f"la chanson durera environ {d:.0f} s : il faut de {bornes[0]} à {bornes[1]} s pour un {'Short' if v == 'short' else 'long'}")
        if not any(o.lower().startswith("r") for o in ordre):
            err.append("il faut un refrain (strophe nommée « r »)")
        if len(set(ordre)) == len(ordre) and len(ordre) > 2:
            av.append("aucune strophe n'est reprise : une chanson d'enfants gagne à répéter son refrain")
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


# ---------------------------------------------------------------- audio (cloud)
def _sha(o) -> str:
    return hashlib.sha1(json.dumps(o, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def generer_audio(ep: dict, ep_dir: Path, sans_cloud: bool = False) -> None:
    """Produit ep_dir/chanson.wav (chant + musique) et ep_dir/alignement.json via le noyau Kaggle (ACE-Step + Whisper). Reprise : même entrée = rien à refaire."""
    ep_dir = Path(ep_dir)
    entree = entree_musique(ep)
    marque = ep_dir / "chanson.sha"
    cle = _sha(entree)
    if (ep_dir / "chanson.wav").exists() and (ep_dir / "alignement.json").exists() and (not marque.exists() or marque.read_text().strip() == cle):
        return
    if sans_cloud:
        raise FileNotFoundError("chanson annoncée prête mais chanson.wav / alignement.json absents")
    (ep_dir / "chanson-entree.json").write_text(json.dumps(entree, ensure_ascii=False, indent=1), encoding="utf-8")
    racine = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, str(racine / "cloud" / "kaggle" / "lancer_musique.py"), str(ep_dir)]
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    marque.write_text(cle, encoding="utf-8")


# ---------------------------------------------------------------- images
def _taille(v: str) -> tuple[int, int]:
    return (1080, 1920) if v == "short" else (1280, 720)


STYLE = {"ciel_haut": "#4FC3F7", "ciel_bas": "#E1F5FE", "colline1": "#7CD84A", "colline2": "#4CBF4C", "colline3": "#2FA84F", "soleil": "#FFE14D", "encre": "#3B2A6E",
         "accent": "#FF4F9A", "doux": "#7C6BC4", "orange": "#FF9A2E", "cyan": "#22C7E8"}
COULEURS_NOTES = ("#FF4F9A", "#FFB400", "#22C7E8", "#7C6BC4", "#4CBF4C")


class _Decor:
    def __init__(self, w: int, h: int, graine: int):
        self.w, self.h = w, h
        self.fond = rendu.degrade(w, h, STYLE["ciel_haut"], STYLE["ciel_bas"])
        d = ImageDraw.Draw(self.fond)
        r = np.random.default_rng(graine)
        base = h * 0.66
        for c, y, a in ((STYLE["colline1"], 0.70, 0.07), (STYLE["colline2"], 0.78, 0.06), (STYLE["colline3"], 0.88, 0.05)):
            ph = float(r.uniform(0, 6))
            pts = [(x, h * y - h * a * (0.5 + 0.5 * math.sin(x / w * 3.4 + ph))) for x in range(0, w + 8, 8)]
            d.polygon(pts + [(w, h), (0, h)], fill=c)
            for _ in range(14):  # fleurs semées sur la colline
                fx = float(r.uniform(0.02, 0.98)) * w
                fy = h * y - h * a * (0.5 + 0.5 * math.sin(fx / w * 3.4 + ph)) + float(r.uniform(18, 60))
                col = ("#FFFFFF", "#FF7BB5", "#FFD84A", "#B58CFF")[int(r.integers(0, 4))]
                for k in range(5):
                    ang = k * 1.2566
                    d.ellipse((fx + math.cos(ang) * 11 - 8, fy + math.sin(ang) * 11 - 8, fx + math.cos(ang) * 11 + 8, fy + math.sin(ang) * 11 + 8), fill=col)
                d.ellipse((fx - 6, fy - 6, fx + 6, fy + 6), fill="#FFB400")
        del base
        self.nuages = [(float(r.uniform(0, 1)), float(r.uniform(0.18, 0.5)), float(r.uniform(40, 80)), float(r.uniform(0.3, 0.8))) for _ in range(5)]

    def image(self, t: float) -> Image.Image:
        img = self.fond.copy()
        d = ImageDraw.Draw(img)
        cx, cy = (self.w * 0.84, self.h * 0.34) if self.h > self.w else (self.w * 0.90, self.h * 0.32)
        for i in range(14):  # soleil souriant, rayons qui tournent
            a = t * 0.35 + i * math.pi / 7
            d.line((cx + math.cos(a) * 82, cy + math.sin(a) * 82, cx + math.cos(a) * 128, cy + math.sin(a) * 128), fill=STYLE["soleil"], width=13)
        d.ellipse((cx - 72, cy - 72, cx + 72, cy + 72), fill=STYLE["soleil"])
        d.ellipse((cx - 28, cy - 18, cx - 16, cy - 2), fill=STYLE["encre"])
        d.ellipse((cx + 16, cy - 18, cx + 28, cy - 2), fill=STYLE["encre"])
        d.arc((cx - 30, cy - 12, cx + 30, cy + 34), 20, 160, fill=STYLE["encre"], width=6)
        for (x0, y0, r, vit) in self.nuages:
            x = ((x0 + vit * t / 60) % 1.3 - 0.15) * self.w
            y = self.h * y0
            for dx, dy, rr in ((0, 0, r), (-r * 0.9, r * 0.2, r * 0.7), (r * 0.9, r * 0.25, r * 0.75), (r * 0.2, -r * 0.4, r * 0.7)):
                d.ellipse((x + dx - rr, y + dy - rr * 0.8, x + dx + rr, y + dy + rr * 0.8), fill="#FFFFFF")
        return img


def _notes(img: Image.Image, t: float, beat: float, ox: float, oy: float, e: float, graine: int) -> None:
    """Petites notes de musique qui montent et ondulent depuis le personnage qui chante."""
    d = ImageDraw.Draw(img)
    for k in range(4):
        age = ((t / (beat * 2) + k / 4) % 1.0)
        x = ox + math.sin(age * 6 + k * 1.7 + graine) * 70 * e + (k - 1.5) * 40 * e
        y = oy - age * 420 * e
        col = COULEURS_NOTES[(k + graine) % 5]
        s = 16 * e * (1 - age * 0.3)
        d.ellipse((x - s, y - s * 0.75, x + s, y + s * 0.75), fill=col)
        d.line((x + s * 0.85, y, x + s * 0.85, y - s * 3.1), fill=col, width=max(3, int(s * 0.28)))
        d.line((x + s * 0.85, y - s * 3.1, x + s * 2.0, y - s * 2.3), fill=col, width=max(3, int(s * 0.3)))


def _mots_ligne(d, ligne: dict, f, largeur_max: float):
    """Retourne les lignes d'écran : [[(mot, largeur)], ...]."""
    espace = d.textlength(" ", font=f)
    rangees, cur, wcur = [], [], 0.0
    for m in ligne["mots"]:
        lw = d.textlength(m["m"], font=f)
        if cur and wcur + lw > largeur_max:
            rangees.append((cur, wcur - espace))
            cur, wcur = [], 0.0
        cur.append((m, lw))
        wcur += lw + espace
    rangees.append((cur, wcur - espace))
    return rangees, espace


def _paroles(img, d, t: float, lignes: list[dict], cur: int, w: int, h: int, e: float, portrait: bool) -> None:
    f = rendu.police(int((78 if portrait else 62) * e))
    l = lignes[cur]
    rangees, espace = _mots_ligne(d, l, f, w - 120)
    haut = f.size * 1.35 * len(rangees)
    y0 = h * (0.075 if portrait else 0.06)
    pad = 26
    # bandeau doux blanc translucide derrière les paroles (lisibilité)
    box = (50, int(y0 - pad), w - 50, int(y0 + haut + pad - 10))
    zone = img.crop(box).convert("RGBA")
    ov = Image.new("RGBA", zone.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle((0, 0, zone.width - 1, zone.height - 1), radius=48, fill=(255, 255, 255, 190))
    img.paste(Image.alpha_composite(zone, ov).convert("RGB"), box[:2])
    y = y0
    for rang, lw in rangees:
        x = w / 2 - lw / 2
        for m, mw in rang:
            chantee = t >= m["debut"]
            en_cours = m["debut"] <= t < max(m["fin"], m["debut"] + 0.25)
            dy = -16 * e * math.sin(math.pi * (t - m["debut"]) / max(0.25, m["fin"] - m["debut"])) if en_cours else 0
            col = STYLE["accent"] if chantee else STYLE["encre"]
            d.text((x, y + dy), m["m"], font=f, fill=col, stroke_width=max(3, int(5 * e)), stroke_fill="#FFFFFF")
            x += mw + espace
        y += f.size * 1.35


def _scene(t: float, ep: dict, lignes: list[dict], meta: list[dict], env: np.ndarray, fps: int, decor: _Decor, w: int, h: int, beat: float) -> Image.Image:
    img = decor.image(t)
    d = ImageDraw.Draw(img)
    portrait = h > w
    e = w / 1080 if portrait else w / 1280
    cur = max([i for i, l in enumerate(lignes) if t >= l["debut"] - 0.3] or [-1])
    chante_ligne = cur >= 0 and lignes[cur]["debut"] - 0.1 <= t <= lignes[cur]["fin"] + 0.25
    ouv = float(env[min(len(env) - 1, int(t * fps))]) if chante_ligne else 0.0
    refrain = cur >= 0 and meta[cur]["refrain"]
    # qui chante : l'éléphant et le cactus se relaient d'une ligne à l'autre ; le refrain se chante à deux
    chanteur = None if cur < 0 else "tous" if refrain else ("elephant" if cur % 2 == 0 else "cactus")
    echelle = (0.90 if portrait else 0.72)
    sol = h * (0.93 if portrait else 0.93)
    pos = {"elephant": w * (0.26 if portrait else 0.30), "cactus": w * (0.74 if portrait else 0.70)}
    for nom, ph in (("elephant", 0.0), ("cactus", 0.25)):
        chante = chanteur in ("tous", nom) and chante_ligne
        img_p, dy, _ = pompikoboo.animer(nom, t, beat, ouv if chante else 0.0, chante, ph)
        s = echelle * (1.03 if chante else 1.0)
        sp = img_p.resize((int(img_p.width * s), int(img_p.height * s)), Image.BICUBIC)
        x = int(pos[nom] - sp.width / 2)
        y = int(sol - sp.height + dy * e * echelle)
        ombre = Image.new("RGBA", (int(sp.width * 0.8), int(34 * e)), (0, 0, 0, 0))
        ImageDraw.Draw(ombre).ellipse((0, 0, ombre.width - 1, ombre.height - 1), fill=(20, 80, 40, 90))
        img.paste(ombre, (int(pos[nom] - ombre.width / 2), int(sol - 22 * e)), ombre)
        img.paste(sp, (x, y), sp)
        if chante:
            _notes(img, t, beat, pos[nom], sol - sp.height * 0.75, e, 0 if nom == "elephant" else 2)
    d = ImageDraw.Draw(img)
    if cur < 0 or t >= lignes[-1]["fin"] + 0.4:
        titre = ep["miniature"]["gros"] if cur < 0 else "Bravo !"
        a = rendu.facilite(t / 0.7) if cur < 0 else rendu.facilite((t - lignes[-1]["fin"]) / 0.6)
        rendu.texte_centre(d, w / 2, h * 0.12 - (1 - a) * 60, titre, rendu.police(int(130 * e)), STYLE["accent"], w - 100, ombre="#FFFFFF")
        if cur < 0:
            rendu.texte_centre(d, w / 2, h * 0.12 + 170 * e, "Chante avec nous !", rendu.police(int(58 * e)), STYLE["encre"], w - 120, ombre="#FFFFFF")
    else:
        _paroles(img, ImageDraw.Draw(img), t, lignes, cur, w, h, e, portrait)
    return img


def charger_chanson(ep: dict, ep_dir: Path):
    """(audio mono 48 kHz, lignes alignées, méta des lignes, alignement.json)."""
    ep_dir = Path(ep_dir)
    al = json.loads((ep_dir / "alignement.json").read_text(encoding="utf-8"))
    audio = rendu.lire_audio(ep_dir / "chanson.wav", rendu.SR)
    meta = lignes_dans_l_ordre(ep["chanson"])
    lignes = al["lignes"]
    if len(lignes) != len(meta):
        raise ValueError(f"alignement.json : {len(lignes)} lignes pour {len(meta)} lignes de paroles")
    return audio, lignes, meta, al


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = 24) -> Path:
    v = type_video(ep)
    w, h = _taille(v)
    audio, lignes, meta, al = charger_chanson(ep, ep_dir)
    total = len(audio) / rendu.SR
    env = alignement.enveloppe_voix(audio, rendu.SR, fps)
    beat = 60.0 / ep["chanson"]["tempo"]
    graine = sum(ord(c) for c in ep["id"])
    decor = _Decor(w, h, graine % 17)
    muet = Path(out_dir) / "rendu.mp4"
    with rendu.Encodeur(muet, w, h, fps) as enc:
        for i in range(int(total * fps)):
            enc.ecrire(_scene(i / fps, ep, lignes, meta, env, fps, decor, w, h, beat))
    wav = Path(out_dir) / "mixage.wav"
    rendu.ecrire_wav(wav, np.clip(audio * 0.92, -1, 1))
    final = Path(out_dir) / f"{ep['id']}.mp4"
    mes = rendu.muxer(muet, wav, final, LUFS)
    muet.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), lignes=len(lignes), tempo=ep["chanson"]["tempo"],
              style=ep["chanson"]["style"], appariement=al.get("appariement"), methode_alignement=al.get("methode"), pour_enfants=True)
    if (al.get("appariement") or 0) < MIN_APPARIEMENT:
        qa.setdefault("alertes", []).append(f"chant peu intelligible (appariement paroles/chant {al.get('appariement')}) : à écouter avant publication")
    if al.get("a_ecouter"):
        qa.setdefault("alertes", []).append(str(al["a_ecouter"]))
    return final


def miniature(ep: dict, profil: dict) -> Image.Image:
    w, h = 1280, 720
    decor = _Decor(w, h, sum(ord(c) for c in ep["id"]) % 17)
    img = decor.image(3.0)
    mini = ep.get("miniature") or {}
    for nom, x in (("elephant", 250), ("cactus", 1030)):
        sp = pompikoboo.sprite(nom, 3, False, 2)
        sp = sp.resize((int(sp.width * 0.78), int(sp.height * 0.78)), Image.LANCZOS)
        img.paste(sp, (x - sp.width // 2, h - sp.height + 10), sp)
    d = ImageDraw.Draw(img)
    rendu.texte_centre(d, 640, 36, str(mini.get("texte_haut", "")).upper(), rendu.police(66), STYLE["encre"], 760, ombre="#FFFFFF")
    gros = str(mini.get("gros", ""))
    rendu.texte_centre(d, 640, 190, gros, rendu.police(140 if len(gros) <= 10 else 96), STYLE["accent"], 520, ombre="#FFFFFF")
    return img
