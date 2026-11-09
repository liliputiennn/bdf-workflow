"""Format langues : validation avec seconde passe (retraduction, confiance, sources), script de voix par langue, rendu. Aucun réseau."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from autopilot.formats import apprendre
from autopilot.formats.tests import faux

RACINE = Path(__file__).resolve().parents[3]
PROFIL = {"format_options": {"langue_cible": "en"}}
SRC = ["https://en.wiktionary.org/wiki/please", "https://www.tatoeba.org/fr/sentences/show/1"]


def lecon(fr, cible, retraduction, check, phon=None):
    return {"fr": fr, "cible": cible, "retraduction": retraduction, "confiance": "sure", "sources": list(SRC), "check": check} | ({"phonetique": phon} if phon else {})


def episode():
    return {"id": "langues-test", "titre": "Anglais : commander au café", "chaine": "Langues", "theme": "langues", "video": "short", "format_contenu": "langues",
            "langue_cible": "en", "situation": "Au café",
            "lecons": [lecon("Je voudrais un café, s'il vous plaît.", "I would like a coffee, please.", "Je voudrais un café, s'il vous plaît.", ["coffee"], "aï woud laïk a kofi plize"),
                       lecon("Combien ça coûte ?", "How much is it?", "Combien est-ce que ça coûte ?", ["much"]),
                       lecon("Avez-vous de l'eau ?", "Do you have some water?", "Avez-vous de l'eau ?", ["water"])],
            "miniature": {"texte_haut": "Au café", "gros": "Coffee?"}}


def valider(ep, pub=None):
    return apprendre.valider_episode(ep, None, pub if pub is not None else {"langue": "fr", "description": "Prononciation approximative."}, PROFIL, reseau=False)


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau):
        err, _ = valider(ep)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_episode_valide(self):
        self.assertEqual(valider(episode())[0], [])

    def test_incertitude_refusee_plutot_que_publiee(self):
        ep = episode()
        ep["lecons"][1]["confiance"] = "incertain"
        self.refuse(ep, "confiance")

    def test_retraduction_qui_s_eloigne_du_francais(self):
        ep = episode()
        ep["lecons"][2]["retraduction"] = "Voulez-vous un café noir ?"
        self.refuse(ep, "ne correspond pas")

    def test_retraduction_absente_ou_recopiee(self):
        ep = episode()
        del ep["lecons"][0]["retraduction"]
        self.refuse(ep, "retraduction")
        ep = episode()
        ep["lecons"][0]["retraduction"] = ep["lecons"][0]["cible"]
        self.refuse(ep, "recopiée")

    def test_phrase_rester_en_francais(self):
        ep = episode()
        for l in ep["lecons"]:
            l["cible"] = l["fr"]
            l["check"] = ["voudrais"] if "voudrais" in l["fr"] else ["eau"] if "eau" in l["fr"] else ["combien"]
            l["retraduction"] = l["fr"] + " donc"
        err, _ = valider(ep)
        self.assertTrue(any("ne ressemblent pas à la langue" in e for e in err), err)

    def test_sources_et_mots_a_verifier(self):
        ep = episode()
        ep["lecons"][0]["sources"] = ["https://en.wiktionary.org/a", "https://en.wiktionary.org/b"]
        self.refuse(ep, "sites différents")
        ep = episode()
        ep["lecons"][0]["check"] = ["tea"]
        self.refuse(ep, "pas dans la phrase étrangère")
        ep = episode()
        ep["lecons"][0]["sources"] = ep["lecons"][0]["sources"][:1]
        self.refuse(ep, "au moins 2 sources")

    def test_chiffres_gros_mots_promesses_sujets(self):
        ep = episode()
        ep["lecons"][1]["fr"] = "Il coûte 2 euros ?"
        self.refuse(ep, "chiffres")
        ep = episode()
        ep["lecons"][2]["cible"] = "Do you have some fucking water?"
        self.refuse(ep, "gros mot")
        ep = episode()
        ep["titre"] = "Anglais couramment en trente jours"
        ep["lecons"][0]["fr"] = "Parle couramment sans effort, s'il vous plaît."
        self.refuse(ep, "promesse")
        ep = episode()
        ep["lecons"][0]["fr"] = "Où est le président, s'il vous plaît ?"
        self.refuse(ep, "sujet interdit")

    def test_langue_cible_et_titre_et_nombre(self):
        ep = episode()
        ep["langue_cible"] = "es"
        self.refuse(ep, "cette chaîne enseigne")
        ep = episode()
        ep["langue_cible"] = "ja"
        self.refuse(ep, "non prise en charge")
        ep = episode()
        ep["titre"] = "Commander au café"
        self.refuse(ep, "nom de la langue")
        ep = episode()
        ep["lecons"] = ep["lecons"][:2]
        self.refuse(ep, "il en faut de 3 à 4")

    def test_phrase_en_double_et_publication_en_anglais(self):
        ep = episode()
        ep["lecons"][1]["cible"] = ep["lecons"][0]["cible"]
        ep["lecons"][1]["check"] = ["coffee"]
        self.refuse(ep, "en double")
        err, _ = valider(episode(), {"langue": "en", "description": "x"})
        self.assertTrue(any("publication.langue" in e for e in err))

    def test_forme_illisible(self):
        self.assertTrue(valider({"id": "x"})[0])
        self.assertTrue(apprendre.valider_episode(None, None, None, PROFIL)[0])


class Similitude(unittest.TestCase):
    def test_similitude(self):
        self.assertGreaterEqual(apprendre.similitude("Combien ça coûte ?", "Combien est-ce que ça coûte ?"), 0.9)
        self.assertLess(apprendre.similitude("Avez-vous de l'eau ?", "Voulez-vous un café noir ?"), 0.34)
        self.assertEqual(apprendre.similitude("", "x"), 0.0)


class Voix(unittest.TestCase):
    def test_langues_pauses_et_vitesses(self):
        s = apprendre.script_voix(episode())
        self.assertEqual(len(s["phrases"]), 1 + 3 * 3 + 1)
        for p in s["plan"]:
            self.assertEqual(s["langues"][str(p["cible"] + 1)], "en")  # la phrase étrangère est synthétisée dans sa langue
            self.assertEqual(s["langues"][str(p["lent"] + 1)], "en")
            self.assertEqual(s["vitesses"][str(p["lent"] + 1)], apprendre.VITESSE_LENTE)
            self.assertNotIn(str(p["fr"] + 1), s["langues"])  # la consigne reste en français
        self.assertIn(str(s["plan"][1]["fr"] + 1), s["pauses"])  # silence pour répéter avant la leçon 2
        self.assertEqual(s["phrases"][s["plan"][0]["cible"]], "I would like a coffee, please.")


class Rendu(unittest.TestCase):
    def test_rendu_et_miniature(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-lang-"))
        try:
            ep = episode()
            d, out = tmp / "ep", tmp / "out"
            d.mkdir()
            out.mkdir()
            s = apprendre.script_voix(ep)
            faux.fausse_voix(d, s["phrases"], s["pauses"])
            qa = {}
            final = apprendre.rendre(ep, d, out, {"nom": "Langues (nom à choisir)", "format_options": {"langue_cible": "en"}}, qa, fps=8)
            self.assertTrue(final.exists())
            self.assertTrue(25 <= qa["duree_s"] <= 60, qa)
            self.assertTrue(-15.5 <= qa["lufs"] <= -12.5, qa)
            self.assertEqual(apprendre.miniature(ep, PROFIL).size, (1280, 720))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class VoiceGeneral(unittest.TestCase):
    def test_voice_py_gere_la_langue_par_phrase(self):
        src = (RACINE / "autopilot" / "voice.py").read_text(encoding="utf-8")
        self.assertIn('episode.get("langues")', src)
        self.assertIn("language=tts_l", src)
        self.assertNotIn("language=TTS_LANGUE", src)


class Banque(unittest.TestCase):
    def test_sujets_de_depart(self):
        s = json.loads((RACINE / "subjects" / "langues" / "00-sujets-de-depart.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s), 30)
        self.assertEqual(len({x["titre"] for x in s}), len(s))


if __name__ == "__main__":
    unittest.main()
