"""Format ASMR (essai) : variété obligatoire (anti « contenu inauthentique »), douceur, honnêteté, sons sans raccord, rendu avec voix simulée."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from autopilot.formats import asmr, synth
from autopilot.formats.tests import faux

DESC = {"description": "Un scénario chuchoté. Voix de synthèse. Sons : pages, tapotements. Cette vidéo détend mais ne remplace pas un avis médical.", "langue": "fr"}
OBJETS = ("livre", "carnet", "crayon", "tasse", "lampe", "boîte", "pinceau", "ruban")
COULEURS = ("bleu", "rouge", "vert", "gris", "rose")
PHRASES = [f"Je pose doucement le petit {o} {c} sur la table de bois, et j'écoute le bruit qu'il fait." for o in OBJETS for c in COULEURS]  # 40 phrases différentes


def episode(**plus):
    ep = {"id": "asmr-test", "titre": "ASMR chuchoté : la petite bibliothèque", "chaine": "ASMR", "theme": "asmr", "video": "long", "format_contenu": "asmr",
          "scenario": "bibliotheque", "phrases": list(PHRASES), "declencheurs": [{"type": "pages", "graine": 3}, {"type": "tapotement", "graine": 8}],
          "ambiance": {"type": "nappe", "graine": 5, "duree_min": 30}, "decor": {"type": "bibliotheque", "graine": 2},
          "miniature": {"texte_haut": "Chuchoté et doux", "gros": "Bibliothèque"}}
    ep.update(plus)
    return ep


def valider(ep, pub=None):
    return asmr.valider_episode(ep, None, DESC if pub is None else pub, {}, reseau=False)


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau, pub=None):
        err, _ = valider(ep, pub)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_episode_valide(self):
        err, _ = valider(episode())
        self.assertEqual(err, [])

    def test_jamais_un_short(self):
        self.refuse(episode(video="short"), "jamais un Short")

    def test_scenario_obligatoire(self):
        self.refuse(episode(scenario="plage"), "scenario")

    def test_des_sons_seuls_sont_refuses(self):
        ep = episode()
        del ep["phrases"]
        self.refuse(ep, "phrases")

    def test_declencheurs_varies(self):
        self.refuse(episode(declencheurs=[{"type": "pages", "graine": 1}, {"type": "pages", "graine": 2}]), "deux fois le même son")
        self.refuse(episode(declencheurs=[]), "declencheurs")

    def test_texte_repete_refuse(self):
        self.refuse(episode(phrases=["Je pose le livre sur la table."] * 40), "répétées")

    def test_douceur(self):
        ph = list(PHRASES)
        ph[3] = "Attention, un monstre arrive !"
        self.refuse(episode(phrases=ph), "agité")
        ph[3] = "CHUTTT maintenant, doucement."
        self.refuse(episode(phrases=ph), "capitales")

    def test_promesse_de_sante_refusee(self):
        ph = list(PHRASES)
        ph[5] = "Cette vidéo guérit l'anxiété pour toujours."
        self.refuse(episode(phrases=ph), "promesse")

    def test_description_honnete_et_voix_de_synthese(self):
        self.refuse(episode(), "avis médical", pub={"description": "Voix de synthèse.", "langue": "fr"})
        self.refuse(episode(), "voix de synthèse", pub={"description": "Cette vidéo détend mais ne remplace pas un avis médical.", "langue": "fr"})

    def test_duree_assez_longue_pour_le_scenario(self):
        longs = [f"Je pose doucement le petit livre sur la table de bois et j'écoute le bruit numéro {m}." for m in
                 ("un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze") * 10]
        self.refuse(episode(ambiance={"type": "nappe", "graine": 5, "duree_min": 15}, phrases=longs), "plus courte")


class Variete(unittest.TestCase):
    """Le garde-fou « contenu inauthentique » : pas deux fois le même scénario, décor ou premier son dans les derniers épisodes."""

    def test_meme_scenario_refuse(self):
        prec = [episode(id="a", scenario="atelier", decor={"type": "atelier", "graine": 1}, declencheurs=[{"type": "brossage", "graine": 1}]),
                episode(id="b")]
        err = asmr.variete_ok(episode(id="c"), prec)
        self.assertTrue(any("scénario" in e for e in err) and any("décor" in e for e in err) and any("déclencheur" in e for e in err), err)

    def test_episode_different_accepte(self):
        neuf = episode(id="c", scenario="atelier", decor={"type": "atelier", "graine": 9}, declencheurs=[{"type": "brossage", "graine": 4}])
        self.assertEqual(asmr.variete_ok(neuf, [episode(id="b")]), [])

    def test_fenetre_limitee(self):
        vieux = episode(id="v", scenario="atelier", decor={"type": "atelier", "graine": 1}, declencheurs=[{"type": "brossage", "graine": 1}])
        autres = [episode(id=f"x{i}", scenario="the-chaud", decor={"type": "bougies", "graine": i}, declencheurs=[{"type": "grattement", "graine": i}])
                  for i in range(asmr.FENETRE_VARIETE)]
        nouveau = episode(id="n", scenario="atelier", decor={"type": "atelier", "graine": 3}, declencheurs=[{"type": "brossage", "graine": 3}])
        self.assertEqual(asmr.variete_ok(nouveau, [vieux] + autres), [])


class Sons(unittest.TestCase):
    def test_declencheurs_doux_deterministes_et_sans_raccord(self):
        for t in synth.DECLENCHEURS:
            a = synth.declencheur(t, 40, 7)
            self.assertTrue(np.array_equal(a, synth.declencheur(t, 40, 7)), t)
            self.assertFalse(np.array_equal(a, synth.declencheur(t, 40, 8)), t)
            self.assertLessEqual(float(np.abs(a).max()), 0.51)
            self.assertLess(float(np.abs(a[-synth.SR:]).max()), 0.01, f"{t} : la fin de la boucle doit être silencieuse (raccord)")
            self.assertGreater(float(np.abs(a).max()), 0.2, t)
        with self.assertRaises(ValueError):
            synth.declencheur("explosion", 10, 1)

    def test_decor_boucle(self):
        for t in asmr.DECORS:
            dec = asmr.Decor(t, 4, w=320, h=180)
            a, b = np.asarray(dec.image(0.0), dtype=np.int16), np.asarray(dec.image(30.0), dtype=np.int16)
            self.assertLess(float(np.abs(a - b).mean()), 1.0, f"{t} : la boucle de 30 s doit se raccorder")


class Rendu(unittest.TestCase):
    def test_rendu_et_miniature(self):
        ep = episode(ambiance={"type": "pluie", "graine": 5, "duree_min": 30})
        with tempfile.TemporaryDirectory() as tmp:
            ep_dir, out = Path(tmp, "ep"), Path(tmp, "out")
            ep_dir.mkdir()
            out.mkdir()
            s = asmr.script_voix(ep)
            faux.fausse_voix(ep_dir, s["phrases"], s["pauses"], mot_s=0.2)
            qa = {}
            final = asmr.rendre(ep, ep_dir, out, {}, qa, fps=4)
            self.assertTrue(final.exists())
            self.assertAlmostEqual(qa["duree_s"], 1800, delta=3)
            self.assertEqual(qa["declencheurs"], ["pages", "tapotement"])
        self.assertEqual(asmr.miniature(ep, {}).size, (1280, 720))


if __name__ == "__main__":
    unittest.main()
