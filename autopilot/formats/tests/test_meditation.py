"""Format méditation : validation (douceur, durée, honnêteté), voix lente à longues pauses, décors qui bouclent, rendu léger. Aucun réseau, aucune publication."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from autopilot import chaines
from autopilot.formats import meditation, rendu
from autopilot.formats.tests import faux

RACINE = Path(__file__).resolve().parents[3]
DESC = {"description": "Une séance guidée. Ne remplace pas un avis médical. Ne pas écouter en conduisant.", "langue": "fr", "contenu_ia": True}
DEBUT = ["Installe-toi confortablement.", "Pose tes mains sur tes genoux.", "Ferme doucement les yeux.", "Inspire doucement par le nez.", "Souffle lentement par la bouche."]
PHRASES = DEBUT + [f"Sens la chaleur de la lumière {m} sur ton visage et laisse ton corps se poser." for m in
                   ("dorée rose claire tendre paisible lente calme ambrée pâle limpide dense fine douce chaude fraîche "
                    "ronde large haute basse sage tiède vive neuve libre unie souple fluide nette ample").split()]  # 35 phrases


def episode(**plus):
    ep = {"id": "meditation-test", "titre": "Méditation guidée : la lumière douce", "chaine": "Méditation", "theme": "meditation", "video": "long", "format_contenu": "meditation",
          "phrases": list(PHRASES), "ambiance": {"type": "nappe", "graine": 11, "duree_min": 10}, "decor": {"type": "aube-collines", "graine": 5},
          "miniature": {"texte_haut": "Méditation guidée", "gros": "Lumière douce"}}
    ep.update(plus)
    return ep


def valider(ep, pub=None):
    return meditation.valider_episode(ep, None, DESC if pub is None else pub, {}, reseau=False)


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau, pub=None):
        err, _ = valider(ep, pub)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_episode_valide(self):
        self.assertEqual(valider(episode())[0], [])

    def test_jamais_un_short(self):
        self.refuse(episode(video="short"), "jamais des Shorts")

    def test_duree_ambiance_et_decor(self):
        self.refuse(episode(ambiance={"type": "nappe", "graine": 1, "duree_min": 5}), "duree_min")
        self.refuse(episode(ambiance={"type": "nappe", "graine": 1, "duree_min": 60}), "duree_min")
        self.refuse(episode(ambiance={"type": "tonnerre", "graine": 1, "duree_min": 10}), "ambiance.type")
        self.refuse(episode(ambiance={"type": "nappe", "graine": "x", "duree_min": 10}), "graine")
        self.refuse(episode(decor={"type": "disco", "graine": 1}), "decor.type")

    def test_seance_obligatoire(self):
        ep = episode()
        del ep["phrases"]
        self.refuse(ep, "obligatoire")
        self.assertTrue(valider(episode(phrases=[]))[0])

    def test_seance_trop_longue_pour_la_video(self):
        ph = DEBUT + [f"Laisse venir une image {m} et lente dans ton esprit calme." for m in ["bleue", "verte", "rose", "dorée", "claire", "pâle"] * 20]
        self.refuse(episode(phrases=ph), "plus courte")

    def test_voix_qui_remplit_trop_peu(self):
        self.refuse(episode(ambiance={"type": "nappe", "graine": 1, "duree_min": 40}), "ne remplit que")

    def test_mots_agites_exclamation_chiffres_phrase_longue(self):
        for mal, morceau in (("N'aie pas peur, tout est calme.", "apaisant"), ("Respire avec calme !", "exclamation"),
                             ("Compte jusqu'à 3 en respirant.", "chiffres"), ("Un orage gronde au loin.", "apaisant"), (" ".join(["doucement"] * 20), "au plus")):
            ph = list(PHRASES)
            ph[8] = mal
            self.refuse(episode(phrases=ph), morceau)

    def test_aucune_promesse_de_sante_ni_conseil_medical(self):
        for mal in ("Cette séance va guérir ton anxiété.", "Respire, cela soulage la douleur.", "Arrête ton traitement et respire.", "Cette méditation réduit le stress."):
            ph = list(PHRASES)
            ph[7] = mal
            self.refuse(episode(phrases=ph), "promesse de santé")
        self.refuse(episode(titre="Méditation guidée : un miracle garanti"), "promesse de santé")
        self.refuse(episode(), "promesse de santé", pub={**DESC, "description": DESC["description"] + " Soigne ton insomnie."})

    def test_phrase_d_honnetete_et_contenu_ia(self):
        self.refuse(episode(), "avis médical", pub={**DESC, "description": "Une séance guidée."})
        self.refuse(episode(), "contenu_ia", pub={**DESC, "contenu_ia": False})
        self.refuse(episode(), "contenu_ia", pub={k: v for k, v in DESC.items() if k != "contenu_ia"})

    def test_la_seance_invite_a_respirer(self):
        ph = [p for p in PHRASES if not meditation.RE_SOUFFLE.search(p)]
        self.refuse(episode(phrases=ph), "respirer")

    def test_pas_une_simple_repetition(self):
        ph = PHRASES[:5] + ["Respire doucement et reste calme."] * 30
        self.refuse(episode(phrases=ph), "identiques")

    def test_miniature_obligatoire_et_titre(self):
        ep = episode()
        del ep["miniature"]
        self.refuse(ep, "miniature")
        self.refuse(episode(titre="M" * 80), "titre")

    def test_forme_illisible(self):
        self.assertTrue(valider({"id": "x"})[0])
        self.assertTrue(meditation.valider_episode(None, None, None, {})[0])


class Voix(unittest.TestCase):
    def test_pauses_longues_apres_une_invitation_a_respirer(self):
        s = meditation.script_voix(episode())
        self.assertEqual(s["phrases"], PHRASES)
        self.assertNotIn("1", s["pauses"])  # pas de silence avant la première phrase
        self.assertEqual(s["pauses"]["5"], meditation.PAUSE_LONGUE_S)  # après « Inspire doucement par le nez. »
        self.assertEqual(s["pauses"]["2"], meditation.PAUSE_COURTE_S)
        self.assertEqual(s["vitesses"]["1"], meditation.VITESSE_VOIX)
        self.assertGreaterEqual(meditation.VITESSE_VOIX, 0.8)  # voice.py borne la vitesse à 0,8
        self.assertEqual(len(s["vitesses"]), len(PHRASES))

    def test_aucune_balise_d_emotion(self):
        self.assertFalse(any("[" in p for p in meditation.script_voix(episode())["phrases"]))


class Rendu(unittest.TestCase):
    def test_les_trois_decors_bouclent_et_bougent(self):
        for t in meditation.DECORS:
            dec = meditation.Decor(t, 9)
            a, b = dec.image(0.0), dec.image(float(meditation.BOUCLE_VIDEO_S))
            self.assertEqual(a.size, (1280, 720))
            self.assertEqual(a.tobytes(), b.tobytes(), t)
            self.assertNotEqual(a.tobytes(), dec.image(5.0).tobytes(), t)

    def test_palette_chaude_pas_de_vert_pelouse(self):
        r, g, b = rendu.hex_rgb(meditation.STYLE["bas"])
        self.assertTrue(r > 200 and r > g > b)  # horizon abricot
        px = meditation.Decor("lac-doux", 3).image(0.0).getpixel((640, 10))
        self.assertTrue(px[2] >= px[1], px)  # le haut du ciel est lavande (bleu/violet), jamais vert

    def test_rendu_court_avec_fausse_voix(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-med-"))
        try:
            ep = episode(phrases=PHRASES[:8], ambiance={"type": "vagues", "graine": 2, "duree_min": 2}, decor={"type": "souffle", "graine": 3})
            d, out = tmp / "ep", tmp / "out"
            d.mkdir()
            out.mkdir()
            s = meditation.script_voix(ep)
            faux.fausse_voix(d, s["phrases"], s["pauses"], mot_s=0.2)
            qa = {}
            final = meditation.rendre(ep, d, out, {}, qa, fps=5)
            self.assertAlmostEqual(qa["duree_s"], 120, delta=1.5)
            self.assertTrue(-24.5 <= qa["lufs"] <= -21.5, qa)
            self.assertLess(qa["taille_mo"], 15)
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["meditation-test.mp4"])
            self.assertGreater(rendu.duree(final), 100)
            self.assertEqual(meditation.miniature(ep, {}).size, (1280, 720))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Profil(unittest.TestCase):
    def test_profil_inactif_et_branche(self):
        p = json.loads((RACINE / "autopilot" / "chaines" / "meditation.json").read_text(encoding="utf-8"))
        self.assertIs(p["active"], False)
        self.assertIs(p["preparation"], False)
        self.assertEqual(p["format"], "meditation")
        self.assertEqual(p["format_module"], "autopilot.formats.meditation")
        self.assertEqual(p["briques"], {"fabrique": "formats/fabrique.py", "miniature": "formats/miniature_formats.py"})
        self.assertEqual(p["frequence"]["shorts_par_jour"], 0)
        self.assertIs(p["publication"]["mention_ia_description"], True)
        self.assertEqual(chaines.valider_profil(p), [])
        self.assertIs(meditation.CONTROLES_STANDARD, False)
        self.assertIn("meditation", chaines.FORMATS)
        self.assertEqual(meditation.DUREE_S["long"][0], 600)

    def test_voix_a_confirmer(self):
        v = json.loads((RACINE / "autopilot" / "voix" / "meditation" / "voix.json").read_text(encoding="utf-8"))
        self.assertTrue(v["locuteur"])
        self.assertIs(v["a_confirmer"], True)
        self.assertIn("Apache-2.0", v["licence"])

    def test_consignes_disent_l_essentiel(self):
        c = meditation.consignes({})
        for mot in ("Ne remplace pas un avis médical", "contenu_ia", "NOUVELLE"):
            self.assertIn(mot, c)


class Banque(unittest.TestCase):
    def test_sujets_de_depart(self):
        s = json.loads((RACINE / "subjects" / "meditation" / "00-sujets-de-depart.json").read_text(encoding="utf-8"))
        self.assertEqual(len(s), 30)
        self.assertEqual(len({x["titre"] for x in s}), 30)
        self.assertEqual({x["format"] for x in s}, {"long"})
        for x in s:
            self.assertLessEqual(len(x["titre"]), 70)
            self.assertIsNone(meditation.RE_SANTE.search(x["titre"] + " " + x["angle"]), x)
        themes = {x["theme"].lower() for x in s}
        for t in ("respiration", "scan du corps", "lâcher-prise", "gratitude", "marche imaginaire"):
            self.assertIn(t, themes)


if __name__ == "__main__":
    unittest.main()
