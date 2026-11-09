"""Cloud : les nouveaux formats (quiz, langues, sommeil, musique) se fabriquent et se publient sur GitHub Actions comme en local.

Lancer :  python -m unittest discover -s autopilot/tests      (depuis pixel-faits/)
Aucun réseau, aucun secret : on vérifie le code des workflows, du noyau Kaggle, du stock et des jetons par chaîne.
"""
import base64
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CLOUD = RACINE / "autopilot" / "cloud"
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(CLOUD))
sys.path.insert(0, str(CLOUD / "kaggle"))
from autopilot import chaines  # noqa: E402
import jetons_chaines  # noqa: E402
import lancer_voix  # noqa: E402
import stockage  # noqa: E402


class Runner(unittest.TestCase):
    def test_fabrique_installe_ffmpeg_pillow_numpy_et_une_police(self):
        y = (CLOUD / "github" / "workflows" / "fabrique.yml").read_text(encoding="utf-8")
        self.assertIn("ffmpeg", y)
        self.assertRegex(y, r"pip install[^\n]*\bpillow\b")
        self.assertRegex(y, r"pip install[^\n]*\bnumpy\b")
        self.assertIn("fonts-dejavu-core", y)  # chemin repris par formats/rendu.py (/usr/share/fonts/truetype/dejavu/)


