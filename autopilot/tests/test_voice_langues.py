"""La voix suit la langue de la chaîne (BDF_LANGUE) : langue de synthèse, de Whisper, mots-nombres ; le français reste identique. Aucune voix n'est lancée."""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

AUTOPILOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUTOPILOT))
import voice  # noqa: E402


def recharger(**env):
    with mock.patch.dict(os.environ, env, clear=False):
        for k in ("BDF_LANGUE", "BDF_LOCUTEUR"):
            if k not in env:
                os.environ.pop(k, None)
        return importlib.reload(voice)


class LangueDeLaVoix(unittest.TestCase):
    def tearDown(self):
        recharger()

    def test_francais_par_defaut(self):
        v = recharger()
        self.assertEqual((v.LANGUE, v.TTS_LANGUE, v.WHISPER_LANGUE), ("fr", "French", "fr"))
        self.assertIn("vingt", v.NUMWORDS)
        self.assertEqual(v.phonetique("ces"), "ce")

    def test_anglais(self):
        v = recharger(BDF_LANGUE="en")
        self.assertEqual((v.LANGUE, v.TTS_LANGUE, v.WHISPER_LANGUE), ("en", "English", "en"))
        self.assertIn("thousand", v.NUMWORDS)
        self.assertNotIn("vingt", v.NUMWORDS)
        self.assertEqual(v.phonetique("ces"), "ces")  # « ces » : mot anglais ordinaire, pas d'homophone français appliqué
        self.assertEqual(v.phonetique("tenders"), "tender")

    def test_les_nombres_en_lettres_ne_comptent_pas_dans_la_fidelite(self):
        v = recharger(BDF_LANGUE="en")
        self.assertEqual(v.fidelity("It costs twelve thousand dollars", "It costs 12,000 dollars"), 1.0)

    def test_langue_inconnue_retombe_sur_le_francais(self):
        v = recharger(BDF_LANGUE="xx")
        self.assertEqual((v.TTS_LANGUE, v.WHISPER_LANGUE), ("French", "fr"))


if __name__ == "__main__":
    unittest.main()
