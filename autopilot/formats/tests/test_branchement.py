"""Branchement des crochets du module de format dans le rédacteur (stock.py besoin) et la validation (valider.py).

Chaque test travaille dans un dossier temporaire (BDF_ROOT) et lance les scripts en sous-processus, comme autopilot/tests/test_chaines.py :
aucun épisode ni état réel n'est lu ou modifié. Le module de format factice est posé dans un dossier temporaire ajouté à PYTHONPATH.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]


class Branchement(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bdf-fmt-"))
        for d in ("autopilot/chaines", "autopilot/state", "episodes-b/_brouillons", "subjects/histoire", "modules"):
            (self.tmp / d).mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def profil(self, ident, **extra):
        p = {"id": ident, "nom": ident.upper(), "langue": "fr", "format": "business", **extra}
        (self.tmp / "autopilot/chaines" / f"{ident}.json").write_text(json.dumps(p), encoding="utf-8")

    def module(self, nom, code):
        (self.tmp / "modules" / f"{nom}.py").write_text(code, encoding="utf-8")

    def lancer(self, script, *args):
        env = {**os.environ, "BDF_ROOT": str(self.tmp), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
               "PYTHONPATH": str(self.tmp / "modules") + os.pathsep + os.environ.get("PYTHONPATH", "")}
        return subprocess.run([sys.executable, str(RACINE / "autopilot" / script), *args], capture_output=True, text=True,
                              encoding="utf-8", cwd=str(RACINE), env=env, timeout=120)

    def besoin(self, chaine):
        r = self.lancer("writer/stock.py", "besoin", "--chaine", chaine, "--cible", "2", "--max", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout[r.stdout.index("{"):])

    def test_consignes_dans_besoin(self):
        self.module("fmt_branche", "def consignes(p):\n    return 'CONSIGNES-' + p['id'].upper()\n")
        self.profil("histoire", format="histoire", active=False, preparation=True, format_module="fmt_branche",
                    dossiers={"sujets": "subjects/histoire"})
        self.assertEqual(self.besoin("histoire")["consignes_format"], "CONSIGNES-HISTOIRE")

    def test_chaine_sans_module_garde_consignes_vides(self):
        self.profil("fr", active=True)
        self.assertEqual(self.besoin("fr")["consignes_format"], "")

    def _brouillon(self, nom="x"):
        d = self.tmp / "episodes-b" / "_brouillons" / nom
        d.mkdir(parents=True)
        (d / "episode-long.json").write_text(json.dumps({"id": nom, "titre": "t", "theme": "papier-vert", "chaine": "c", "chapitres": []}), encoding="utf-8")
        return d

    def test_valider_brouillon_utilise_valider_episode(self):
        self.module("fmt_refuse", "def valider_episode(ep, faits, pub, profil):\n    return ['REFUS-FORMAT'], ['AVERT-FORMAT']\n")
        self.profil("histoire", format="histoire", active=False, preparation=True, format_module="fmt_refuse",
                    dossiers={"sujets": "subjects/histoire"})
        d = self._brouillon()
        r = self.lancer("writer/valider.py", "x", "--sans-reseau", "--chaine", "histoire")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("REFUS-FORMAT", r.stdout)
        self.assertIn("AVERT-FORMAT", r.stdout)
        self.assertTrue(d.exists())  # jamais déplacé vers episodes-b/
        self.assertFalse((self.tmp / "episodes-b" / "x").exists())

    def test_module_introuvable_refuse_l_episode(self):
        self.profil("histoire", format="histoire", active=False, preparation=True, format_module="fmt_absent",
                    dossiers={"sujets": "subjects/histoire"})
        d = self._brouillon()
        r = self.lancer("writer/valider.py", "x", "--sans-reseau", "--chaine", "histoire")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("fmt_absent", r.stdout)
        self.assertIn("introuvable", r.stdout)
        self.assertTrue(d.exists())

    def test_crochet_qui_plante_refuse_l_episode(self):
        self.module("fmt_plante", "def valider_episode(ep, faits, pub, profil):\n    raise RuntimeError('boum')\n")
        self.profil("histoire", format="histoire", active=False, preparation=True, format_module="fmt_plante",
                    dossiers={"sujets": "subjects/histoire"})
        d = self._brouillon()
        r = self.lancer("writer/valider.py", "x", "--sans-reseau", "--chaine", "histoire")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("a planté", r.stdout)
        self.assertTrue(d.exists())


if __name__ == "__main__":
    unittest.main()
