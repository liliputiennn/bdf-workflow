"""Sons synthétisés par du code (aucun modèle, aucun échantillon, aucune licence à vérifier : tout est calculé ici avec numpy).

- ambiances de sommeil : pluie, vagues, vent, forêt de nuit, nappe douce ; chaque bruit est généré dans le domaine des fréquences,
  donc PÉRIODIQUE : la boucle de `duree_s` secondes se raccorde sans clic ;
- instruments de chansons : boîte à musique et xylophone (synthèse additive avec décroissance).

Tout est déterministe pour une `graine` donnée (deux vidéos différentes = deux graines différentes).
"""
import numpy as np

SR = 48000


def _rng(graine: int) -> np.random.Generator:
    return np.random.default_rng(int(graine) & 0xFFFFFFFF)


def bruit_colore(n: int, pente: float, rng, fmin: float = 20.0, fmax: float = 20000.0, sr: int = SR) -> np.ndarray:
    """Bruit de densité 1/f^pente (0 = blanc, 1 = rose, 2 = brun), bande passante [fmin, fmax], périodique sur n échantillons."""
    f = np.fft.rfftfreq(n, 1 / sr)
    amp = np.zeros_like(f)
    bande = (f >= fmin) & (f <= fmax)
    amp[bande] = f[bande] ** (-pente / 2)
    phases = np.exp(2j * np.pi * rng.random(len(f)))
    x = np.fft.irfft(amp * phases, n)
    return (x / (np.max(np.abs(x)) + 1e-12)).astype(np.float32)


def lfo(n: int, cycles: float, phase: float = 0.0) -> np.ndarray:
    """Sinus lent à `cycles` cycles entiers sur n échantillons (donc périodique), valeurs 0..1."""
    t = np.arange(n) / n
    return 0.5 + 0.5 * np.sin(2 * np.pi * (cycles * t + phase))


def fondu(x: np.ndarray, entree_s: float, sortie_s: float, sr: int = SR) -> np.ndarray:
    x = x.copy()
    a, b = int(entree_s * sr), int(sortie_s * sr)
    if a:
        x[:a] *= np.linspace(0, 1, a, dtype=np.float32)
    if b:
        x[-b:] *= np.linspace(1, 0, b, dtype=np.float32)
    return x


def ambiance(type_: str, duree_s: float, graine: int = 1, sr: int = SR) -> np.ndarray:
    """Boucle d'ambiance mono (float32, crête ≈ 0,5). Types : pluie, vagues, vent, foret, nappe."""
    n = int(duree_s * sr)
    r = _rng(graine)
    if type_ == "pluie":
        fond = bruit_colore(n, 1.0, r, 300, 9000, sr)
        gouttes = bruit_colore(n, 0.2, r, 2000, 14000, sr) * (r.random(n) > 0.9992).astype(np.float32) * 0
        irreg = 0.75 + 0.25 * bruit_colore(n, 2.0, r, 0.05, 2.0, sr)
        x = fond * irreg * (0.8 + 0.2 * lfo(n, max(1, round(duree_s / 23)), r.random()))
        x += 0.25 * bruit_colore(n, 0.4, r, 4000, 12000, sr) * (0.5 + 0.5 * bruit_colore(n, 1.0, r, 5.0, 40.0, sr) ** 2)
    elif type_ == "vagues":
        periode = r.uniform(8.0, 11.0)
        cycles = max(1, round(duree_s / periode))
        houle = lfo(n, cycles, r.random()) ** 2.2
        x = bruit_colore(n, 1.8, r, 40, 3500, sr) * (0.15 + 0.85 * houle)
        x += 0.35 * bruit_colore(n, 0.5, r, 1500, 8000, sr) * houle ** 3  # écume qui monte avec la vague
    elif type_ == "vent":
        souffle = 0.35 + 0.65 * lfo(n, max(1, round(duree_s / r.uniform(14, 22))), r.random()) * (0.6 + 0.4 * lfo(n, max(2, round(duree_s / 5.3)), r.random()))
        x = bruit_colore(n, 1.4, r, 80, 1800, sr) * souffle
    elif type_ == "foret":
        x = 0.55 * ambiance("vent", duree_s, graine + 1, sr)
        grillons = np.sin(2 * np.pi * np.cumsum(np.full(n, 4300.0) / sr)) * (lfo(n, max(1, round(duree_s * 5.1)), 0) > 0.82) * 0.04
        x = x + grillons.astype(np.float32)
    elif type_ == "nappe":
        x = nappe(n, graine, sr)
    else:
        raise ValueError(f"ambiance inconnue : {type_}")
    x = x.astype(np.float32)
    return 0.5 * x / (np.max(np.abs(x)) + 1e-9)


