"""Format « Sommeil et relaxation » : de longues vidéos calmes (30 à 180 minutes) = une histoire douce racontée lentement, puis une ambiance sonore
générée par du code (pluie, vagues, vent, forêt de nuit, nappe) sur un décor sombre et très lent.

Rendu LÉGER : une boucle vidéo de 30 s (Pillow, 15 images/s) bouclée par ffmpeg SANS réencodage (`-stream_loop` + `-c:v copy`), une boucle audio de 120 s
sans raccord (bruits périodiques, voir synth.py) bouclée par ffmpeg ; seule l'histoire demande la voix (quelques minutes). Une vidéo de deux heures coûte
donc à peu près ce que coûte une histoire de dix minutes. Aucun modèle musical, aucun échantillon : rien à créditer, rien à vérifier côté licence.

Crochets du moteur : `consignes`, `valider_episode`. `CONTROLES_STANDARD = False`.
episode.json : {id, titre, chaine, theme, video: "long", format_contenu: "sommeil", phrases: [l'histoire, lue lentement],
                ambiance: {type, graine, duree_min}, decor: {type, graine}, miniature: {texte_haut, gros}}
"""
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import commun, rendu, rendu_remotion, synth

CONTROLES_STANDARD = False
LUFS = -23.0
SEUIL_VOIX = 0.85  # voix lente et douce : le contrôle par reconnaissance confond des mots voisins (« Ses » / « Les », score 0,89) sans que l'histoire en souffre ; en dessous de 0,85 la phrase est refaite puis signalée
DUREE_S = {"long": (20 * 60, 3 * 3600 + 180), "short": (20 * 60, 3 * 3600 + 180)}
AMBIANCES = ("pluie", "vagues", "vent", "foret", "nappe")
DECORS = ("nuit-etoilee", "lune-sur-mer", "foret-brume")
MINUTES = (30, 180)
MOTS = (400, 1800)
DEBUT_VOIX_S = 20.0
BOUCLE_AUDIO_S = 120
BOUCLE_VIDEO_S = 30
FPS = 15
VITESSE_VOIX = 0.92
PAUSE_ENTRE_PHRASES_S = 0.7
VOIX_SUR_AMBIANCE_DB = 12  # la voix dépasse l'ambiance de 12 dB

STYLE = {"haut": "#05081A", "bas": "#101B3D", "lune": "#E8E4D0", "etoile": "#B9C4F0", "colline": "#0A1228", "brume": "#2A3A66"}

RE_AGITE = re.compile(r"explos|\bcris?\b|hurl|\bsang\b|\bmort|\btuer\b|peur|danger|urgen|\bvite\b|course|attaqu|monstre|fant[ôo]me|accident|\bfeu\b|incendi|orage|tonnerre|\bguerre\b|panique|terrible|affreux", re.I)
RE_PROMESSE_SANTE = re.compile(r"gu[ée]ri\w*|soign\w*|m[ée]dicament|th[ée]rapie|garanti\w*|miracle|dormir en|endormir en|insomnie (?:disparait|disparaît|guérie)|sans effort", re.I)