class VoixKaggle(unittest.TestCase):
    def kernel(self, entree: dict, options: dict) -> tuple[str, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            d = lancer_voix.construire_kernel(Path(tmp), json.dumps(entree).encode(), options, "utilisateur")
            return (d / "script.py").read_text(encoding="utf-8"), json.loads((d / "kernel-metadata.json").read_text(encoding="utf-8"))

    def test_entree_complete_transmise(self):
        entree = {"phrases": ["Bonjour.", "Hello."], "pauses": {"2": 1.5}, "vitesses": {"1": 0.9}, "langues": {"2": "en"}}
        opts = {"essais": 2, "seuil": 0.9, "budget_s": 0, "fichier": "voix-entree.json", "vitesse": 1.0, "langue": "fr", "locuteur": "Ryan", "style": "calme", "modele_hf": "X/Y"}
        texte, meta = self.kernel(entree, opts)
        compile(texte, "script.py", "exec")  # le noyau généré est du Python valide
        b64 = re.search(r'^INPUT_B64 = "([^"]*)"', texte, re.M).group(1)
        self.assertEqual(json.loads(base64.b64decode(b64)), entree)  # pauses, vitesses et langues arrivent intacts à voice.py
        o = json.loads(base64.b64decode(re.search(r'^OPTIONS = json.loads\(base64.b64decode\("([^"]*)"', texte, re.M).group(1)))
        self.assertEqual((o["fichier"], o["locuteur"], o["style"], o["langue"]), ("voix-entree.json", "Ryan", "calme", "fr"))
        self.assertTrue(meta["enable_internet"])  # nécessaire pour télécharger le modèle de voix intégrée

    def test_noyau_pose_les_variables_de_voix(self):
        src = (CLOUD / "kaggle" / "kernel_template.py").read_text(encoding="utf-8")
        for var in ("BDF_LOCUTEUR", "BDF_STYLE", "BDF_LANGUE", "BDF_MODEL_CUSTOM", "BDF_VITESSE"):
            self.assertIn(var, src)
        self.assertIn('"--episode-file", OPTIONS["fichier"]', src)

    def test_options_lues_dans_l_environnement(self):
        # lancer_voix --dry-run ne contacte rien : il construit le noyau et s'arrête
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "voix-entree.json").write_text(json.dumps({"phrases": ["a"], "langues": {"1": "es"}}), encoding="utf-8")
            env = {**os.environ, "KAGGLE_USERNAME": "x", "BDF_LOCUTEUR": "Ryan", "BDF_STYLE": "doux", "BDF_LANGUE": "en", "BDF_VITESSE": "1.0", "PYTHONIOENCODING": "utf-8"}
            r = subprocess.run([sys.executable, str(CLOUD / "kaggle" / "lancer_voix.py"), tmp, "--episode-file", "voix-entree.json", "--dry-run"],
                               capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("kernel prêt", r.stdout)


class StockGithub(unittest.TestCase):
    def test_limite_de_2_gio(self):
        self.assertTrue(stockage.taille_ok(1500 * 1024**2, "github"))
        self.assertFalse(stockage.taille_ok(2 * 1024**3, "github"))
        self.assertTrue(stockage.taille_ok(5 * 1024**3, "r2"))

    def test_verifier_taille_refuse_un_fichier_trop_gros(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            nom = f.name
        try:
            old = stockage.LIMITE_ASSET_GITHUB
            stockage.LIMITE_ASSET_GITHUB = 10
            Path(nom).write_bytes(b"x" * 11)
            with self.assertRaises(stockage.TropGros):
                stockage.verifier_taille(nom, "github")
            stockage.verifier_taille(nom, "r2")
        finally:
            stockage.LIMITE_ASSET_GITHUB = old
            os.unlink(nom)


class JetonsParChaine(unittest.TestCase):
    PROFILS = {"fr": {"jeton_fichier": "token.json"}, "en": {"jeton_fichier": "token-en.json"},
               "musique-enfants": {"jeton_fichier": "token-musique-enfants.json"}, "quiz": {"jeton_fichier": "client_secret.json"}}

    def test_noms_de_secrets(self):
        self.assertEqual(jetons_chaines.nom_secret("fr"), "YT_TOKEN")
        self.assertEqual(jetons_chaines.nom_secret("musique-enfants"), "YT_TOKEN_MUSIQUE_ENFANTS")

    def test_ecriture_sans_fuite(self):
        jeton = json.dumps({"refresh_token": "R", "access_token": "A"})
        env = {"YT_TOKEN_EN": jeton, "YT_TOKEN_MUSIQUE_ENFANTS": "pas du json", "YT_TOKEN": jeton, "YT_TOKEN_QUIZ": jeton}
        plan = {p["id"]: p for p in jetons_chaines.planifier(self.PROFILS, env)}
        self.assertTrue(plan["en"]["valide"])
        self.assertTrue(plan["musique-enfants"]["present"] and not plan["musique-enfants"]["valide"])
        self.assertFalse(plan["quiz"]["valide"])  # un profil ne peut pas viser client_secret.json
        self.assertNotIn(jeton, json.dumps(list(plan.values())))
        with tempfile.TemporaryDirectory() as tmp:
            n = jetons_chaines.ecrire(list(plan.values()), env, Path(tmp))
            self.assertEqual(n, 1)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["token-en.json"])  # fr : écrit par le workflow, pas ici

    def test_chaque_profil_a_sa_ligne_dans_le_workflow(self):
        y = (CLOUD / "github" / "workflows" / "publication.yml").read_text(encoding="utf-8")
        for ident in chaines.charger_profils():
            if ident == chaines.CHAINE_DEFAUT:
                continue
            nom = jetons_chaines.nom_secret(ident)
            self.assertIn(f"{nom}: ${{{{ secrets.{nom} }}}}", y, f"profil {ident} : ligne manquante dans publication.yml")
        self.assertIn("jetons_chaines.py", y)


if __name__ == "__main__":
    unittest.main()


class VoixIntegreeSurKaggle(unittest.TestCase):
    def test_une_voix_integree_force_le_modele_customvoice(self):
        """Régression (GitHub Actions, 2026-11-09) : `--modele-hf` valait le modèle Base, qui ne sait pas lire une voix intégrée."""
        src = (Path(__file__).resolve().parents[1] / "cloud" / "kaggle" / "lancer_voix.py").read_text(encoding="utf-8")
        self.assertIn('if options["locuteur"]:', src)
        self.assertNotIn('options["locuteur"] and not options["modele_hf"]', src)
        self.assertIn("0.6B-CustomVoice", src)
