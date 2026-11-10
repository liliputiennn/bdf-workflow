"""Format « ASMR » (ESSAI) : de longues vidéos très douces = un petit scénario chuchoté (voix de synthèse basse, lente) + des sons « déclencheurs »
synthétisés par du code (tapotements, brossage, pages, grattement) + une ambiance discrète, sur un décor chaud en boucle.

Rendu LÉGER, comme le sommeil : boucle vidéo de 30 s bouclée sans réencodage, boucle audio de 120 s sans raccord. Aucun échantillon, aucune licence.

RISQUE À SURVEILLER — « contenu inauthentique / répétitif » (YouTube) : des vidéos qui ne diffèrent que par le titre sont déclassées. Ce module REFUSE
donc un épisode sans `scenario`, avec un décor ou un déclencheur déjà trop utilisé dans les derniers épisodes (voir `variete_ok`, appelée par le profil
via `format_options.historique`), et exige un texte inédit (scénario chuchoté de 30 à 120 phrases, pas une boucle de sons seule).

Crochets du moteur : `consignes`, `valider_episode`. `CONTROLES_STANDARD = False`.
episode.json : {id, titre, chaine, theme, video: "long", format_contenu: "asmr", scenario: "bibliotheque",
                phrases: [le scénario chuchoté], declencheurs: [{type, graine}] (1 à 3), ambiance: {type, graine, duree_min},
                decor: {type, graine}, miniature: {texte_haut, gros}}
"""
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import commun, rendu, synth

CONTROLES_STANDARD = False
MENTIONS_PERMISES = True  # la description doit indiquer la voix de synthèse (voir writer/valider.py)
LUFS = -23.0
SEUIL_VOIX = 0.85  # voix chuchotée et lente : la reconnaissance confond des mots voisins sans que le scénario en souffre
DUREE_S = {"long": (10 * 60, 90 * 60 + 180), "short": (10 * 60, 90 * 60 + 180)}
SCENARIOS = ("bibliotheque", "atelier", "tente-pluie", "bureau-lampe", "the-chaud", "carnet-voyage", "jardin-nuit", "boutique-lanternes")
DECORS = ("lampe-bureau", "bougies", "tente-nuit", "bibliotheque", "atelier")
AMBIANCES = ("pluie", "vent", "foret", "nappe")
DECLENCHEURS = synth.DECLENCHEURS
MINUTES = (15, 90)
MOTS = (250, 1400)
FENETRE_VARIETE = 4  # parmi les 4 derniers épisodes de la chaîne, un même décor ou un même scénario ne revient pas
DEBUT_VOIX_S = 8.0
BOUCLE_AUDIO_S = 120
BOUCLE_VIDEO_S = 30
FPS = 15
VITESSE_VOIX = 0.9
PAUSE_ENTRE_PHRASES_S = 1.1
VOIX_SUR_SONS_DB = 6  # la voix dépasse les sons de 6 dB (les déclencheurs restent bien audibles)

PALETTES = {  # (haut, bas, lueur)
    "lampe-bureau": ("#150D08", "#3A2412", (255, 190, 110)),
    "bougies": ("#0E0A12", "#2A1722", (255, 160, 80)),
    "tente-nuit": ("#07101C", "#142B3A", (255, 200, 130)),
    "bibliotheque": ("#120B08", "#33200F", (255, 185, 100)),
    "atelier": ("#0E0F0C", "#2C2A1C", (255, 210, 130)),
}

RE_BRUYANT = re.compile(r"explos|\bcris?\b|hurl|\bsang\b|\bmort|tuer|peur|danger|urgen|attaqu|monstre|accident|incendi|orage|tonnerre|guerre|panique", re.I)
RE_PROMESSE = re.compile(r"gu[ée]ri\w*|soign\w*|m[ée]dicament|th[ée]rapie|garanti\w*|miracle|dormir en|endormir en|anxi[ée]t[ée] (?:dispara|gu[ée]ri)|sans effort|stress (?:dispara|gu[ée]ri)", re.I)
RE_CRIE = re.compile(r"[A-ZÉÈÀ]{5,}")  # un mot en capitales est lu fort

