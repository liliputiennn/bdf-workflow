"""Format quiz : sujets, validation (réponses justes et sourcées), script de voix, rendu. Aucun réseau (reseau=False), aucune publication."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from autopilot.formats import quiz
from autopilot.formats.tests import faux

RACINE = Path(__file__).resolve().parents[3]


def manche(q="Quel animal est le plus rapide à la course sur terre ?", opts=("Le guépard", "Le lion", "Le cheval"), bonne=0, check=("guépard",)):
    return {"question": q, "options": list(opts), "bonne": bonne, "explication": "Le guépard atteint environ cent kilomètres à l'heure.",
            "sources": ["https://fr.wikipedia.org/wiki/Gu%C3%A9pard", "https://www.nationalgeographic.fr/guepard"], "check": list(check)}


def episode():
    return {"id": "quiz-test", "titre": "Quiz animaux : sauras-tu répondre ?", "chaine": "Quiz", "theme": "quiz", "video": "short", "format_contenu": "quiz",
            "manches": [manche(),
                        manche("Combien de cœurs a une pieuvre ?", ("Un", "Trois", "Huit"), 1, ("trois",)) | {"explication": "Elle a un cœur principal et deux cœurs pour ses branchies, soit trois en tout."},
                        manche("Quel oiseau ne vole pas mais nage très bien ?", ("Le pingouin vert", "Le manchot", "La cigogne"), 1, ("manchot",)) | {"explication": "Le manchot utilise ses ailes comme des nageoires pour nager."}],
            "miniature": {"texte_haut": "Animaux", "gros": "?"}}


def valider(ep, pub=None):
    return quiz.valider_episode(ep, None, pub if pub is not None else {"langue": "fr"}, {}, reseau=False)


class Validation(unittest.TestCase):
    def test_episode_valide(self):
        self.assertEqual(valider(episode())[0], [])

    def refuse(self, ep, morceau):
        err, _ = valider(ep)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_refus_sans_deux_sources(self):
        ep = episode()
        ep["manches"][0]["sources"] = ep["manches"][0]["sources"][:1]
        self.refuse(ep, "au moins 2 sources")

    def test_refus_memes_sites(self):
        ep = episode()
        ep["manches"][1]["sources"] = ["https://fr.wikipedia.org/a", "https://fr.wikipedia.org/b"]
        self.refuse(ep, "sites différents")

    def test_refus_source_non_https_ou_reseau_social(self):
        ep = episode()
        ep["manches"][0]["sources"] = ["http://exemple.fr/a", "https://www.facebook.com/x"]
        self.refuse(ep, "refusée")

    def test_refus_mot_a_verifier_hors_de_la_bonne_reponse(self):
        ep = episode()
        ep["manches"][0]["check"] = ["lion"]
        self.refuse(ep, "ni dans la bonne réponse ni dans l'explication")

    def test_refus_bonne_reponse_hors_limites(self):
        ep = episode()
        ep["manches"][0]["bonne"] = 3
        self.refuse(ep, "« bonne »")

    def test_refus_toujours_la_meme_place(self):
        ep = episode()
        ep["manches"][1]["bonne"] = 0
        ep["manches"][1]["check"] = ["un"]
        ep["manches"][1]["explication"] = "Un seul cœur, dit la légende, mais c'est faux : trois en tout chez la pieuvre."
        ep["manches"][2]["bonne"] = 0
        ep["manches"][2]["check"] = ["pingouin"]
        ep["manches"][2]["explication"] = "Le pingouin vert n'existe pas ; ce texte sert seulement au test."
        self.refuse(ep, "toujours à la même place")

    def test_refus_question_qui_vieillit(self):
        ep = episode()
        ep["manches"][0]["question"] = "Quel est actuellement l'animal le plus rapide ?"
        self.refuse(ep, "vieillir")

    def test_refus_reponses_doublons_et_ambigues(self):
        ep = episode()
        ep["manches"][0]["options"] = ["Le guépard", "le guépard", "Le cheval"]
        self.refuse(ep, "identiques")
        ep = episode()
        ep["manches"][2]["options"] = ["Le pingouin vert", "Le manchot", "Toutes les réponses"]
        self.refuse(ep, "toutes / aucune")

    def test_refus_sujets_interdits_et_promesses(self):
        ep = episode()
        ep["manches"][0]["question"] = "Quel président a gagné les élections en premier ?"
        self.refuse(ep, "sujet interdit")
        ep = episode()
        ep["manches"][0]["explication"] = "Le guépard vit longtemps, c'est garanti sans aucun doute possible."
        self.refuse(ep, "promesse")

    def test_nombre_de_questions_et_titre(self):
        ep = episode()
        ep["manches"] = ep["manches"][:2]
        self.refuse(ep, "il en faut de 3 à 4")
        ep = episode()
        ep["titre"] = "Animaux : sauras-tu répondre ?"
        self.refuse(ep, "quiz")

    def test_miniature_obligatoire(self):
        ep = episode()
        del ep["miniature"]
        self.refuse(ep, "miniature")

    def test_question_en_double(self):
        ep = episode()
        ep["manches"][1]["question"] = ep["manches"][0]["question"]
        self.refuse(ep, "en double")

    def test_forme_illisible_ne_plante_pas(self):
        self.assertTrue(valider({"id": "x"})[0])
        self.assertTrue(quiz.valider_episode("pas un dict", None, None, {})[0])


class Voix(unittest.TestCase):
    def test_script_pause_et_plan(self):
        ep = episode()
        s = quiz.script_voix(ep)
        self.assertEqual(len(s["plan"]), 3)
        self.assertEqual(len(s["phrases"]), 1 + 4 * 3 + 1)
        for p in s["plan"]:  # le silence de réflexion précède la phrase « La bonne réponse… » (numérotée de 1 dans voice.py)
            self.assertEqual(s["pauses"][str(p["rep"] + 1)], 3.0)
            self.assertTrue(s["phrases"][p["rep"]].startswith("La bonne réponse"))
        self.assertFalse(any(any(c.isdigit() for c in ph) for ph in s["phrases"]))  # la voix lit des mots, pas des chiffres

    def test_quiz_long_a_une_pause_plus_longue(self):
        ep = episode()
        ep["video"] = "long"
        s = quiz.script_voix(ep)
        self.assertEqual(s["pauses"][str(s["plan"][0]["rep"] + 1)], 5.0)


class Rendu(unittest.TestCase):
    def test_rendu_complet_avec_fausse_voix(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-quiz-"))
        try:
            ep = episode()
            d, out = tmp / "ep", tmp / "out"
            d.mkdir()
            out.mkdir()
            s = quiz.script_voix(ep)
            faux.fausse_voix(d, s["phrases"], s["pauses"])
            qa = {}
            final = quiz.rendre(ep, d, out, {"nom": "Quiz (nom à choisir)"}, qa, fps=8)
            self.assertTrue(final.exists() and final.stat().st_size > 10000)
            self.assertTrue(20 <= qa["duree_s"] <= 60, qa)
            self.assertTrue(-15.5 <= qa["lufs"] <= -12.5, qa)
            self.assertEqual(quiz.miniature(ep, {}).size, (1280, 720))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_voix_incoherente_refusee(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-quiz-"))
        try:
            faux.fausse_voix(tmp, ["une seule phrase"])
            with self.assertRaises(ValueError):
                quiz.rendre(episode(), tmp, tmp, {"nom": "Q"}, {}, fps=8)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Banque(unittest.TestCase):
    def test_sujets_de_depart(self):
        s = json.loads((RACINE / "subjects" / "quiz" / "00-sujets-de-depart.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s), 30)
        self.assertEqual(len({x["titre"] for x in s}), len(s))
        self.assertTrue({x["format"] for x in s} <= {"short", "long"})
        self.assertGreaterEqual(len({x["theme"] for x in s}), 6)  # alternance des thèmes


if __name__ == "__main__":
    unittest.main()
