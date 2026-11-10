"""Format finance perso pédagogique : sources, honnêteté (pas de promesse, pas de conseil), script de voix, rendu avec voix simulée. Aucun réseau."""
import tempfile
import unittest
from pathlib import Path

from autopilot.formats import finance
from autopilot.formats.tests import faux

DESC = ("Le livret A expliqué simplement. Cette vidéo est éducative et ne constitue pas un conseil financier.\n"
        "Sources : https://www.service-public.fr/livret-a https://www.banque-france.fr/livret-a https://www.amf-france.org/x https://www.economie.gouv.fr/y")


def point(titre="Un compte sans risque de perte", texte=None, **plus):
    p = {"titre": titre, "texte": texte or ["Le livret A est un compte d'épargne réglementé.", "Les sommes restent disponibles à tout moment."],
         "chiffre": {"valeur": "3 %", "legende": "taux en vigueur, à vérifier"},
         "sources": ["https://www.service-public.fr/livret-a", "https://www.banque-france.fr/livret-a"], "check": ["livret"]}
    p.update(plus)
    return p


def episode(**plus):
    ep = {"id": "finance-test", "titre": "Le livret A expliqué simplement", "chaine": "Finance", "theme": "finance", "video": "short", "format_contenu": "finance",
          "sujet": "Le livret A",
          "points": [point("Un compte d'épargne réglementé"), point("Un plafond de dépôt", ["Il existe un plafond de dépôt fixé par la loi.", "Au-delà, il faut un autre compte."]),
                     point("Des intérêts non imposés", ["Les intérêts du livret A ne sont pas soumis à l'impôt.", "Le taux est fixé par l'État et peut changer."])],
          "miniature": {"texte_haut": "Épargne simple", "gros": "Livret A"}}
    ep.update(plus)
    return ep


def valider(ep, pub=None):
    return finance.valider_episode(ep, None, {"description": DESC, "langue": "fr"} if pub is None else pub, {}, reseau=False)


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau, pub=None):
        err, _ = valider(ep, pub)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_episode_valide(self):
        err, _ = valider(episode())
        self.assertEqual(err, [])

    def test_promesse_de_rendement_refusee(self):
        ep = episode()
        ep["points"][0]["texte"] = ["Ce placement offre un rendement garanti à tous."]
        self.refuse(ep, "rendement")

    def test_conseil_personnalise_refuse(self):
        ep = episode()
        ep["points"][1]["texte"] = ["Tu dois investir dans ce fonds maintenant."]
        self.refuse(ep, "refusé")

    def test_recommandation_de_marque_refusee(self):
        ep = episode()
        ep["points"][2]["texte"] = ["Ouvre un compte chez Boursorama pour commencer."]
        self.refuse(ep, "marque")

    def test_chiffres_dans_le_texte_lu_refuses_mais_pas_a_l_ecran(self):
        ep = episode()
        ep["points"][0]["texte"] = ["Le taux est de 3 pour cent."]
        self.refuse(ep, "pas de chiffres")

    def test_deux_sources_de_sites_differents(self):
        ep = episode()
        ep["points"][0]["sources"] = ["https://www.service-public.fr/a", "https://www.service-public.fr/b"]
        self.refuse(ep, "sites différents")

    def test_source_manquante(self):
        ep = episode()
        del ep["points"][1]["sources"]
        self.refuse(ep, "au moins 2 sources")

    def test_mention_obligatoire_dans_la_description(self):
        self.refuse(episode(), "ne constitue pas un conseil financier", pub={"description": "Sources : https://www.service-public.fr/x", "langue": "fr"})

    def test_sources_obligatoires_dans_la_description(self):
        self.refuse(episode(), "Sources", pub={"description": "Cette vidéo est éducative et ne constitue pas un conseil financier.", "langue": "fr"})

    def test_titre_sans_promesse(self):
        self.refuse(episode(titre="Devenez riche avec le livret A"), "promesse")

    def test_nombre_de_points(self):
        ep = episode()
        ep["points"] = ep["points"][:2]
        self.refuse(ep, "points : il en faut")

    def test_un_long_demande_plus_de_points(self):
        self.refuse(episode(video="long"), "points : il en faut")


class Voix(unittest.TestCase):
    def test_script_se_termine_par_la_mention(self):
        s = finance.script_voix(episode())
        self.assertEqual(s["phrases"][-1], finance.MENTION)
        self.assertEqual(len(s["plan"]), 3)
        self.assertEqual(s["plan"][0]["debut"], 1)
        self.assertLess(s["plan"][0]["fin"], s["plan"][1]["debut"])


class Rendu(unittest.TestCase):
    def test_rendu_et_miniature(self):
        ep = episode()
        with tempfile.TemporaryDirectory() as tmp:
            ep_dir, out = Path(tmp, "ep"), Path(tmp, "out")
            ep_dir.mkdir()
            out.mkdir()
            s = finance.script_voix(ep)
            faux.fausse_voix(ep_dir, s["phrases"], s["pauses"])
            qa = {}
            final = finance.rendre(ep, ep_dir, out, {"nom": "Finance"}, qa, fps=6)
            self.assertTrue(final.exists() and final.stat().st_size > 1000)
            self.assertGreater(qa["duree_s"], 10)
            self.assertEqual(qa["points"], 3)
        self.assertEqual(finance.miniature(ep, {}).size, (1280, 720))


if __name__ == "__main__":
    unittest.main()
