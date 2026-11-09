"""Rédacteur et profils par chaîne : banque de sujets propre à chaque chaîne, besoins calculés chaîne par chaîne.

Lancer :  python -m unittest discover -s autopilot/tests      (depuis pixel-faits/)
Chaque test travaille dans un dossier temporaire (BDF_ROOT) : aucun épisode réel n'est lu ni modifié.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


class Redacteur(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bdf-chaines-"))
        (self.tmp / "autopilot" / "chaines").mkdir(parents=True)
        (self.tmp / "autopilot" / "state").mkdir(parents=True)
        (self.tmp / "episodes-b").mkdir()
        (self.tmp / "subjects" / "en").mkdir(parents=True)
        self.profil("fr", active=True)
        self.profil("en", active=False, langue="en", voix={"dossier": "voix/en"})
        self.ecrire("subjects/premier.json", [{"titre": "Les fourmis voyagent", "theme": "Animaux"}])
        self.ecrire("subjects/en/idees.json", [{"titre": "Travel words", "theme": "Voyage"}])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ecrire(self, rel, contenu):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")

    def profil(self, ident, **extra):
        self.ecrire(f"autopilot/chaines/{ident}.json", {"id": ident, "nom": ident.upper(), "langue": "fr", "format": "business",
                                                        "jeton_fichier": "token.json" if ident == "fr" else f"token-{ident}.json", **extra})

    def lancer(self, script, *args):
        env = {**os.environ, "BDF_ROOT": str(self.tmp), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, str(RACINE / "autopilot" / script), *args], capture_output=True, text=True,
                              encoding="utf-8", cwd=str(RACINE), env=env, timeout=120)

    def test_les_sujets_d_une_chaine_viennent_de_sa_banque_et_portent_son_prefixe(self):
        r = self.lancer("writer/stock.py", "besoin", "--chaine", "en", "--cible", "2", "--max", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        bilan = json.loads(r.stdout[r.stdout.index("{"):])
        self.assertEqual(bilan["chaine"], "en")
        self.assertEqual([s["id"] for s in bilan["sujets"]], ["en-travel-words"])  # préfixe : les identifiants restent uniques dans episodes-b/
        self.assertEqual(bilan["langue"], "en")
        red = json.loads((self.tmp / "autopilot" / "state" / "redaction.json").read_text(encoding="utf-8"))
        self.assertIn("en", red["par_chaine"])

    def test_la_chaine_par_defaut_ne_pioche_pas_dans_les_sujets_des_autres(self):
        r = self.lancer("writer/stock.py", "besoin", "--cible", "2", "--max", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        bilan = json.loads(r.stdout[r.stdout.index("{"):])
        self.assertEqual(bilan["chaine"], "fr")
        self.assertEqual([s["id"] for s in bilan["sujets"]], ["les-fourmis-voyagent"])
        red = json.loads((self.tmp / "autopilot" / "state" / "redaction.json").read_text(encoding="utf-8"))
        self.assertEqual(red["chaine"], "fr")  # le haut du fichier reste celui de la chaîne par défaut
        self.assertIn("fr", red["par_chaine"])

    def test_le_besoin_d_une_chaine_ignore_les_episodes_des_autres(self):
        for i in range(5):
            d = self.tmp / "episodes-b" / f"fr-{i}"
            d.mkdir()
            (d / "episode.json").write_text("{}", encoding="utf-8")
            (d / "status.json").write_text(json.dumps({"etat": "pret", "maj": "2026-11-08T10:00:00", "raison": None, "tentatives": 0}), encoding="utf-8")
        r = self.lancer("writer/stock.py", "etat", "--chaine", "en")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 vidéo(s)", r.stdout)  # les 5 épisodes prêts sont ceux de la chaîne par défaut
        r = self.lancer("writer/stock.py", "etat")
        self.assertIn("5 vidéo(s)", r.stdout)

    def test_chaine_inconnue(self):
        r = self.lancer("writer/stock.py", "besoin", "--chaine", "nexiste-pas")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("chaîne inconnue", r.stderr)

    def test_valider_refuse_une_chaine_inconnue(self):
        brouillon = self.tmp / "episodes-b" / "_brouillons" / "x"
        brouillon.mkdir(parents=True)
        for nom in ("episode.json", "faits.json", "publication.json"):
            (brouillon / nom).write_text("{}", encoding="utf-8")
        r = self.lancer("writer/valider.py", "x", "--sans-reseau", "--chaine", "nexiste-pas")
        self.assertEqual(r.returncode, 1)
        self.assertIn("inconnue", r.stdout)
        self.assertTrue(brouillon.exists())  # rien n'est déplacé


if __name__ == "__main__":
    unittest.main()
