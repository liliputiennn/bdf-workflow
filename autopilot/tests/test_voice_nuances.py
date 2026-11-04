import shutil
import sys
import unittest
from pathlib import Path

import numpy as np

AUTOPILOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUTOPILOT))
import voice  # noqa: E402


class Nuance(unittest.TestCase):
    def test_deterministe(self):
        self.assertEqual(voice.nuance("Combien ça rapporte par jour ?"), voice.nuance("Combien ça rapporte par jour ?"))

    def test_phrase_choc_plus_lente_et_plus_appuyee_qu_une_longue(self):
        courte = voice.nuance("Zéro euro de départ.")
        longue = voice.nuance("Tu prends ton téléphone, tu écris à dix personnes du quartier et tu leur proposes ton aide pour vingt euros ce soir même.")
        self.assertLess(courte[0], 1.0)
        self.assertGreater(longue[0], 1.0)
        self.assertGreater(courte[1], longue[1])   # plus de gain
        self.assertGreater(courte[2], longue[2])   # un temps après

    def test_question_laisse_respirer(self):
        self.assertGreater(voice.nuance("Et combien ça rapporte vraiment par mois ?")[2], voice.nuance("Et voilà combien ça rapporte vraiment par mois.")[2])

    def test_deux_phrases_voisines_ne_sonnent_pas_pareil(self):
        a, b = voice.nuance("Tu choisis un outil gratuit pour commencer ce soir."), voice.nuance("Tu choisis un modèle gratuit pour commencer demain.")
        self.assertNotEqual(a[0], b[0])

    def test_intensite_zero_donne_une_voix_uniforme_et_bornes_respectees(self):
        self.assertEqual(voice.nuance("Zéro euro de départ.", 0), (1.0, 0.0, 0.0))
        for t in ("Oui.", "Pourquoi ?", "Attends…", "C'est parti !", " ".join(["mot"] * 30)):
            v, g, p = voice.nuance(t, 3)
            self.assertTrue(0.8 <= v <= 1.25 and -3 <= g <= 3 and p >= 0, (t, v, g, p))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg absent")
class Etirer(unittest.TestCase):
    def test_vitesse_change_la_duree(self):
        sr = 24000
        wav = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr * 2) / sr)).astype(np.float32)
        plus_vite, plus_lent = voice.etirer(wav, sr, 1.25), voice.etirer(wav, sr, 0.8)
        self.assertAlmostEqual(len(plus_vite) / len(wav), 1 / 1.25, delta=0.05)
        self.assertAlmostEqual(len(plus_lent) / len(wav), 1 / 0.8, delta=0.05)
        self.assertIs(voice.etirer(wav, sr, 1.0), wav)


if __name__ == "__main__":
    unittest.main()