CONSIGNES = """Chaîne ASMR (ESSAI) : une vidéo longue et douce. Tu écris UN scénario à chuchoter (champ `phrases`, 250 à 1400 mots, 30 à 120 phrases) : quelqu'un te montre calmement des objets, range, lit ou prépare quelque chose (`scenario` parmi bibliotheque, atelier, tente-pluie, bureau-lampe, the-chaud, carnet-voyage, jardin-nuit, boutique-lanternes).
Voix : chuchotée, basse, très lente, jamais d'effet ni de balise d'émotion. Phrases courtes (20 mots au plus), mots simples, « tu » chaleureux, gestes décrits (« je pose le livre », « écoute ce petit bruit »). Aucun point d'exclamation, aucun mot en capitales, aucun chiffre (nombres en lettres).
Sons : `declencheurs` = 1 à 3 parmi tapotement, brossage, pages, grattement, chacun avec une `graine` entière différente ; `ambiance` = {type parmi pluie, vent, foret, nappe, graine, duree_min 15 à 90}. L'histoire dure moins longtemps que la vidéo : les sons continuent après la voix.
`decor.type` parmi lampe-bureau, bougies, tente-nuit, bibliotheque, atelier ; `decor.graine` entière.
VARIÉTÉ OBLIGATOIRE (YouTube déclasse les vidéos répétitives) : scénario, décor et déclencheurs principaux DIFFÉRENTS des quatre derniers épisodes, texte entièrement inédit, titre qui décrit le scénario précis (« ASMR chuchoté : la petite bibliothèque, pages et tapotements »).
Interdit : bruit soudain, cri, peur, danger, urgence, promesse de santé (« guérit l'anxiété », « tu dormiras vite »), conseils médicaux. La description contient « Cette vidéo détend mais ne remplace pas un avis médical. », indique que la voix est de synthèse, liste les sons utilisés. Titre : 70 caractères au plus."""


def consignes(profil: dict) -> str:
    return CONSIGNES


def duree_totale_s(ep: dict) -> float:
    return float(ep["ambiance"]["duree_min"]) * 60


def script_voix(ep: dict) -> dict:
    ph = [p.strip() for p in ep["phrases"]]
    return {"phrases": ph, "pauses": {str(i + 1): PAUSE_ENTRE_PHRASES_S for i in range(1, len(ph))},
            "vitesses": {str(i + 1): VITESSE_VOIX for i in range(len(ph))}}


def variete_ok(ep: dict, precedents: list[dict]) -> list[str]:
    """Erreurs si le scénario, le décor ou le déclencheur principal reviennent dans les `FENETRE_VARIETE` derniers épisodes."""
    err = []
    recents = precedents[-FENETRE_VARIETE:]
    if any(p.get("scenario") == ep.get("scenario") for p in recents):
        err.append(f"scénario « {ep.get('scenario')} » déjà utilisé dans les {FENETRE_VARIETE} derniers épisodes : change de scénario (variété obligatoire)")
    if any((p.get("decor") or {}).get("type") == (ep.get("decor") or {}).get("type") for p in recents):
        err.append(f"décor « {(ep.get('decor') or {}).get('type')} » déjà utilisé dans les {FENETRE_VARIETE} derniers épisodes")
    prem = [(d or {}).get("type") for d in (ep.get("declencheurs") or [])][:1]
    if prem and any(prem == [((p.get("declencheurs") or [{}])[0] or {}).get("type")] for p in recents):
        err.append(f"déclencheur principal « {prem[0]} » déjà le premier d'un des {FENETRE_VARIETE} derniers épisodes")
    return err


