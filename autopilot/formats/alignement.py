"""Synchronisation paroles <-> chant généré (aucun GPU : s'exécute aussi bien sur le noyau Kaggle que dans le rendu GitHub Actions).

Le modèle de musique chante nos paroles mais ne dit pas QUAND : on fait transcrire le chant par Whisper (mots horodatés) puis on aligne les
paroles connues sur cette transcription (suite de lettres commune la plus longue, interpolation entre les points d'ancrage). Si la
transcription est trop pauvre, repli prudent : paroles réparties à régime constant sur la durée chantée. Le taux d'appariement sert de
contrôle qualité (chant intelligible ou non). Ce fichier est embarqué tel quel dans le noyau Kaggle : n'importer que numpy et la bibliothèque standard.
"""
import difflib
import re
import unicodedata

import numpy as np

MIN_APPARIEMENT = 0.35  # en dessous : chant peu intelligible, à faire écouter
BLOC_MIN = 3


def lettres(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))


def _mots_de(ligne: str) -> list[str]:
    return [m for m in str(ligne).replace("’", "'").split() if lettres(m)]


def aligner(lignes: list[str], mots_whisper: list[dict], duree: float) -> dict:
    """lignes : paroles dans l'ordre chanté. mots_whisper : [{"mot","debut","fin"}].
    Renvoie {"lignes": [{"debut","fin","mots":[{"m","debut","fin"}]}], "appariement": 0..1, "methode": "whisper"|"regulier"}."""
    mots_l = [_mots_de(l) for l in lignes]
    texte, pos_mot = "", []  # pos_mot : (index de ligne, index de mot, début, fin) en caractères
    for i, ms in enumerate(mots_l):
        for j, m in enumerate(ms):
            a = len(texte)
            texte += lettres(m)
            pos_mot.append((i, j, a, len(texte)))
    heard, temps = "", []
    for w in mots_whisper:
        l = lettres(w.get("mot", ""))
        if not l:
            continue
        d, f = float(w["debut"]), float(w["fin"])
        for k, c in enumerate(l):
            heard += c
            temps.append(d + (f - d) * (k + 0.5) / len(l))
    n = max(1, len(texte))
    ancres_x, ancres_t, appar = [], [], 0
    if heard and texte:
        sm = difflib.SequenceMatcher(None, texte, heard, autojunk=False)
        for b in sm.get_matching_blocks():
            if b.size >= BLOC_MIN:
                appar += b.size
                for k in range(b.size):
                    ancres_x.append(b.a + k)
                    ancres_t.append(temps[b.b + k])
    taux = appar / n
    if taux >= MIN_APPARIEMENT and len(ancres_x) >= 6:
        t_deb = float(np.interp(0, ancres_x, ancres_t))
        x = np.arange(n + 1, dtype=float)
        t = np.interp(x, ancres_x, np.maximum.accumulate(ancres_t))
        methode = "whisper"
        # avant la première ancre / après la dernière, np.interp reste plat : on étire au débit moyen
        debit = (ancres_t[-1] - ancres_t[0]) / max(1.0, ancres_x[-1] - ancres_x[0])
        for k in range(len(t)):
            if x[k] < ancres_x[0]:
                t[k] = ancres_t[0] - (ancres_x[0] - x[k]) * debit
            elif x[k] > ancres_x[-1]:
                t[k] = ancres_t[-1] + (x[k] - ancres_x[-1]) * debit
        t = np.clip(t, 0, duree)
        del t_deb
    else:
        methode = "regulier"
        d0, d1 = min(6.0, 0.1 * duree), max(duree - 4.0, 0.5 * duree)
        t = d0 + (d1 - d0) * np.arange(n + 1) / n
    out = [{"debut": 0.0, "fin": 0.0, "mots": []} for _ in lignes]
    for i, j, a, b in pos_mot:
        out[i]["mots"].append({"m": mots_l[i][j], "debut": round(float(t[a]), 3), "fin": round(float(t[b]), 3)})
    dernier = 0.0
    for o in out:
        if o["mots"]:
            o["debut"], o["fin"] = max(dernier, o["mots"][0]["debut"]), max(o["mots"][-1]["fin"], o["mots"][0]["debut"] + 0.4)
            dernier = o["debut"]
    for k, o in enumerate(out):  # une ligne finit avant que la suivante commence
        if k + 1 < len(out) and o["fin"] > out[k + 1]["debut"]:
            o["fin"] = max(o["debut"] + 0.3, out[k + 1]["debut"] - 0.02)
        for m in o["mots"]:
            m["debut"] = round(min(max(m["debut"], o["debut"]), o["fin"]), 3)
            m["fin"] = round(min(max(m["fin"], m["debut"] + 0.05), o["fin"]), 3)
        o["debut"], o["fin"] = round(o["debut"], 3), round(o["fin"], 3)
    return {"lignes": out, "appariement": round(float(min(1.0, taux)), 3), "methode": methode}


def enveloppe_voix(x: np.ndarray, sr: int, fps: int) -> np.ndarray:
    """Ouverture de bouche 0..1 par image : énergie dans la bande de la voix (200-3500 Hz), lissée."""
    pas = sr // fps
    n = len(x) // pas
    if n <= 0:
        return np.zeros(1)
    fen = np.hanning(pas)
    freqs = np.fft.rfftfreq(pas, 1 / sr)
    bande = (freqs >= 200) & (freqs <= 3500)
    e = np.array([np.sqrt(np.mean(np.abs(np.fft.rfft(x[i * pas:(i + 1) * pas] * fen))[bande] ** 2)) for i in range(n)])
    ref = np.percentile(e, 92) + 1e-9
    e = np.clip(e / ref, 0, 1) ** 0.8
    lisse = np.convolve(e, [0.25, 0.5, 0.25], mode="same")
    return lisse
