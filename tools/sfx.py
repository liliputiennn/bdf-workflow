"""SFX 8 bits et nappe de tension, synthétisés (aucune licence à gérer).

Usage : python tools/sfx.py public/sfx
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)


def t(d):
    return np.arange(int(d * SR)) / SR


def env(x, a=0.002, r=0.05):
    n = len(x)
    e = np.ones(n)
    na, nr = int(a * SR), min(int(r * SR), n)
    e[:na] = np.linspace(0, 1, na)
    e[n - nr:] *= np.linspace(1, 0, nr)
    return x * e


def square(f, d):
    return np.sign(np.sin(2 * np.pi * f * t(d)))


def save(name, x, gain=0.5):
    x = x / (np.max(np.abs(x)) + 1e-9) * gain
    sf.write(out / f"{name}.wav", x.astype(np.float32), SR)


# bip d'étiquette : deux notes carrées
save("blip", np.concatenate([env(square(1320, 0.04)), env(square(1760, 0.05))]), 0.25)
# tic de compteur
save("tick", env(square(2400, 0.012), r=0.01), 0.18)
# tampon : choc grave + bruit
d = 0.35
thud = np.sin(2 * np.pi * 70 * t(d)) * np.exp(-t(d) * 14)
noise = rng.standard_normal(len(t(d))) * np.exp(-t(d) * 30)
save("stamp", thud + 0.5 * noise, 0.7)
# souffle de transition : bruit qui monte puis retombe
d = 0.45
n = rng.standard_normal(len(t(d)))
n = np.convolve(n, np.ones(40) / 40, mode="same")
save("whoosh", n * np.sin(np.pi * t(d) / d) ** 2, 0.35)
# alarme : deux tons alternés
save("alarm", np.concatenate([env(square(f, 0.12)) for f in (880, 660, 880, 660)]), 0.22)
# signal perdu : glissando descendant puis bruit blanc
d = 0.9
f = np.linspace(900, 80, len(t(d)))
glide = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR))
save("lost", np.concatenate([env(glide, r=0.2), rng.standard_normal(int(0.5 * SR)) * 0.15]), 0.25)
# fusée : grondement de bruit grave
d = 2.5
r = np.convolve(rng.standard_normal(len(t(d))), np.ones(300) / 300, mode="same")
save("rocket", env(r * np.minimum(1, t(d) * 2), r=0.8), 0.5)
# nappe de tension : quinte grave avec battement lent, 95 s
d = 95
tt = t(d)
drone = (np.sin(2 * np.pi * 55 * tt) + 0.6 * np.sin(2 * np.pi * 82.4 * tt)
         + 0.25 * np.sin(2 * np.pi * 110.3 * tt)) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * tt))
pulse = np.sin(2 * np.pi * 220 * tt) * (np.mod(tt, 0.857) < 0.05) * 0.15  # tic de pendule ~70 bpm
fade = np.minimum(1, tt / 3) * np.minimum(1, (d - tt) / 3)
save("drone", (drone + pulse) * fade, 0.5)
print("ok", sorted(p.name for p in out.iterdir()))