def _historique(profil: dict) -> list[dict]:
    """episode.json des épisodes déjà écrits de cette chaîne (les plus récents en dernier). Silencieux hors dépôt complet."""
    try:
        from autopilot import common
        ident = (profil or {}).get("id")
        if not ident:
            return []
        eps = [e for e in common.list_episodes(chaine=ident)]
        eps.sort(key=lambda e: common.get_status(e).get("maj", ""))
        sortie = []
        for e in eps:
            j = common.read_json(common.ep_dir(e) / "episode.json", None)
            if isinstance(j, dict) and j.get("format_contenu") == "asmr":
                sortie.append(j)
        return sortie
    except Exception:
        return []


def valider_episode(ep: dict, faits, pub, profil: dict, reseau: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    av: list[str] = []
    if not isinstance(ep, dict):
        return ["episode.json illisible"], av
    if ep.get("video") != "long":
        err.append("« video » doit valoir « long » (l'ASMR n'est jamais un Short)")
    if ep.get("scenario") not in SCENARIOS:
        err.append(f"« scenario » doit être l'un de : {', '.join(SCENARIOS)}")
    amb, dec, decl = ep.get("ambiance"), ep.get("decor"), ep.get("declencheurs")
    if not isinstance(amb, dict) or amb.get("type") not in AMBIANCES:
        err.append(f"« ambiance.type » doit être l'un de : {', '.join(AMBIANCES)}")
    else:
        m = amb.get("duree_min")
        if isinstance(m, bool) or not isinstance(m, int) or not MINUTES[0] <= m <= MINUTES[1]:
            err.append(f"« ambiance.duree_min » : entier de {MINUTES[0]} à {MINUTES[1]} minutes")
        if isinstance(amb.get("graine"), bool) or not isinstance(amb.get("graine"), int):
            err.append("« ambiance.graine » : nombre entier")
    if not isinstance(dec, dict) or dec.get("type") not in DECORS:
        err.append(f"« decor.type » doit être l'un de : {', '.join(DECORS)}")
    elif isinstance(dec.get("graine"), bool) or not isinstance(dec.get("graine"), int):
        err.append("« decor.graine » : nombre entier")
    if not isinstance(decl, list) or not 1 <= len(decl) <= 3:
        err.append("« declencheurs » : 1 à 3 sons déclencheurs ({type, graine})")
    else:
        for i, d in enumerate(decl, 1):
            if not isinstance(d, dict) or d.get("type") not in DECLENCHEURS or isinstance(d.get("graine"), bool) or not isinstance(d.get("graine"), int):
                err.append(f"declencheurs[{i}] : type parmi {', '.join(DECLENCHEURS)} et graine entière")
        if len({d.get("type") for d in decl if isinstance(d, dict)}) < len(decl):
            err.append("declencheurs : deux fois le même son (variété)")
    ph = ep.get("phrases")
    if not isinstance(ph, list) or not all(isinstance(p, str) and p.strip() for p in ph):
        return err + ["« phrases » manque : le scénario chuchoté est obligatoire (des sons seuls seraient un contenu répétitif)"], av
    mots = sum(len(p.split()) for p in ph)
    if not 30 <= len(ph) <= 120:
        err.append(f"{len(ph)} phrases : il en faut de 30 à 120")
    if not MOTS[0] <= mots <= MOTS[1]:
        err.append(f"{mots} mots : il en faut de {MOTS[0]} à {MOTS[1]}")
    if len({commun.norm(p) for p in ph}) < 0.9 * len(ph):
        err.append("trop de phrases répétées : le texte doit être varié")
    for i, p in enumerate(ph, 1):
        if len(p.split()) > 20:
            err.append(f"phrase {i} : {len(p.split())} mots, 20 au plus")
        if "!" in p:
            err.append(f"phrase {i} : pas de point d'exclamation")
        if commun.chiffres(p):
            err.append(f"phrase {i} : pas de chiffres (nombres en lettres)")
        if RE_CRIE.search(p):
            err.append(f"phrase {i} : pas de mot en capitales (il serait lu fort)")
        for rx, msg in ((RE_BRUYANT, "trop agité pour de l'ASMR"), (RE_PROMESSE, "aucune promesse de santé")):
            m = rx.search(p)
            if m:
                err.append(f"phrase {i} : « {m.group(0)} » : {msg}")
    if isinstance(amb, dict) and isinstance(amb.get("duree_min"), int) and mots:
        voix_s = mots / 1.6 + len(ph) * PAUSE_ENTRE_PHRASES_S
        if amb["duree_min"] * 60 < DEBUT_VOIX_S + voix_s + 30:
            err.append(f"la vidéo ({amb['duree_min']} min) est plus courte que le scénario (environ {voix_s / 60:.0f} min) : allonge `duree_min`")
    titre = str(ep.get("titre", ""))
    if RE_PROMESSE.search(titre):
        err.append("titre : aucune promesse de santé")
    if not isinstance(pub, dict):
        err.append("publication.json illisible")
    else:
        d = commun.norm(str(pub.get("description", "")))
        if "ne remplace pas un avis medical" not in d:
            err.append("description : la phrase « Cette vidéo détend mais ne remplace pas un avis médical. » est obligatoire")
        if "synthese" not in d and "synthetique" not in d:
            err.append("description : indique que la voix est une voix de synthèse")
        m = RE_PROMESSE.search(str(pub.get("description", "")) + " " + titre)
        if m:
            err.append(f"publication : « {m.group(0)} » : aucune promesse de santé")
    mini = ep.get("miniature")
    if not isinstance(mini, dict) or not 1 <= len(str(mini.get("texte_haut", "")).split()) <= 5 or not str(mini.get("gros", "")).strip():
        err.append("« miniature » : texte_haut (1 à 5 mots) et gros (1 à 3 mots) obligatoires")
    # variété par rapport aux derniers épisodes de la chaîne (garde-fou « contenu inauthentique »)
    precedents = [e for e in _historique(profil) if e.get("id") != ep.get("id")]
    for e in variete_ok(ep, precedents):
        err.append(e)
    return err, av


# ---------------------------------------------------------------- décor : boucle de 30 s
class Decor:
    """Scène chaude et sombre ; tout mouvement est périodique sur BOUCLE_VIDEO_S (la boucle se raccorde sans saut)."""

    def __init__(self, type_: str, graine: int, w: int = 1280, h: int = 720):
        self.type, self.w, self.h = type_, w, h
        haut, bas, self.lueur = PALETTES[type_]
        r = np.random.default_rng(graine)
        self.fond = rendu.degrade(w, h, haut, bas)
        d = ImageDraw.Draw(self.fond)
        self.sources = []  # (x, y, rayon, rapidité du scintillement, phase)
        if type_ == "lampe-bureau":
            d.rectangle((0, int(h * 0.74), w, h), fill="#1D120A")  # bureau
            lx = int(r.integers(int(w * 0.25), int(w * 0.75)))
            d.polygon([(lx - 60, int(h * 0.45)), (lx + 60, int(h * 0.45)), (lx + 30, int(h * 0.30)), (lx - 30, int(h * 0.30))], fill="#2B1A0D")
            d.rectangle((lx - 6, int(h * 0.45), lx + 6, int(h * 0.74)), fill="#2B1A0D")
            self.sources.append((lx, int(h * 0.47), 230, 2, 0.0))
            for _ in range(int(r.integers(3, 6))):  # objets posés (carnets, tasse)
                x0 = int(r.integers(80, w - 200))
                d.rounded_rectangle((x0, int(h * 0.70), x0 + int(r.integers(60, 150)), int(h * 0.74)), radius=6, fill="#3A2412")
        elif type_ == "bougies":
            d.rectangle((0, int(h * 0.80), w, h), fill="#160D12")
            for i in range(int(r.integers(3, 6))):
                x0 = int(w * (0.18 + 0.64 * (i + r.uniform(0, 0.6)) / 5))
                hb = int(r.integers(70, 160))
                d.rounded_rectangle((x0 - 16, int(h * 0.80) - hb, x0 + 16, int(h * 0.80)), radius=5, fill="#D9C9A8")
                self.sources.append((x0, int(h * 0.80) - hb - 18, 170, int(r.integers(2, 5)), float(r.uniform(0, 1))))
        elif type_ == "tente-nuit":
            d.polygon([(int(w * 0.18), h), (int(w * 0.5), int(h * 0.2)), (int(w * 0.82), h)], fill="#0B1A24")
            d.polygon([(int(w * 0.42), h), (int(w * 0.5), int(h * 0.42)), (int(w * 0.58), h)], fill="#2A1C10")
            self.sources.append((int(w * 0.5), int(h * 0.62), 200, 2, 0.3))
            self.etoiles = [(int(r.integers(0, w)), int(r.integers(0, int(h * 0.3))), float(r.uniform(1.0, 2.6)), int(r.integers(1, 4)), float(r.uniform(0, 1))) for _ in range(60)]
        elif type_ == "bibliotheque":
            for rang in range(4):  # étagères de livres de couleurs sourdes
                y = int(h * (0.12 + rang * 0.21))
                x = 20
                while x < w - 20:
                    lg, ht = int(r.integers(22, 48)), int(r.integers(90, 135))
                    teinte = tuple(int(c) for c in r.integers(40, 120, 3))
                    d.rectangle((x, y + 150 - ht, x + lg, y + 150), fill=(teinte[0] + 30, teinte[1] + 5, teinte[2] - 10 if teinte[2] > 10 else 0))
                    x += lg + 2
                d.rectangle((0, y + 150, w, y + 160), fill="#24160B")
            self.sources.append((int(r.integers(int(w * 0.3), int(w * 0.7))), int(h * 0.55), 320, 1, 0.5))
        else:  # atelier : planches de bois et ampoules suspendues
            for k in range(0, h, 46):
                d.line((0, k, w, k), fill="#1E1D14", width=3)
            for i in range(int(r.integers(2, 4))):
                x0 = int(w * (0.2 + 0.6 * (i + r.uniform(0, 0.5)) / 3))
                d.line((x0, 0, x0, int(h * 0.3)), fill="#111", width=3)
                self.sources.append((x0, int(h * 0.32), 190, int(r.integers(1, 3)), float(r.uniform(0, 1))))
        self.poussieres = [(float(r.uniform(0, 1)), float(r.uniform(0.1, 0.9)), float(r.uniform(0.6, 2.2)), int(r.integers(1, 3)), float(r.uniform(0, 1))) for _ in range(40)]

    def image(self, t: float) -> Image.Image:
        ph = (t % BOUCLE_VIDEO_S) / BOUCLE_VIDEO_S
        glow = Image.new("RGB", (self.w, self.h), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for (x, y, rayon, cyc, p0) in self.sources:
            a = 0.8 + 0.2 * math.sin(2 * math.pi * (cyc * ph * 3 + p0))  # scintillement lent, périodique
            c = tuple(int(v * 0.30 * a) for v in self.lueur)
            gd.ellipse((x - rayon, y - rayon, x + rayon, y + rayon), fill=c)
        glow = glow.filter(ImageFilter.GaussianBlur(70))
        img = Image.fromarray(np.minimum(255, np.asarray(self.fond, dtype=np.int16) + np.asarray(glow, dtype=np.int16)).astype(np.uint8))
        d = ImageDraw.Draw(img)
        for (x, y, rayon, cyc, p0) in self.sources:  # petit cœur lumineux
            a = 0.8 + 0.2 * math.sin(2 * math.pi * (cyc * ph * 3 + p0))
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=tuple(int(v * a) for v in self.lueur))
        for (px, py, r, cyc, p0) in self.poussieres:  # poussières qui dérivent, bouclent à la fin des 30 s
            xx = ((px + cyc * 0.04 * ph) % 1.0) * self.w
            yy = (py - 0.08 * ph + 0.02 * math.sin(2 * math.pi * (ph * cyc + p0))) % 1.0 * self.h
            al = 0.25 + 0.25 * math.sin(2 * math.pi * (ph * 2 + p0))
            d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=tuple(int(v * al) for v in self.lueur))
        for (sx, sy, r, cyc, p0) in getattr(self, "etoiles", []):
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * (cyc * ph + p0)))
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(int(185 * a), int(196 * a), int(240 * a)))
        return img


