"""Format sommeil : validation (douceur, durée, honnêteté), ambiances sans raccord, rendu léger. Aucun réseau, aucune publication."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from autopilot.formats import rendu, sommeil, synth
from autopilot.formats.tests import faux

RACINE = Path(__file__).resolve().parents[3]
DESC = {"description": "Une histoire douce. Cette vidéo détend mais ne remplace pas un avis médical.", "langue": "fr"}
PHRASES = [f"La nuit tombe doucement sur le petit village, et la lampe de la maison {m} brille." for m in
           ("bleue", "jaune", "verte", "grise", "rose") * 12]  # 60 phrases de 15 mots = 900 mots


def episode(**plus):
    ep = {"id": "sommeil-test", "titre": "Histoire pour s'endormir : le village", "chaine": "Sommeil", "theme": "sommeil", "video": "long", "format_contenu": "sommeil",
          "phrases": list(PHRASES), "ambiance": {"type": "pluie", "graine": 11, "duree_min": 60}, "decor": {"type": "nuit-etoilee", "graine": 5},
          "miniature": {"texte_haut": "Histoire douce", "gros": "Le village"}}
    ep.update(plus)
    return ep


def valider(ep, pub=None):
    return sommeil.valider_episode(ep, None, DESC if pub is None else pub, {}, reseau=False)


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau, pub=None):
        err, _ = valider(ep, pub)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_episode_valide(self):
        self.assertEqual(valider(episode())[0], [])

    def test_jamais_un_short(self):
        self.refuse(episode(video="short"), "jamais des Shorts")

    def test_duree_et_ambiance(self):
        self.refuse(episode(ambiance={"type": "pluie", "graine": 1, "duree_min": 10}), "duree_min")
        self.refuse(episode(ambiance={"type": "pluie", "graine": 1, "duree_min": 400}), "duree_min")
        self.refuse(episode(ambiance={"type": "tonnerre", "graine": 1, "duree_min": 60}), "ambiance.type")
        self.refuse(episode(ambiance={"type": "pluie", "graine": "x", "duree_min": 60}), "graine")
        self.refuse(episode(decor={"type": "disco", "graine": 1}), "decor.type")

    def test_histoire_obligatoire(self):
        err, _ = valider(episode(phrases=[]))
        self.assertTrue(err)
        ep = episode()
        del ep["phrases"]
        self.refuse(ep, "obligatoire")

    def test_ambiance_plus_courte_que_l_histoire(self):
        ph = [" ".join(["calme"] * 20) + "." for _ in range(150)]  # 3000 mots : trop long aussi
        self.refuse(episode(phrases=ph), "mots :")
        ph = [" ".join(["calme"] * 15) + "." for _ in range(100)]  # 1500 mots = ~15 min de voix lente
        err, _ = valider(episode(phrases=ph, ambiance={"type": "pluie", "graine": 1, "duree_min": 30}))
        self.assertFalse(any("plus courte" in e for e in err))  # 30 min couvrent bien 15 min de voix

    def test_mots_agites_exclamation_chiffres(self):
        for mal, morceau in (("Soudain un cri terrible réveille tout le village.", "trop agité"), ("Il est temps de dormir !", "exclamation"),
                             ("Il y a douze maisons et 3 chats endormis.", "chiffres"), ("Un orage gronde au loin dans la nuit.", "trop agité")):
            ph = list(PHRASES)
            ph[3] = mal
            self.refuse(episode(phrases=ph), morceau)

    def test_phrase_trop_longue(self):
        ph = list(PHRASES)
        ph[0] = " ".join(["doucement"] * 30)
        self.refuse(episode(phrases=ph), "22 au plus")

    def test_promesses_de_sante(self):
        ph = list(PHRASES)
        ph[2] = "Cette histoire va guérir ton insomnie."
        self.refuse(episode(phrases=ph), "promesse de santé")
        self.refuse(episode(titre="Dormir en dix minutes : garanti"), "promesse de santé")
        self.refuse(episode(), "promesse de santé", pub={"description": "Cette vidéo détend mais ne remplace pas un avis médical. Un miracle pour dormir.", "langue": "fr"})

    def test_phrase_d_honnetete_dans_la_description(self):
        self.refuse(episode(), "ne remplace pas un avis médical", pub={"description": "Une histoire douce.", "langue": "fr"})

    def test_miniature_obligatoire(self):
        ep = episode()
        del ep["miniature"]
        self.refuse(ep, "miniature")

    def test_forme_illisible(self):
        self.assertTrue(valider({"id": "x"})[0])
        self.assertTrue(sommeil.valider_episode(None, None, None, {})[0])


class Sons(unittest.TestCase):
    def test_ambiances_sans_raccord_et_deterministes(self):
        for t in sommeil.AMBIANCES:
            a = synth.ambiance(t, 4, graine=3)
            self.assertEqual(len(a), 4 * synth.SR)
            self.assertLess(float(np.max(np.abs(a))), 0.51)
            self.assertGreater(float(np.sqrt(np.mean(a ** 2))), 0.005, t)
            self.assertTrue(np.array_equal(a, synth.ambiance(t, 4, graine=3)))  # même graine = même son
            self.assertFalse(np.array_equal(a, synth.ambiance(t, 4, graine=4)))  # deux graines = deux vidéos différentes
            saut = abs(float(a[0]) - float(a[-1]))  # la boucle se raccorde : la fin rejoint le début sans clic
            self.assertLess(saut, 0.2, t)

    def test_ambiance_inconnue(self):
        with self.assertRaises(ValueError):
            synth.ambiance("tempete", 2)


class Rendu(unittest.TestCase):
    def test_rendu_leger_avec_fausse_voix(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-som-"))
        try:
            ep = episode(phrases=PHRASES[:10], ambiance={"type": "vagues", "graine": 2, "duree_min": 2}, decor={"type": "lune-sur-mer", "graine": 3})
            d, out = tmp / "ep", tmp / "out"
            d.mkdir()
            out.mkdir()
            s = sommeil.script_voix(ep)
            self.assertEqual(s["vitesses"]["1"], sommeil.VITESSE_VOIX)
            faux.fausse_voix(d, s["phrases"], s["pauses"], mot_s=0.2)
            qa = {}
            final = sommeil.rendre(ep, d, out, {}, qa, fps=5)
            self.assertAlmostEqual(qa["duree_s"], 120, delta=1.5)
            self.assertTrue(-24.5 <= qa["lufs"] <= -21.5, qa)
            self.assertLess(qa["taille_mo"], 15)  # rendu léger : pas de vidéo lourde pour une ambiance
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["sommeil-test.mp4"])  # fichiers intermédiaires supprimés
            self.assertGreater(rendu.duree(final), 100)
            self.assertEqual(sommeil.miniature(ep, {}).size, (1280, 720))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_les_trois_decors_se_dessinent_et_bouclent(self):
        for t in sommeil.DECORS:
            dec = sommeil.Decor(t, 9)
            a, b = dec.image(0.0), dec.image(float(sommeil.BOUCLE_VIDEO_S))
            self.assertEqual(a.size, (1280, 720))
            self.assertEqual(a.tobytes(), b.tobytes(), t)  # la boucle vidéo se raccorde exactement
            self.assertNotEqual(a.tobytes(), dec.image(3.0).tobytes(), t)  # ça bouge


class Banque(unittest.TestCase):
    def test_sujets_de_depart(self):
        s = json.loads((RACINE / "subjects" / "sommeil" / "00-sujets-de-depart.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s), 20)
        self.assertEqual(len({x["titre"] for x in s}), len(s))
        self.assertEqual({x["format"] for x in s}, {"long"})  # que des longs : aucun Short de sommeil


if __name__ == "__main__":
    unittest.main()