def nappe(n: int, graine: int, sr: int = SR) -> np.ndarray:
    """Accord doux et lent (quarte/quinte, fréquences basses), tremblement très lent ; périodique."""
    r = _rng(graine)
    base = float(r.choice([110.0, 123.47, 130.81, 146.83]))
    t = np.arange(n) / sr
    duree_s = n / sr
    x = np.zeros(n, dtype=np.float32)
    for rap, a in ((1.0, 1.0), (1.5, 0.6), (2.0, 0.5), (2.5, 0.25), (3.0, 0.15)):
        f = round(base * rap * duree_s) / duree_s  # nombre entier de cycles : la boucle se raccorde
        mod = 0.75 + 0.25 * lfo(n, max(1, round(duree_s / r.uniform(9, 17))), r.random())
        x += (a * mod * np.sin(2 * np.pi * f * t + r.random() * 6.28)).astype(np.float32)
    return x


# ---------------------------------------------------------------- notes et instruments
def frequence(degre: int, tonique: float = 261.63, gamme: tuple = (0, 2, 4, 5, 7, 9, 11)) -> float:
    """Fréquence du degré `degre` (1 = tonique, 8 = octave, 0 ou négatif = en dessous) d'une gamme majeure par défaut."""
    d = degre - 1
    octave, i = divmod(d, len(gamme))
    return tonique * 2 ** ((gamme[i] + 12 * octave) / 12)


def note(freq: float, duree_s: float, instrument: str = "boite", sr: int = SR, vel: float = 0.8) -> np.ndarray:
    """Une note : 'boite' (boîte à musique, cloche douce), 'xylophone' (court, boisé), 'flute' (souffle doux)."""
    n = int(duree_s * sr)
    t = np.arange(n) / sr
    if instrument == "xylophone":
        x = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 3.9 * t) * np.exp(-t * 30)
        env = np.exp(-t * 9.0)
    elif instrument == "flute":
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.0 * t)
        x = np.sin(2 * np.pi * freq * t * vib) + 0.25 * np.sin(4 * np.pi * freq * t) + 0.06 * np.sin(6 * np.pi * freq * t)
        env = np.minimum(1.0, t / 0.04) * np.exp(-np.maximum(0, t - duree_s * 0.6) * 6.0)
    else:  # boîte à musique
        x = np.sin(2 * np.pi * freq * t) + 0.45 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 3) + 0.2 * np.sin(2 * np.pi * freq * 4.02 * t) * np.exp(-t * 8)
        env = np.exp(-t * 3.2)
    attaque = np.minimum(1.0, t / 0.004)
    y = x * env * attaque * vel
    y[-min(n, 200):] *= np.linspace(1, 0, min(n, 200))
    return y.astype(np.float32)


def melodie(evenements: list[tuple[float, float, float]], duree_totale_s: float, instrument: str = "boite", sr: int = SR) -> np.ndarray:
    """Mixe des notes (début_s, durée_s, fréquence) dans une piste mono de `duree_totale_s`."""
    piste = np.zeros(int(duree_totale_s * sr) + sr, dtype=np.float32)
    for debut, d, f in evenements:
        nn = note(f, d + 0.6, instrument, sr)
        i = int(debut * sr)
        piste[i:i + len(nn)] += nn[: max(0, len(piste) - i)]
    return piste[: int(duree_totale_s * sr)]