# ---------------------------------------------------------------- audio
def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))) + 1e-9)


def boucle_audio(ep: dict, chemin: Path) -> None:
    """Déclencheurs (niveau plein) + ambiance discrète (-14 dB), sur BOUCLE_AUDIO_S secondes."""
    amb = ep["ambiance"]
    x = 0.20 * synth.ambiance(amb["type"], BOUCLE_AUDIO_S, amb["graine"])
    for d in ep["declencheurs"]:
        x = x + synth.declencheur(d["type"], BOUCLE_AUDIO_S, d["graine"])
    rendu.ecrire_wav(chemin, x)


def mixer(boucle: Path, voix: Path, sortie: Path, total_s: float) -> None:
    amb = rendu.lire_audio(boucle)
    v = rendu.lire_audio(voix)
    g = (_rms(v) * 10 ** (-VOIX_SUR_SONS_DB / 20)) / _rms(amb)
    delai = int(DEBUT_VOIX_S * 1000)
    fc = (f"[0:a]volume={g:.5f},afade=t=in:st=0:d=6[b];[1:a]adelay={delai}|{delai}[v];[b][v]amix=inputs=2:duration=first:normalize=0,"
          f"afade=t=out:st={max(0.0, total_s - 30):.2f}:d=30,alimiter=limit=0.95[m]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(boucle), "-i", str(voix), "-filter_complex", fc, "-map", "[m]",
                    "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", str(sortie)], check=True)


