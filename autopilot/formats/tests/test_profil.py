import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE))
from autopilot import chaines  # noqa: E402


class ProfilHistoire(unittest.TestCase):
    def setUp(self):
        self.p = chaines.profil("histoire")

    def test_profil_valide_inactif_en_preparation(self):
        self.assertIsNotNone(self.p)
        self.assertTrue(self.p["valide"], self.p.get("erreurs"))
        self.assertFalse(self.p["active"])  # activation = décision de l'utilisateur
        self.assertTrue(self.p["preparation"])
        self.assertFalse(self.p["format_pret"])  # passe à true seulement après une fabrication réelle complète
        self.assertEqual(self.p["format_module"], "autopilot.formats.histoire")
        self.assertIsNotNone(chaines.charger_format(self.p))

    def test_voix_integree_et_theme(self):
        info = chaines.voix_info(self.p)
        self.assertEqual(info["mode"], "integree")
        self.assertTrue(info["disponible"])
        self.assertEqual(self.p["style"]["theme"], "parchemin")
        self.assertEqual(self.p["frequence"], {"shorts_par_jour": 2, "longs_par_semaine": 2})

    def test_brique_miniature_remplacee(self):
        defaut = RACINE / "autopilot" / "miniature.py"
        brique = chaines.brique(self.p, "miniature", defaut)
        self.assertEqual(brique.name, "miniature_histoire.py")
        self.assertTrue(brique.exists())

    def test_banque_de_sujets(self):
        f = RACINE / "subjects" / "histoire" / "00-sujets-de-depart.json"
        sujets = json.loads(f.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(sujets), 10)
        self.assertTrue(all(s["titre"] and s["format"] == "long" and s["theme"] == "Histoire" for s in sujets))
        self.assertEqual(len({s["titre"] for s in sujets}), len(sujets))

    def test_aucun_code_n_ecrit_active(self):
        for f in (RACINE / "autopilot" / "formats").glob("*.py"):
            self.assertNotRegex(f.read_text(encoding="utf-8"), r"""["']active["']\s*\]?\s*=\s*True""")


if __name__ == "__main__":
    unittest.main()