CONSIGNES = """Chaîne SOMMEIL : une vidéo longue et calme. Tu écris UNE histoire douce à raconter lentement (champ `phrases`, 400 à 1800 mots, 40 à 200 phrases) ; la vidéo continue ensuite avec une ambiance sonore et un décor très lents, `ambiance.duree_min` de 30 à 180.
Voix : régulière, basse, sans effet (jamais de balise d'émotion). Phrases courtes (22 mots au plus), mots simples, images douces : la nuit, l'eau, les étoiles, un chemin, une lampe, une couverture. Rythme qui ralentit vers la fin ; les dernières phrases parlent de repos et de silence.
Interdit dans l'histoire : bruit soudain, cri, danger, peur, monstre, feu, orage, course, mort, sang, urgence, point d'exclamation, chiffres (écris les nombres en lettres). Rien qui réveille ou inquiète.
Honnêteté : aucune promesse de santé (« guérit l'insomnie », « tu dormiras en dix minutes », « miracle »). La description contient la phrase « Cette vidéo détend mais ne remplace pas un avis médical. » et rien d'autre de médical.
Chaque vidéo est NOUVELLE : une histoire inédite (lieu, personnage, objets différents des précédentes), une `ambiance.type` parmi pluie, vagues, vent, foret, nappe, une `graine` différente (nombre entier), un `decor.type` parmi nuit-etoilee, lune-sur-mer, foret-brume. Pas de série identique : c'est la règle de YouTube contre le contenu répétitif.
Titre : « Histoire pour s'endormir : … » ou « Ambiance … pour dormir », 70 caractères au plus. Description : de quoi parle l'histoire, le type d'ambiance, la durée, la phrase d'honnêteté ci-dessus."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def duree_totale_s(ep: dict) -> float:
    return float(ep["ambiance"]["duree_min"]) * 60


# ---------------------------------------------------------------- script de la voix
def script_voix(ep: dict) -> dict:
    ph = [p.strip() for p in ep["phrases"]]
    return {"phrases": ph, "pauses": {str(i + 1): PAUSE_ENTRE_PHRASES_S for i in range(1, len(ph))},
            "vitesses": {str(i + 1): VITESSE_VOIX for i in range(len(ph))}}


# ---------------------------------------------------------------- validation
def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    if ep.get("video") != "long":
        err.append("« video » doit valoir « long » (les vidéos de sommeil ne sont jamais des Shorts)")
    amb, dec = ep.get("ambiance"), ep.get("decor")
    if not isinstance(amb, dict) or amb.get("type") not in AMBIANCES:
        err.append(f"« ambiance.type » doit être l'un de : {', '.join(AMBIANCES)}")
    else:
        m = amb.get("duree_min")
        if isinstance(m, bool) or not isinstance(m, int) or not MINUTES[0] <= m <= MINUTES[1]:
            err.append(f"« ambiance.duree_min » : entier de {MINUTES[0]} à {MINUTES[1]} minutes")
        if isinstance(amb.get("graine"), bool) or not isinstance(amb.get("graine"), int):
            err.append("« ambiance.graine » : nombre entier (une graine différente par vidéo)")
    if not isinstance(dec, dict) or dec.get("type") not in DECORS:
        err.append(f"« decor.type » doit être l'un de : {', '.join(DECORS)}")
    elif isinstance(dec.get("graine"), bool) or not isinstance(dec.get("graine"), int):
        err.append("« decor.graine » : nombre entier")
    ph = ep.get("phrases")
    if not isinstance(ph, list) or not all(isinstance(p, str) and p.strip() for p in ph):
        return err + ["« phrases » manque : l'histoire à raconter (liste de phrases) est obligatoire (une ambiance seule serait un contenu sans valeur)"], av
    mots = sum(len(p.split()) for p in ph)
    if not 40 <= len(ph) <= 200:
        err.append(f"{len(ph)} phrases : il en faut de 40 à 200")
    if not MOTS[0] <= mots <= MOTS[1]:
        err.append(f"{mots} mots : il en faut de {MOTS[0]} à {MOTS[1]} (environ cinq à quinze minutes de voix lente)")
    for i, p in enumerate(ph, 1):
        if len(p.split()) > 22:
            err.append(f"phrase {i} : {len(p.split())} mots, 22 au plus (phrases courtes et calmes)")
        if "!" in p:
            err.append(f"phrase {i} : pas de point d'exclamation")
        if commun.chiffres(p):
            err.append(f"phrase {i} : pas de chiffres (écris les nombres en lettres)")
        m = RE_AGITE.search(p)
        if m:
            err.append(f"phrase {i} : « {m.group(0)} » est trop agité pour s'endormir")
        m = RE_PROMESSE_SANTE.search(p)
        if m:
            err.append(f"phrase {i} : « {m.group(0)} » : aucune promesse de santé")
    if isinstance(amb, dict) and isinstance(amb.get("duree_min"), int) and mots:
        voix_s = mots / 1.7 + len(ph) * PAUSE_ENTRE_PHRASES_S
        if amb["duree_min"] * 60 < DEBUT_VOIX_S + voix_s + 60:
            err.append(f"l'ambiance ({amb['duree_min']} min) est plus courte que l'histoire (environ {voix_s / 60:.0f} min) : allonge `duree_min`")
    titre = str(ep.get("titre", ""))
    if RE_PROMESSE_SANTE.search(titre):
        err.append("titre : aucune promesse de santé")
    if not isinstance(pub, dict):
        err.append("publication.json illisible")
    else:
        d = commun.norm(str(pub.get("description", "")))
        if "ne remplace pas un avis medical" not in d:
            err.append("description : la phrase « Cette vidéo détend mais ne remplace pas un avis médical. » est obligatoire")
        m = RE_PROMESSE_SANTE.search(str(pub.get("description", "")) + " " + titre)
        if m:
            err.append(f"publication : « {m.group(0)} » : aucune promesse de santé")
        if pub.get("langue") not in (None, "fr"):
            err.append("publication.langue doit valoir « fr »")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not str(mini.get("gros", "")).strip():
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (l'idée de la vidéo en 1 à 3 mots) obligatoires")
    if isinstance(ep.get("miniature"), dict) and mini.get("gros") and len(str(mini["gros"]).split()) > 3:
        av.append("miniature : « gros » trop long, 3 mots au plus pour rester lisible")
    return err, av


# ---------------------------------------------------------------- décor : boucle de 30 s
def _colline(w: int, y0: int, amp: float, graine: int, couleur, d: ImageDraw.ImageDraw, h: int) -> None:
    r = np.random.default_rng(graine)
    p = r.uniform(0, 6.28, 3)
    pts = [(x, y0 - amp * (0.5 + 0.3 * math.sin(x / w * 5 + p[0]) + 0.2 * math.sin(x / w * 11 + p[1]) + 0.1 * math.sin(x / w * 23 + p[2]))) for x in range(0, w + 8, 8)]
    d.polygon(pts + [(w, h), (0, h)], fill=couleur)


class Decor:
    """Décor sombre : tout mouvement est périodique sur BOUCLE_VIDEO_S secondes (la boucle se raccorde sans saut)."""

    def __init__(self, type_: str, graine: int, w: int = 1280, h: int = 720):
        self.type, self.w, self.h = type_, w, h
        r = np.random.default_rng(graine)
        self.fond = rendu.degrade(w, h, STYLE["haut"], STYLE["bas"])
        d = ImageDraw.Draw(self.fond)
        self.lune = (int(r.integers(int(w * 0.62), int(w * 0.88))), int(r.integers(int(h * 0.14), int(h * 0.30))), int(r.integers(46, 70)))
        if type_ == "foret-brume":
            for i, (y, a, c) in enumerate(((0.80, 150, "#0B1A24"), (0.88, 120, "#08141C"), (0.96, 90, "#050D13"))):
                _colline(w, int(h * y), a, graine + i, c, d, h)
        elif type_ == "lune-sur-mer":
            d.rectangle((0, int(h * 0.62), w, h), fill="#0A1636")
        else:
            _colline(w, int(h * 0.92), 130, graine, STYLE["colline"], d, h)
        n = 140 if type_ != "foret-brume" else 70
        self.etoiles = [(int(r.integers(0, w)), int(r.integers(0, int(h * 0.62))), float(r.uniform(1.2, 3.2)), int(r.integers(1, 5)), float(r.uniform(0, 1))) for _ in range(n)]
        self.brume = [(float(r.uniform(0, 1)), float(r.uniform(0.62, 0.9)), float(r.uniform(0.35, 0.7)), int(r.integers(1, 3))) for _ in range(6)]
        halo = Image.new("RGB", (w, h), (0, 0, 0))
        hd = ImageDraw.Draw(halo)
        x, y, rr = self.lune
        hd.ellipse((x - rr * 3, y - rr * 3, x + rr * 3, y + rr * 3), fill=(40, 44, 70))
        self.halo = halo.filter(ImageFilter.GaussianBlur(60))
        # fond + lueur de la lune : fixes, calculés une seule fois
        self.base = Image.fromarray(np.minimum(255, np.asarray(self.fond, dtype=np.int16) + np.asarray(self.halo, dtype=np.int16) // 2).astype(np.uint8))

    def image(self, t: float) -> Image.Image:
        ph = (t % BOUCLE_VIDEO_S) / BOUCLE_VIDEO_S
        img = self.base.copy()  # étoiles qui scintillent par-dessus
        d = ImageDraw.Draw(img)
        x, y, rr = self.lune
        masque = Image.new("L", (self.w, self.h), 0)
        md = ImageDraw.Draw(masque)
        md.ellipse((x - rr, y - rr, x + rr, y + rr), fill=255)
        md.ellipse((x - rr + rr * 0.55, y - rr - 4, x + rr + rr * 0.55, y + rr - 4), fill=0)  # croissant : disque moins un disque décalé
        img.paste(Image.new("RGB", (self.w, self.h), STYLE["lune"]), (0, 0), masque)
        d = ImageDraw.Draw(img)
        for (sx, sy, r, cyc, p0) in self.etoiles:
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * (cyc * ph + p0)))
            c = tuple(int(v * a) for v in rendu.hex_rgb(STYLE["etoile"]))
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=c)
        if self.type == "lune-sur-mer":
            for i in range(14):  # reflet de la lune et vaguelettes qui dérivent
                yy = int(self.h * 0.64) + i * 18 + int(3 * math.sin(2 * math.pi * (ph * 2 + i / 7)))
                ww = int(self.lune[2] * (2.2 - i * 0.1)) + int(10 * math.sin(2 * math.pi * (ph * 3 + i / 5)))
                d.rounded_rectangle((x - ww // 2, yy, x + ww // 2, yy + 5), radius=3, fill=(120, 124, 130) if i < 9 else (70, 80, 110))
        if self.type == "foret-brume":
            ov = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            for (x0, yb, a, cyc) in self.brume:
                cx = ((x0 + cyc * ph) % 1.0) * (self.w + 600) - 300
                od.ellipse((cx - 330, self.h * yb - 36, cx + 330, self.h * yb + 36), fill=(*rendu.hex_rgb(STYLE["brume"]), int(70 * a)))
            img = Image.alpha_composite(img.convert("RGBA"), ov.filter(ImageFilter.GaussianBlur(26))).convert("RGB")
        return img


# ---------------------------------------------------------------- audio
def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))) + 1e-9)


def boucle_audio(ep: dict, chemin: Path) -> None:
    amb = ep["ambiance"]
    x = synth.ambiance(amb["type"], BOUCLE_AUDIO_S, amb["graine"])
    rendu.ecrire_wav(chemin, x)


def mixer(boucle: Path, voix: Path, sortie: Path, total_s: float) -> None:
    """Ambiance bouclée sur toute la durée + histoire après DEBUT_VOIX_S, voix à +12 dB de l'ambiance, fondu d'entrée et de sortie."""
    amb = rendu.lire_audio(boucle)
    v = rendu.lire_audio(voix)
    g_amb = (_rms(v) * 10 ** (-VOIX_SUR_AMBIANCE_DB / 20)) / _rms(amb)
    delai = int(DEBUT_VOIX_S * 1000)
    fc = (f"[0:a]volume={g_amb:.5f},afade=t=in:st=0:d=12[b];[1:a]adelay={delai}|{delai}[v];[b][v]amix=inputs=2:duration=first:normalize=0,"
          f"afade=t=out:st={max(0.0, total_s - 40):.2f}:d=40,alimiter=limit=0.95[m]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(boucle), "-i", str(voix), "-filter_complex", fc, "-map", "[m]",
                    "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", str(sortie)], check=True)


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = FPS) -> Path:
    total = duree_totale_s(ep)
    boucle_v = out_dir / "boucle.mp4"
    moteur = "pillow"
    if rendu_remotion.disponible():
        try:  # décor « créateur » (Remotion), boucle parfaite de {BOUCLE_VIDEO_S} s
            rendu_remotion.rendre_video("Fmt-Boucle", rendu_remotion.props_boucle("sommeil", ep["decor"]["type"], ep["decor"]["graine"], 1280, 720, fps, BOUCLE_VIDEO_S), boucle_v, crf=26)
            moteur = "remotion"
        except Exception as ex:  # noqa: BLE001 - repli sur le rendu léger
            qa.setdefault("alertes_rendu", []).append(f"remotion indisponible, rendu Pillow : {str(ex)[:200]}")
            boucle_v.unlink(missing_ok=True)
    if moteur == "pillow":
        decor = Decor(ep["decor"]["type"], ep["decor"]["graine"])
        with rendu.Encodeur(boucle_v, decor.w, decor.h, fps, crf=32) as enc:
            for i in range(int(BOUCLE_VIDEO_S * fps)):
                enc.ecrire(decor.image(i / fps))
    qa["moteur_rendu"] = moteur
    boucle_a = out_dir / "boucle.wav"
    boucle_audio(ep, boucle_a)
    mix = out_dir / "mixage.m4a"
    mixer(boucle_a, ep_dir / "voice.wav", mix, total)
    final = out_dir / f"{ep['id']}.mp4"
    mes = rendu.muxer(boucle_v, mix, final, LUFS, boucle_video=True, duree_s=total)
    for f in (boucle_v, boucle_a, mix):
        f.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), ambiance=ep["ambiance"]["type"],
              histoire_mots=sum(len(p.split()) for p in ep["phrases"]), taille_mo=round(final.stat().st_size / 1e6, 1))
    return final


def miniature(ep: dict, profil: dict) -> Image.Image:
    decor = Decor(ep["decor"]["type"], ep["decor"]["graine"])
    img = decor.image(7.0).convert("RGB")
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    fonte = rendu.police(150 if len(str(mini.get("gros", ""))) <= 12 else 110)
    rendu.texte_centre(d, 460, 250, str(mini.get("gros", "")), fonte, "#F3EFD8", 780, ombre="#02030A")
    rendu.texte_centre(d, 460, 130, str(mini.get("texte_haut", "")).upper(), rendu.police(56), "#9FB0E8", 780)
    duree = f"{ep['ambiance']['duree_min'] // 60} h" if ep["ambiance"]["duree_min"] % 60 == 0 and ep["ambiance"]["duree_min"] >= 60 else f"{ep['ambiance']['duree_min']} min"
    d.rounded_rectangle((60, 600, 60 + d.textlength(duree, font=rendu.police(60)) + 60, 690), radius=30, fill="#1B2A5C")
    d.text((90, 612), duree, font=rendu.police(60), fill="#E8E4D0")
    return img