def rendre(ep: dict, ep_dir: Path, out_dir: Path, profil: dict, qa: dict, fps: int = FPS) -> Path:
    total = duree_totale_s(ep)
    decor = Decor(ep["decor"]["type"], ep["decor"]["graine"])
    boucle_v = out_dir / "boucle.mp4"
    with rendu.Encodeur(boucle_v, decor.w, decor.h, fps, crf=32) as enc:
        for i in range(int(BOUCLE_VIDEO_S * fps)):
            enc.ecrire(decor.image(i / fps))
    boucle_a = out_dir / "boucle.wav"
    boucle_audio(ep, boucle_a)
    mix = out_dir / "mixage.m4a"
    mixer(boucle_a, ep_dir / "voice.wav", mix, total)
    final = out_dir / f"{ep['id']}.mp4"
    mes = rendu.muxer(boucle_v, mix, final, LUFS, boucle_video=True, duree_s=total)
    for f in (boucle_v, boucle_a, mix):
        f.unlink(missing_ok=True)
    qa.update(lufs=float(mes["input_i"]), pic_dbtp=float(mes["input_tp"]), duree_s=round(rendu.duree(final), 1), scenario=ep["scenario"],
              declencheurs=[d["type"] for d in ep["declencheurs"]], histoire_mots=sum(len(p.split()) for p in ep["phrases"]), taille_mo=round(final.stat().st_size / 1e6, 1))
    return final


def miniature(ep: dict, profil: dict) -> Image.Image:
    decor = Decor(ep["decor"]["type"], ep["decor"]["graine"])
    img = decor.image(9.0).convert("RGB")
    d = ImageDraw.Draw(img)
    mini = ep.get("miniature") or {}
    gros = str(mini.get("gros", ""))
    rendu.texte_centre(d, 460, 250, gros, rendu.police(150 if len(gros) <= 12 else 110), "#FFF1D6", 800, ombre="#0A0604")
    rendu.texte_centre(d, 460, 130, str(mini.get("texte_haut", "")).upper(), rendu.police(54), "#FFC98A", 800)
    d.rounded_rectangle((60, 600, 330, 690), radius=30, fill="#3A2412")
    d.text((90, 616), "ASMR", font=rendu.police(58), fill="#FFD9A8")
    return img
