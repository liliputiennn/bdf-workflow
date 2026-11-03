import copy
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from autopilot.writer import valider  # noqa: E402

DEMO = RACINE / "episodes-b" / "_demo-long" / "episode-long.json"


class Miniature(unittest.TestCase):
    def test_tous_les_styles_sont_acceptes(self):
        for st in ("createur", "telephone", "pile", "chiffre", "question", "contraste"):
            m = {"style": st, "texte_haut": "QUI PAIE VRAIMENT ?", "gros": "0,15 %", "icone": "pieces", "contraste": [{"valeur": "1", "label": "A"}, {"valeur": "2", "label": "B"}]}
            self.assertEqual(valider.controles_miniature(m), [], st)

    def test_style_inconnu_et_champs_manquants(self):
        e = valider.controles_miniature({"style": "arc-en-ciel", "texte_haut": "", "icone": "bateau"})
        self.assertGreaterEqual(len(e), 3)
        self.assertTrue(valider.controles_miniature(None))


class Long(unittest.TestCase):
    @unittest.skipUnless(DEMO.exists(), "démo du format long absente")
    def test_vue_a_plat_et_controles_du_long(self):
        ep = json.loads(DEMO.read_text(encoding="utf-8"))
        ep["theme_accent"] = "chocolat-caramel"
        plat = valider.vue_a_plat(ep)
        self.assertEqual(plat["format"], "long")
        self.assertEqual(plat["theme_accent"], "chocolat-caramel")
        self.assertEqual(len(plat["phrases"]), sum(len(c["phrases"]) for c in ep["chapitres"]))
        err, _, _ = valider.controles_long(copy.deepcopy(ep), [], {"titre": "x"}, reseau=False)
        # la démo est trop courte pour un vrai long : la validation le dit, sans planter
        self.assertTrue(any("6 à 12 minutes" in e or "phrases" in e for e in err), err)
        self.assertTrue(any("faits.json" in e for e in err))

    def test_phrase_trop_longue_en_long(self):
        ep = {"id": "x", "titre": "t", "theme": "chocolat-lait", "chaine": "c", "chapitres": [
            {"titre": "A", "phrases": [" ".join(["mot"] * 30)], "scenes": [{"type": "titre-geant", "phrase": 1, "params": {}}]}]}
        err, _, _ = valider.controles_long(ep, [], {}, reseau=False)
        self.assertTrue(any("30 mots" in e for e in err), err)


if __name__ == "__main__":
    unittest.main()
