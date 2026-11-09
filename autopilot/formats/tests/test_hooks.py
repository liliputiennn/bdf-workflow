import sys
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE))
from autopilot import chaines  # noqa: E402


def _module(nom, **fonctions):
    m = types.ModuleType(nom)
    for k, v in fonctions.items():
        setattr(m, k, v)
    sys.modules[nom] = m
    return nom


class AppelerHook(unittest.TestCase):
    def test_sans_module_renvoie_defaut(self):
        self.assertEqual(chaines.appeler_hook({"format_module": None}, "consignes", {}, defaut="x"), "x")

    def test_appelle_le_crochet(self):
        nom = _module("fmt_test_ok", consignes=lambda p: "Raconte.")
        self.assertEqual(chaines.appeler_hook({"format_module": nom}, "consignes", {"id": "h"}), "Raconte.")

    def test_crochet_absent_renvoie_defaut(self):
        nom = _module("fmt_test_vide")
        self.assertEqual(chaines.appeler_hook({"format_module": nom}, "consignes", {}, defaut=""), "")

    def test_exception_renvoie_sur_erreur(self):
        def casse(*a):
            raise RuntimeError("boum")
        nom = _module("fmt_test_casse", valider_episode=casse)
        r = chaines.appeler_hook({"format_module": nom}, "valider_episode", {}, None, None, {}, defaut=([], []), sur_erreur=(["plantage"], []))
        self.assertEqual(r, (["plantage"], []))

    def test_nom_inconnu_leve(self):
        with self.assertRaises(ValueError):
            chaines.appeler_hook({"format_module": None}, "inconnu")


if __name__ == "__main__":
    unittest.main()
