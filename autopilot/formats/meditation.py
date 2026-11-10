"""Format « Méditation guidée » : des vidéos de 10 à 40 minutes = respiration et relaxation guidées d'une voix lente (longues pauses entre les phrases)
sur un décor doux animé en boucle (aube, lavande, un soleil qui « respire ») et une nappe sonore générée par du code.

Rendu LÉGER, comme `sommeil.py` : une boucle vidéo de 30 s (Pillow, 15 images/s, mouvements périodiques ; trois « respirations » de 10 s par boucle) bouclée
par ffmpeg SANS réencodage, une boucle audio de 120 s sans raccord bouclée par ffmpeg ; seule la voix guidée demande un calcul (quelques minutes de lecture).
Aucun modèle musical, aucun échantillon : rien à créditer.

Crochets du moteur : `consignes`, `valider_episode`, `script_voix`, `rendre`, `miniature`. `CONTROLES_STANDARD = False`.
episode.json : {id, titre, chaine, theme, video: "long", format_contenu: "meditation", phrases: [la séance guidée],
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
DUREE_S = {"long": (10 * 60, 40 * 60 + 120), "short": (10 * 60, 40 * 60 + 120)}
AMBIANCES = ("nappe", "vagues", "foret", "vent", "pluie")
DECORS = ("aube-collines", "lac-doux", "souffle")
MINUTES = (10, 40)
PHRASES = (24, 140)
MOTS = (150, 1100)
MOTS_PAR_PHRASE = 16
DEBUT_VOIX_S = 15.0
FIN_SILENCE_S = 30.0  # l'ambiance continue seule après la dernière phrase
BOUCLE_AUDIO_S = 120
BOUCLE_VIDEO_S = 30
RESPIRATION_S = 10  # une respiration du décor = 10 s, trois par boucle de 30 s
FPS = 15
VITESSE_VOIX = 0.85
PAUSE_COURTE_S = 4.5
PAUSE_LONGUE_S = 9.0  # silence après une phrase qui invite à respirer
MOTS_PAR_S = 1.5  # lecture lente (vitesse 0,85)
VOIX_SUR_AMBIANCE_DB = 14  # la voix dépasse l'ambiance de 14 dB : la voix reste claire
PHRASE_HONNETETE = "Ne remplace pas un avis médical."

STYLE = {"haut": "#2E2457", "milieu": "#8E6FB8", "bas": "#F6B38E", "soleil": "#FFE3B8", "lueur": (255, 176, 120), "colline": ("#6A4C93", "#4A3578", "#33245E"),
         "lac": "#5B4488", "particule": "#FFE9C9", "anneau": "#FFD9B0", "texte": "#FFF4E6", "ombre": "#241A47", "pastille": "#4A3578"}

RE_SOUFFLE = re.compile(r"respir|souffl|inspir|expir|poumon", re.I)
RE_AGITE = re.compile(r"explos|\bcris?\b|hurl|\bsang\b|\bmort|\btuer\b|peur|danger|urgen|\bvite\b|course|attaqu|monstre|fant[ôo]me|accident|incendi|orage|tonnerre|\bguerre\b|panique|terrible|affreux|effray", re.I)
RE_SANTE = re.compile(r"gu[ée]ri\w*|soign\w*|soulag\w*|m[ée]dicament\w*|th[ée]rapi\w*|traitement\w*|diagnostic\w*|maladie\w*|anxi[ée]t\w*|d[ée]pressi\w*|insomni\w*|burn-?out|"
                      r"trouble\w*|garanti\w*|miracle\w*|prescri\w*|docteur|m[ée]decin\w*|angoiss\w*|douleur\w*|sans effort|en quelques (?:minutes|secondes)|"
                      r"(?:r[ée]du|diminu|supprim|chass|combat|[ée]limin)\w*\s+(?:le |ton |ta |les |tes )?(?:stress|fatigue)", re.I)

CONSIGNES = """Chaîne MÉDITATION : une séance guidée, calme, de 10 à 40 minutes. Tu écris la séance dans `phrases` (24 à 140 phrases, 150 à 1100 mots) ; la voix les lit très lentement, avec de longs silences entre elles (9 secondes après une invitation à respirer, 4,5 secondes sinon). La vidéo dure `ambiance.duree_min` minutes (10 à 40) : la voix commence après quelques secondes de nappe sonore, la dernière phrase est suivie d'un long silence doux.
Forme d'une séance : 1) s'installer (assis ou allongé, les mains posées, les yeux fermés) ; 2) quelques respirations lentes guidées (« Inspire doucement par le nez. Souffle doucement par la bouche. ») ; 3) le cœur du thème (scan du corps, lâcher-prise, gratitude, marche imaginaire, lumière, souvenir doux…) ; 4) le retour : bouger doucement les doigts, ouvrir les yeux, remercier. Au moins deux phrases invitent à respirer.
Voix : régulière, basse, chaude, sans effet (jamais de balise d'émotion). Phrases courtes (16 mots au plus), mots simples, tutoiement, verbes à l'impératif doux. Quelques phrases peuvent se répéter comme un refrain (« Respire doucement. »), mais la séance ne doit pas être une simple répétition.
Interdit : bruit soudain, cri, peur, danger, urgence, point d'exclamation, chiffres (écris les nombres en lettres, ne compte pas « un, deux, trois » avec des chiffres), tout mot qui inquiète.
Honnêteté : aucune promesse de santé, aucun conseil médical (pas de « soigne », « guérit », « soulage », « réduit le stress », « traitement », « anxiété », « dépression », « insomnie », « douleur »…). Une méditation est un moment de calme, pas un soin. La description contient la phrase « Ne remplace pas un avis médical. » ; ajoute aussi de ne pas écouter en conduisant. Contenu généré en partie par une IA : `contenu_ia` vrai.
Chaque séance est NOUVELLE : un thème, des images, un déroulé différents des précédentes ; `ambiance.type` parmi nappe, vagues, foret, vent, pluie ; `decor.type` parmi aube-collines, lac-doux, souffle ; des `graine` différentes (nombres entiers). Pas de série identique : c'est la règle de YouTube contre le contenu répétitif.
Titre : « Méditation guidée : … » ou « Respiration guidée : … », 70 caractères au plus. Description : le thème, ce que la voix va guider, l'ambiance, la durée, la phrase d'honnêteté, des mots-clés utiles (méditation guidée, respiration, relaxation, pleine conscience)."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def duree_totale_s(ep: dict) -> float:
    return float(ep["ambiance"]["duree_min"]) * 60


# ---------------------------------------------------------------- script de la voix
def pause_apres(phrase: str) -> float:
    return PAUSE_LONGUE_S if RE_SOUFFLE.search(phrase) else PAUSE_COURTE_S


def pauses_de(phrases: list[str]) -> dict[str, float]:
    """Silence AVANT la phrase n (1 = première) : long après une invitation à respirer."""
    return {str(i + 1): pause_apres(phrases[i - 1]) for i in range(1, len(phrases))}


def duree_voix_s(phrases: list[str]) -> float:
    return sum(len(p.split()) for p in phrases) / MOTS_PAR_S + sum(pauses_de(phrases).values())


def script_voix(ep: dict) -> dict:
    ph = [p.strip() for p in ep["phrases"]]
    return {"phrases": ph, "pauses": pauses_de(ph), "vitesses": {str(i + 1): VITESSE_VOIX for i in range(len(ph))}}


# ---------------------------------------------------------------- validation
def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    if ep.get("video") != "long":
        err.append("« video » doit valoir « long » (les méditations ne sont jamais des Shorts)")
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
        return err + ["« phrases » manque : la séance guidée (liste de phrases) est obligatoire"], av
    mots = sum(len(p.split()) for p in ph)
    if not PHRASES[0] <= len(ph) <= PHRASES[1]:
        err.append(f"{len(ph)} phrases : il en faut de {PHRASES[0]} à {PHRASES[1]}")
    if not MOTS[0] <= mots <= MOTS[1]:
        err.append(f"{mots} mots : il en faut de {MOTS[0]} à {MOTS[1]}")
    for i, p in enumerate(ph, 1):
        if len(p.split()) > MOTS_PAR_PHRASE:
            err.append(f"phrase {i} : {len(p.split())} mots, {MOTS_PAR_PHRASE} au plus (phrases courtes et calmes)")
        if "!" in p:
            err.append(f"phrase {i} : pas de point d'exclamation")
        if commun.chiffres(p):
            err.append(f"phrase {i} : pas de chiffres (écris les nombres en lettres)")
        m = RE_AGITE.search(p)
        if m:
            err.append(f"phrase {i} : « {m.group(0)} » n'est pas un mot apaisant")
        m = RE_SANTE.search(p)
        if m:
            err.append(f"phrase {i} : « {m.group(0)} » : aucune promesse de santé ni conseil médical")
    if sum(1 for p in ph if RE_SOUFFLE.search(p)) < 2:
        err.append("la séance doit inviter à respirer (au moins deux phrases avec respire, inspire, souffle…)")
    if len({commun.norm(p) for p in ph}) < 0.6 * len(ph):
        err.append("trop de phrases identiques : une séance n'est pas une simple répétition (60 % de phrases différentes au moins)")
    if isinstance(amb, dict) and isinstance(amb.get("duree_min"), int) and not isinstance(amb.get("duree_min"), bool) and ph:
        voix_s, total = duree_voix_s(ph), amb["duree_min"] * 60
        if total < DEBUT_VOIX_S + voix_s + FIN_SILENCE_S:
            err.append(f"l'ambiance ({amb['duree_min']} min) est plus courte que la séance guidée (environ {voix_s / 60:.0f} min de voix et de silences) : allonge `duree_min`")
        elif voix_s < 0.25 * total:
            err.append(f"la voix ne remplit que {voix_s / total:.0%} de la vidéo ({amb['duree_min']} min) : raccourcis `duree_min` ou allonge la séance")
        elif voix_s < 0.4 * total:
            av.append(f"la voix ne remplit que {voix_s / total:.0%} de la vidéo : beaucoup de nappe seule")
    titre = str(ep.get("titre", ""))
    if not titre.strip() or len(titre) > 70:
        err.append("titre : 1 à 70 caractères")
    m = RE_SANTE.search(titre)
    if m:
        err.append(f"titre : « {m.group(0)} » : aucune promesse de santé")
    if not isinstance(pub, dict):
        err.append("publication.json illisible")
    else:
        desc = str(pub.get("description", ""))
        if "ne remplace pas un avis medical" not in commun.norm(desc):
            err.append(f"description : la phrase « {PHRASE_HONNETETE} » est obligatoire")
        m = RE_SANTE.search(desc + " " + str(pub.get("titre", "")))
        if m:
            err.append(f"publication : « {m.group(0)} » : aucune promesse de santé ni conseil médical")
        if pub.get("langue") not in (None, "fr"):
            err.append("publication.langue doit valoir « fr »")
        if pub.get("contenu_ia") is not True:
            err.append("publication.contenu_ia doit valoir true (voix de synthèse : contenu modifié ou généré à déclarer)")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not str(mini.get("gros", "")).strip():
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (l'idée de la vidéo en 1 à 3 mots) obligatoires")
    elif len(str(mini["gros"]).split()) > 3:
        av.append("miniature : « gros » trop long, 3 mots au plus pour rester lisible")
    return err, av


# ---------------------------------------------------------------- décor : boucle de 30 s
def _fond(w: int, h: int) -> np.ndarray:
    """Dégradé d'aube à trois couleurs : nuit lavande en haut, lavande au milieu, abricot à l'horizon."""
    haut, mil, bas = (np.array(rendu.hex_rgb(STYLE[k]), dtype=np.float32) for k in ("haut", "milieu", "bas"))
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    bas_part = np.clip((t - 0.5) / 0.5, 0, 1)
    haut_part = np.clip(t / 0.5, 0, 1)
    col = np.where(t < 0.5, haut + (mil - haut) * haut_part, mil + (bas - mil) * bas_part)
    return np.repeat(col[:, None, :], w, axis=1)


def _colline(w: int, y0: int, amp: float, graine: int, couleur, d: ImageDraw.ImageDraw, h: int) -> None:
    r = np.random.default_rng(graine)
    p = r.uniform(0, 6.28, 3)
    pts = [(x, y0 - amp * (0.5 + 0.3 * math.sin(x / w * 4 + p[0]) + 0.2 * math.sin(x / w * 9 + p[1]) + 0.1 * math.sin(x / w * 19 + p[2]))) for x in range(0, w + 8, 8)]
    d.polygon(pts + [(w, h), (0, h)], fill=couleur)


class Decor:
    """Décor doux : tout mouvement est périodique sur BOUCLE_VIDEO_S secondes (trois respirations de 10 s), la boucle se raccorde sans saut."""

    def __init__(self, type_: str, graine: int, w: int = 1280, h: int = 720):
        self.type, self.w, self.h = type_, w, h
        r = np.random.default_rng(graine)
        self.fond = _fond(w, h)
        cx = int(r.integers(int(w * 0.35), int(w * 0.65)))
        self.soleil = (cx, int(h * (0.5 if type_ == "souffle" else 0.58)), int(r.integers(64, 90)))
        x, y, rr = self.soleil
        lueur = Image.new("L", (w, h), 0)
        ImageDraw.Draw(lueur).ellipse((x - rr * 3, y - rr * 3, x + rr * 3, y + rr * 3), fill=200)
        self.lueur = (np.asarray(lueur.filter(ImageFilter.GaussianBlur(70)), dtype=np.float32) / 255.0)[:, :, None] * np.array(STYLE["lueur"], dtype=np.float32)
        # premier plan : opaque, dessiné une seule fois (collines ou lac), collé par-dessus le fond et la lueur
        self.avant = Image.new("RGB", (w, h), (0, 0, 0))
        self.masque = Image.new("L", (w, h), 0)
        ad, md = ImageDraw.Draw(self.avant), ImageDraw.Draw(self.masque)
        if type_ == "aube-collines":
            for i, (y0, amp, c) in enumerate(((0.80, 140, STYLE["colline"][0]), (0.88, 120, STYLE["colline"][1]), (0.97, 100, STYLE["colline"][2]))):
                _colline(w, int(h * y0), amp, graine + i, c, ad, h)
                _colline(w, int(h * y0), amp, graine + i, 255, md, h)
        elif type_ == "lac-doux":
            _colline(w, int(h * 0.66), 60, graine, STYLE["colline"][0], ad, h)
            _colline(w, int(h * 0.66), 60, graine, 255, md, h)
            ad.rectangle((0, int(h * 0.66), w, h), fill=STYLE["lac"])
            md.rectangle((0, int(h * 0.66), w, h), fill=255)
        self.particules = [(int(r.integers(0, w)), int(r.integers(0, h)), float(r.uniform(1.5, 3.5)), int(r.integers(1, 3)), float(r.uniform(0, 1))) for _ in range(36)]

    def image(self, t: float) -> Image.Image:
        ph = (t % BOUCLE_VIDEO_S) / BOUCLE_VIDEO_S
        souffle = 0.5 - 0.5 * math.cos(2 * math.pi * BOUCLE_VIDEO_S / RESPIRATION_S * ph)  # 0 -> 1 -> 0, trois fois par boucle
        arr = self.fond + self.lueur * (0.45 + 0.55 * souffle)
        img = Image.fromarray(np.minimum(255, arr).astype(np.uint8))
        d = ImageDraw.Draw(img)
        x, y, rr = self.soleil
        rs = rr * (0.94 + 0.12 * souffle)
        d.ellipse((x - rs, y - rs, x + rs, y + rs), fill=STYLE["soleil"])
        if self.type == "souffle":
            for k in range(1, 6):  # anneaux qui s'élargissent à l'inspiration et se resserrent à l'expiration
                ra = rr * (1.7 + 0.9 * k) * (0.9 + 0.2 * souffle)
                a = 0.7 - 0.11 * k
                c = tuple(int(v * a + f * (1 - a)) for v, f in zip(rendu.hex_rgb(STYLE["anneau"]), (150, 120, 190)))
                d.ellipse((x - ra, y - ra, x + ra, y + ra), outline=c, width=3)
        if self.type != "souffle":
            img.paste(self.avant, (0, 0), self.masque)
            d = ImageDraw.Draw(img)
        if self.type == "lac-doux":
            for i in range(10):  # reflet du soleil : bandes qui ondulent
                yy = int(self.h * 0.67) + i * 22 + int(3 * math.sin(2 * math.pi * (ph * 3 + i / 5)))
                ww = int(rr * (2.4 - i * 0.18)) + int(12 * math.sin(2 * math.pi * (ph * 3 + i / 4)))
                d.rounded_rectangle((x - ww // 2, yy, x + ww // 2, yy + 6), radius=3, fill=(236, 196, 170) if i < 6 else (190, 150, 170))
        pc = rendu.hex_rgb(STYLE["particule"])
        for (px, py, pr, vit, p0) in self.particules:  # poussières de lumière qui montent très lentement, un tour par boucle
            yy = (py - vit * ph * self.h) % self.h
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * (vit * ph + p0)))
            d.ellipse((px - pr, yy - pr, px + pr, yy + pr), fill=tuple(int(v * a + f * (1 - a)) for v, f in zip(pc, (120, 90, 160))))
        return img


# ---------------------------------------------------------------- audio
def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))) + 1e-9)


