import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from autopilot import musique  # noqa: E402

FFMPEG = shutil.which("ffmpeg") is not None


def fabriquer(dest: Path, expr: str, duree: float, canaux: int = 1) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "aevalsrc=" + expr.replace(",", r"\,") + f":s=48000:d={duree}", "-ac", str(canaux), str(dest)], check=True)


def lire(p: Path):
    import array
    w = wave.open(str(p))
    a = array.array("h", w.readframes(w.getnframes()))
    return [x / 32768 for x in a[:: w.getnchannels()]], w.getframerate()


def rms_db(x):
    import math
    return 20 * math.log10((sum(v * v for v in x) / max(len(x), 1)) ** 0.5 + 1e-9)


class Choix(unittest.TestCase):
    def pool(self, n=4):
        return [Path(f"piste{i}.mp3") for i in range(n)], {Path(f"piste{i}.mp3"): 100.0 for i in range(n)}

    def test_stable_et_varie(self):
        dispo, d = self.pool(6)
        a = musique.choisir("ep-1", dispo, 40, durees=d)
        self.assertEqual(a, musique.choisir("ep-1", dispo, 40, durees=d))
        premieres = {musique.choisir(f"ep-{i}", dispo, 40, durees=d)[0] for i in range(30)}
        self.assertGreater(len(premieres), 2)

    def test_couvre_la_duree_avec_plusieurs_pistes(self):
        dispo, d = self.pool(3)
        suite = musique.choisir("long", dispo, 600, durees=d)
        couvert = sum(d[p] for p in suite) - musique.RACCORD_S * (len(suite) - 1)
        self.assertGreaterEqual(couvert, 600)
        self.assertEqual(len(set(suite[:3])), 3)  # on fait tourner toutes les pistes avant de répéter

    def test_piste_imposee_en_premier(self):
        dispo, d = self.pool(4)
        self.assertEqual(musique.choisir("x", dispo, 40, voulu="piste2", durees=d)[0].name, "piste2.mp3")

    def test_sans_piste(self):
        self.assertEqual(musique.choisir("x", [], 40), [])


@unittest.skipUnless(FFMPEG, "ffmpeg absent")
class Mixage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.musique = self.tmp / "musique"
        self.musique.mkdir()
        fabriquer(self.musique / "bruit.wav", "0.3*sin(2*PI*220*t)+0.2*sin(2*PI*330*t)", 40, canaux=2)
        # voix factice : silence 0-2 s, parole 2-6 s, pause 6-12 s, parole 12-16 s, silence 16-18 s
        fabriquer(self.tmp / "voix.wav", "0.3*sin(2*PI*180*t)*(gt(t,2)*lt(t,6)+gt(t,12)*lt(t,16))", 18)

    def test_sans_piste_ne_fait_rien(self):
        vide = self.tmp / "vide"
        vide.mkdir()
        self.assertIsNone(musique.mixer(self.tmp / "voix.wav", self.tmp / "o.wav", "e", d=vide))
        self.assertFalse((self.tmp / "o.wav").exists())

    def test_aucune_demandee(self):
        self.assertIsNone(musique.mixer(self.tmp / "voix.wav", self.tmp / "o.wav", "e", voulu="aucune", d=self.musique))

    def test_mixage_musique_sous_la_voix_et_remonte_dans_les_pauses(self):
        o = self.tmp / "o.wav"
        r = musique.mixer(self.tmp / "voix.wav", o, "e", d=self.musique)
        self.assertEqual(r["pistes"], ["bruit.wav"])
        self.assertAlmostEqual(musique.duree(o), 18.0, delta=0.1)
        x, sr = lire(o)
        v, _ = lire(self.tmp / "voix.wav")
        fen = lambda s, a, b: s[int(a * sr): int(b * sr)]
        parole_mix, parole_voix = rms_db(fen(x, 3, 5)), rms_db(fen(v, 3, 5))
        pause = rms_db(fen(x, 8, 11))
        # mono -> stéréo : chaque canal perd 3 dB, le volume (LUFS) reste le même
        self.assertLess(abs(parole_mix + 3.01 - parole_voix), 1.0, "la voix ne doit pas être altérée")
        self.assertGreater(pause, -45, "la musique est audible dans la pause")
        self.assertLess(pause, parole_voix - 6, "mais reste bien sous la voix")
        # fondus d'entrée et de sortie
        self.assertLess(rms_db(fen(x, 0, 0.3)), pause - 6)
        self.assertLess(rms_db(fen(x, 17.7, 18)), pause - 6)

    def test_longueur_imposee_complete_la_voix(self):
        o = self.tmp / "o.wav"
        musique.mixer(self.tmp / "voix.wav", o, "e", longueur=25.0, d=self.musique)
        self.assertAlmostEqual(musique.duree(o), 25.0, delta=0.1)

    def test_pistes_trop_courtes_ignorees(self):
        court = self.tmp / "court"
        court.mkdir()
        fabriquer(court / "bip.wav", "0.3*sin(2*PI*440*t)", 5)
        self.assertIsNone(musique.mixer(self.tmp / "voix.wav", self.tmp / "o.wav", "e", d=court))


if __name__ == "__main__":
    unittest.main()
