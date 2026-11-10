"""Bout en bout des formats maison : brouillon -> valider.py -> fabrique (orchestrateur) -> miniature -> publieur avec le FAUX YouTube.

Chaque format traverse tout le pipeline dans un dossier temporaire (copie du code, BDF_ROOT) jusqu'à l'état `pret`, puis `programme` côté faux YouTube.
La voix est simulée (bips) : aucun GPU, aucun modèle, aucun réseau réel, aucune publication réelle. Les profils réels sont copiés avec `active: true`
DANS LE DOSSIER TEMPORAIRE seulement (les vrais profils restent inactifs).

    python -m unittest autopilot.formats.tests.test_e2e_formats     (depuis pixel-faits/)
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parents[3]
PUB = RACINE / "autopilot" / "publish"
for p in (PUB / "tests", PUB, RACINE / "autopilot"):
    sys.path.insert(0, str(p))

from test_multichaines import BaseChaines  # noqa: E402

import common  # noqa: E402
from autopilot.formats import apprendre, asmr, finance, histoires_enfants, meditation, musique_enfants, quiz, sommeil  # noqa: E402
from autopilot.formats.tests import faux, test_apprendre, test_asmr, test_finance, test_histoires_enfants, test_meditation, test_musique_enfants, test_quiz, test_sommeil  # noqa: E402
from test_publieur import MAINTENANT  # noqa: E402


def pub(titre, description, tags=("a", "b", "c", "d")):
    return {"titre": titre, "description": description, "tags": list(tags), "langue": "fr", "contenu_ia": True,
            "question_commentaires": "Et toi ?"}


FORMATS = {
    "quiz": dict(module=quiz, ep=lambda: test_quiz.episode(), long=False, kids=False,
                 pub=lambda ep: pub("Quiz animaux : sauras-tu répondre ?", "Quiz de trois questions sur les animaux. Réponds en commentaire.\n#quiz #animaux #culture")),
    "langues": dict(module=apprendre, ep=lambda: test_apprendre.episode(), long=False, kids=False,
                    pub=lambda ep: pub("Anglais : commander au café", "Trois phrases pour commander. Prononciation approximative.\n#anglais #apprendre")),
    "sommeil": dict(module=sommeil, ep=lambda: test_sommeil.episode(ambiance={"type": "pluie", "graine": 3, "duree_min": 30}), long=True, kids=False,
                    pub=lambda ep: pub("Histoire pour s'endormir : le village", "Une histoire douce et de la pluie. Cette vidéo détend mais ne remplace pas un avis médical.\n#sommeil #histoire")),
    "meditation": dict(module=meditation, ep=lambda: test_meditation.episode(), long=True, kids=False,
                       pub=lambda ep: pub("Méditation guidée : la lumière douce", "Une séance guidée, voix lente et nappe sonore. Ne remplace pas un avis médical. Ne pas écouter en conduisant.\n#méditation #respiration")),
    "finance-perso": dict(module=finance, ep=lambda: test_finance.episode(), long=False, kids=False,
                          pub=lambda ep: pub("Le livret A expliqué simplement", test_finance.DESC + "\n#finance #épargne")),
    "asmr": dict(module=asmr, ep=lambda: test_asmr.episode(ambiance={"type": "pluie", "graine": 3, "duree_min": 30}), long=True, kids=False,
                 pub=lambda ep: pub("ASMR chuchoté : la petite bibliothèque", "Un scénario chuchoté, voix de synthèse. Sons : pages, tapotements. Cette vidéo détend mais ne remplace pas un avis médical.\n#asmr #relaxation")),
    "musique-enfants": dict(module=musique_enfants, ep=lambda: test_musique_enfants.episode(), long=False, kids=True,
                            pub=lambda ep: pub("Chanson du petit jardin pour enfants", "Une petite chanson. Chanson originale à chanter avec les paroles à l'écran.\n#chanson #enfants")),
    "histoires-enfants": dict(module=histoires_enfants, ep=lambda: test_histoires_enfants.episode(), long=False, kids=True,
                              pub=lambda ep: pub("Histoire pour enfants : Lila partage ses carottes", "Lila partage ses carottes. Histoire originale pour les enfants de 3 à 7 ans. Voix et images créées avec des outils informatiques.\n#histoire #enfants")),
}


class BoutEnBout(BaseChaines):
    def setUp(self):
        super().setUp()
        shutil.copytree(RACINE / "autopilot", self.tmp / "autopilot", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("secrets", "state", "logs", "__pycache__", "tests", "cloud", "tiktok", "*.wav", "*.mp4", "*.png"))
        (self.tmp / "autopilot" / "secrets").mkdir(exist_ok=True)

    def profil(self, ident, **plus):
        """Profil réel copié dans le dossier temporaire, ACTIF seulement ici."""
        p = json.loads((RACINE / "autopilot" / "chaines" / f"{ident}.json").read_text(encoding="utf-8"))
        p.update(active=True, **plus)
        (self.tmp / "autopilot" / "chaines" / f"{ident}.json").write_text(json.dumps(p), encoding="utf-8")
        self.ecrire_jeton_chaine(ident, f"refresh-{ident}")
        return p

    def lancer(self, script, *args):
        env = {**os.environ, "BDF_ROOT": str(self.tmp), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "BDF_PAUSE_S": "0"}
        return subprocess.run([sys.executable, str(self.tmp / "autopilot" / script), *args], capture_output=True, text=True, encoding="utf-8",
                              cwd=str(self.tmp), env=env, timeout=900)

    def ecrire_brouillon(self, ident, ep_id, ep, publication):
        d = self.tmp / "episodes-b" / "_brouillons" / ep_id
        d.mkdir(parents=True)
        ep = {**ep, "id": ep_id}
        (d / "episode.json").write_text(json.dumps(ep), encoding="utf-8")
        (d / "publication.json").write_text(json.dumps({**publication, "chaine_id": ident}), encoding="utf-8")
        return ep

    def valider(self, ident, ep_id):
        r = self.lancer("writer/valider.py", ep_id, "--sans-reseau", "--chaine", ident)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(json.loads(r.stdout.strip().splitlines()[-1])["ok"])

    def voix(self, spec, ep_id, ep):
        d = self.tmp / "episodes-b" / ep_id
        s = spec["module"].script_voix(ep)
        if hasattr(spec["module"], "generer_audio"):  # chant généré : le noyau Kaggle est remplacé par une fausse chanson alignée
            test_musique_enfants.fausse_chanson(ep, d)
        if s["phrases"]:
            faux.fausse_voix(d, s["phrases"], s.get("pauses"), mot_s=0.2 if spec["long"] else 0.28)

    def test_chaque_format_va_jusqu_a_la_publication(self):
        for ident, spec in FORMATS.items():
            if os.environ.get("BDF_E2E_FORMATS") and ident not in os.environ["BDF_E2E_FORMATS"].split(","):  # essai ciblé : BDF_E2E_FORMATS=asmr,finance-perso
                continue
            with self.subTest(format=ident):
                self.profil(ident)
                ep_id = f"{ident}-essai"
                ep = self.ecrire_brouillon(ident, ep_id, spec["ep"](), spec["pub"](None))
                self.valider(ident, ep_id)
                self.assertEqual(common.get_status(ep_id)["etat"], "ecrit")
                self.assertEqual(common.chaine_de(ep_id), ident)
                self.voix(spec, ep_id, ep)
                r = self.lancer("run_daily.py", "fabriquer", "--id", ep_id, "--sans-voix", "--sans-traduction", "--chaine", ident)
                self.assertEqual(common.get_status(ep_id)["etat"], "controle", r.stdout + r.stderr)
                qa = json.loads((self.tmp / "exports-b" / ep_id / "qa.json").read_text(encoding="utf-8"))
                self.assertTrue(qa["publiable"], qa)
                r = self.lancer("run_daily.py", "finaliser", "--id", ep_id, "--chaine", ident)
                self.assertEqual(common.get_status(ep_id)["etat"], "pret", r.stdout + r.stderr)
                self.assertTrue((self.tmp / "episodes-b" / ep_id / "miniature.png").exists())
                code, resume = self.lancer_main("--en-attente")
                self.assertEqual(code, 0, resume)
                self.assertEqual(common.get_status(ep_id)["etat"], "programme", resume)
                video = next(v for v in self.faux.videos.values() if v["refresh"] == f"refresh-{ident}")
                self.assertIs(video["status"]["selfDeclaredMadeForKids"], spec["kids"])  # « conçu pour les enfants » : seulement la chaîne de musique enfantine
                self.assertEqual(video["snippet"]["defaultLanguage"], "fr")
                local = datetime.fromisoformat(video["status"]["publishAt"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Paris"))
                p = self.cfg_profil(ident)
                heure = p["publication"].get("heure_long") if spec["long"] else None
                if heure:  # une vidéo de format long part au créneau des longs, jamais à celui des Shorts
                    self.assertEqual(local.strftime("%H:%M"), heure)
                self.assertNotIn("#Shorts", video["snippet"]["description"]) if spec["long"] else None
                self.faux.videos.clear()

    def cfg_profil(self, ident):
        return json.loads((self.tmp / "autopilot" / "chaines" / f"{ident}.json").read_text(encoding="utf-8"))

    def test_chaine_non_active_ignoree_et_echecs_isoles(self):
        self.profil("quiz")
        p = self.cfg_profil("langues")  # copié inactif, sans preparation : ignoré par toutes les commandes
        (self.tmp / "autopilot" / "chaines" / "langues.json").write_text(json.dumps({**p, "active": False, "preparation": False}), encoding="utf-8")
        bon, mauvais, inactif = "quiz-bon", "quiz-sans-voix", "langues-inactif"
        for ep_id, ident, modele in ((bon, "quiz", test_quiz.episode()), (mauvais, "quiz", test_quiz.episode()), (inactif, "langues", test_apprendre.episode())):
            ep = {**modele, "id": ep_id}
            d = self.tmp / "episodes-b" / ep_id
            d.mkdir(parents=True)
            (d / "episode.json").write_text(json.dumps(ep), encoding="utf-8")
            common.set_status(ep_id, "ecrit", chaine_id=ident)
        self.voix(FORMATS["quiz"], bon, {**test_quiz.episode(), "id": bon})  # `quiz-sans-voix` n'a pas de voix : il échoue seul
        r = self.lancer("run_daily.py", "fabriquer", "--sans-voix", "--sans-traduction")
        self.assertEqual(common.get_status(bon)["etat"], "controle", r.stdout + r.stderr)
        self.assertEqual(common.get_status(mauvais)["etat"], "quarantaine")
        self.assertIn("voix", common.get_status(mauvais)["raison"].lower() + (self.tmp / "exports-b" / mauvais / "qa.json").read_text(encoding="utf-8"))
        self.assertEqual(common.get_status(inactif)["etat"], "ecrit")  # chaîne inactive : jamais fabriquée
        self.assertFalse((self.tmp / "exports-b" / inactif).exists())

    def test_le_code_n_active_jamais_une_chaine(self):
        for ident in ("histoire", "quiz", "langues", "sommeil", "meditation", "musique-enfants", "histoires-enfants", "finance-perso", "asmr"):
            p = json.loads((RACINE / "autopilot" / "chaines" / f"{ident}.json").read_text(encoding="utf-8"))
            self.assertIs(p["active"], False, ident)


if __name__ == "__main__":
    unittest.main()