def boucle_audio(ep: dict, chemin: Path) -> None:
    amb = ep["ambiance"]
    rendu.ecrire_wav(chemin, synth.ambiance(amb["type"], BOUCLE_AUDIO_S, amb["graine"]))


def mixer(boucle: Path, voix: Path, sortie: Path, total_s: float) -> None:
    """Ambiance bouclée sur toute la durée + séance après DEBUT_VOIX_S ; la voix dépasse l'ambiance de 14 dB (mesurée sur les passages parlés,
    pas sur les silences), fondu d'entrée de 10 s et de sortie de 30 s."""
    amb = rendu.lire_audio(boucle)
    v = rendu.lire_audio(voix)
    parle = v[np.abs(v) > 0.05 * (float(np.max(np.abs(v))) + 1e-9)]
    g_amb = (_rms(parle if len(parle) else v) * 10 ** (-VOIX_SUR_AMBIANCE_DB / 20)) / _rms(amb)
    delai = int(DEBUT_VOIX_S * 1000)
    fc = (f"[0:a]volume={g_amb:.5f},afade=t=in:st=0:d=10[b];[1:a]adelay={delai}|{delai}[v];[b][v]amix=inputs=2:duration=first:normalize=0,"
          f"afade=t=out:st={max(0.0, total_s - 30):.2f}:d=30,alimiter=limit=0.95[m]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(boucle), "-i", str(voix), "-filter_complex", fc, "-map", "[m]",
                    "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", str(sortie)], check=True)


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = FPS) -> Path:
    total = duree_totale_s(ep)
    boucle_v = out_dir / "boucle.mp4"
    moteur = "pillow"
    if rendu_remotion.disponible():
        try:  # décor « créateur » (Remotion), boucle parfaite de {BOUCLE_VIDEO_S} s
            rendu_remotion.rendre_video("Fmt-Boucle", rendu_remotion.props_boucle("meditation", ep["decor"]["type"], ep["decor"]["graine"], 1280, 720, fps, BOUCLE_VIDEO_S), boucle_v, crf=26)
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
              seance_mots=sum(len(p.split()) for p in ep["phrases"]), taille_mo=round(final.stat().st_size / 1e6, 1))
    return final


def miniature(ep: dict, profil: dict) -> Image.Image:
    decor = Decor(ep["decor"]["type"], ep["decor"]["graine"])
    img = decor.image(5.0).convert("RGB")
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    gros = str(mini.get("gros", ""))
    rendu.texte_centre(d, 640, 215, gros, rendu.police(150 if len(gros) <= 12 else 110), STYLE["texte"], 1100, ombre=STYLE["ombre"])
    rendu.texte_centre(d, 640, 110, str(mini.get("texte_haut", "")).upper(), rendu.police(54), STYLE["anneau"], 1100, ombre=STYLE["ombre"])
    m = ep["ambiance"]["duree_min"]
    duree = f"{m} min"
    d.rounded_rectangle((60, 600, 60 + d.textlength(duree, font=rendu.police(60)) + 60, 690), radius=30, fill=STYLE["pastille"])
    d.text((90, 612), duree, font=rendu.police(60), fill=STYLE["texte"])
    return img
