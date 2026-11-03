"""Tests du format long et de la découpe en Shorts (sans voix réelle, sans rendu).

Lancer :  python -m unittest discover -s autopilot/long/tests -v      (depuis section3-motion/pixel-faits)
"""
import copy
import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
AUTOPILOT = HERE.parent.parent
sys.path.insert(0, str(AUTOPILOT))
sys.path.insert(0, str(AUTOPILOT / "long"))

import common  # noqa: E402
import cut_shorts  # noqa: E402
import longlib as L  # noqa: E402
import make_demo  # noqa: E402
import make_long  # noqa: E402
import make_short  # noqa: E402


def demo():
    return copy.deepcopy(make_demo.DEMO)


class Validation(unittest.TestCase):
    def test_la_demo_est_valide_en_souple(self):
        self.assertEqual(L.validate_long(demo(), minimum=False), [])

    def test_la_demo_est_trop_courte_pour_un_vrai_long(self):
        err = L.validate_long(demo())
        self.assertTrue(any("chapitres" in e for e in err))
        self.assertTrue(any("phrases : il en faut" in e for e in err))

    def test_champs_manquants(self):
        self.assertTrue(L.validate_long({"id": "x"}))

    def test_theme_inconnu(self):
        ep = demo()
        ep["theme"] = "rose"
        self.assertTrue(any("thème" in e for e in L.validate_long(ep, minimum=False)))

    def test_scene_doublon_de_type(self):
        ep = demo()
        ep["chapitres"][0]["scenes"][1]["type"] = "titre-geant"
        self.assertTrue(any("de suite" in e for e in L.validate_long(ep, minimum=False)))

    def test_premiere_scene_a_la_phrase_1(self):
        ep = demo()
        ep["chapitres"][1]["scenes"][0]["phrase"] = 2
        self.assertTrue(any("première scène" in e for e in L.validate_long(ep, minimum=False)))

    def test_scene_hors_chapitre(self):
        ep = demo()
        ep["chapitres"][2]["scenes"][-1]["phrase"] = 99
        self.assertTrue(any("entre 1 et 8" in e for e in L.validate_long(ep, minimum=False)))

    def test_icone_inconnue(self):
        ep = demo()
        ep["chapitres"][1]["scenes"][0]["params"]["icone"] = "fusee"
        self.assertTrue(any("icône" in e for e in L.validate_long(ep, minimum=False)))

    def test_phrase_trop_longue_et_promesse(self):
        ep = demo()
        ep["chapitres"][0]["phrases"][0] = "x" * 200
        ep["chapitres"][0]["phrases"][1] = "C'est garanti sans effort."
        err = " ".join(L.validate_long(ep, minimum=False))
        self.assertIn("trop longue", err)
        self.assertIn("interdite", err)

    def test_short_hors_chapitre_ou_trop_court(self):
        ep = demo()
        ep["chapitres"][0]["short"]["fin_phrase"] = 20
        ep["chapitres"][1]["short"] = {"debut_phrase": 1, "fin_phrase": 2, "accroche": "Trop court"}
        err = " ".join(L.validate_long(ep, minimum=False))
        self.assertIn("entre 1 et 8", err)
        self.assertIn("de 4 à 24 phrases", err)

    def test_au_plus_douze_shorts(self):
        ep = demo()
        for k in range(L.SHORTS_MAX):
            ep["chapitres"].append({**copy.deepcopy(ep["chapitres"][0]), "titre": f"Bonus {k}"})
        self.assertTrue(any("Shorts marqués" in e for e in L.validate_long(ep, minimum=False)))

    def test_le_theme_d_accent_passe_au_short(self):
        ep = demo()
        ep["theme_accent"] = "chocolat-caramel"
        self.assertEqual(L.validate_long(ep, minimum=False), [])
        court, _ = L.build_short_episode(ep, 0, "x-s1")
        self.assertEqual(court["theme_accent"], "chocolat-caramel")
        ep["theme_accent"] = "inconnu"
        self.assertTrue(any("accent" in e for e in L.validate_long(ep, minimum=False)))


class Aplatissement(unittest.TestCase):
    def test_numerotation_globale_et_pauses(self):
        fl = L.flatten(demo())
        self.assertEqual(len(fl["phrases"]), 24)
        self.assertEqual([c["first"] for c in fl["chapitres"]], [1, 9, 17])
        self.assertEqual(fl["pauses"], {9: 2.0, 17: 2.0})  # pas de pause avant le chapitre 1
        # la 1re scène du chapitre 2 (phrase locale 1) devient la phrase globale 9
        self.assertIn(("objet", 9), [(s["type"], s["phrase"]) for s in fl["scenes"]])
        self.assertEqual([s["phrase"] for s in fl["scenes"]], sorted(s["phrase"] for s in fl["scenes"]))

    def test_carte_desactivee(self):
        ep = demo()
        ep["chapitres"][1]["carte"] = False
        self.assertEqual(L.flatten(ep)["pauses"], {17: 2.0})

    def test_voix_entree(self):
        v = L.voix_entree(demo())
        self.assertEqual(len(v["phrases"]), 24)
        self.assertEqual(v["pauses"], {"9": 2.0, "17": 2.0})
        json.dumps(v)

    def test_chapitres_temps(self):
        ep = demo()
        tm = make_demo.timings_pour(ep)
        ch = L.chapitres_temps(ep, tm)
        self.assertEqual(ch[0]["borne_s"], 0.0)
        self.assertIsNone(ch[0]["carte_de_s"])
        for a, b in zip(ch, ch[1:]):  # les segments se touchent sans trou
            self.assertAlmostEqual(a["borne_fin_s"], b["borne_s"], places=3)
        self.assertAlmostEqual(ch[-1]["borne_fin_s"], tm["total"], places=3)
        self.assertGreater(ch[1]["debut_s"] - ch[1]["carte_de_s"], 1.5)  # le silence de la carte est visible
        self.assertAlmostEqual(sum(c["duree_s"] for c in ch), tm["total"], places=2)

    def test_timings_incoherents(self):
        ep = demo()
        tm = make_demo.timings_pour(ep)
        tm["lines"].pop()
        with self.assertRaises(ValueError):
            L.chapitres_temps(ep, tm)

    def test_plages_images_couvrent_tout(self):
        ep = demo()
        tm = make_demo.timings_pour(ep)
        pl = make_long.plages_images(L.chapitres_temps(ep, tm), tm["total"])
        self.assertEqual(pl[0][0], 0)
        for (_, b), (a, _) in zip(pl, pl[1:]):
            self.assertEqual(a, b + 1)
        self.assertEqual(pl[-1][1] + 1, int(-(-tm["total"] * 30 // 1)) + make_long.TAIL_FRAMES)


class ExtractionShort(unittest.TestCase):
    def test_les_shorts_de_la_demo_passent_validate(self):
        ep = demo()
        for k in range(3):
            sep, _ = L.build_short_episode(ep, k, f"x-s{k + 1}")
            self.assertEqual(make_short.validate(sep), [], f"Short {k + 1}")

    def test_scene_active_au_debut_passe_a_la_phrase_1(self):
        ep = demo()
        sep, _ = L.build_short_episode(ep, 1, "x-s1")  # chapitre 2, phrases 2..8
        self.assertEqual(sep["scenes"][0], {**ep["chapitres"][1]["scenes"][1], "phrase": 1})
        self.assertEqual(len(sep["phrases"]), 7)
        self.assertEqual(sep["phrases"][0], ep["chapitres"][1]["phrases"][1])

    def test_doublons_de_type_fusionnes(self):
        ep = demo()
        ch = ep["chapitres"][0]
        ch["scenes"] = [{"type": "titre-geant", "phrase": 1, "params": {}}, {"type": "chiffre", "phrase": 2, "params": {}},
                        {"type": "chiffre", "phrase": 4, "params": {}}, {"type": "question", "phrase": 6, "params": {}}]
        ch["short"] = {"debut_phrase": 1, "fin_phrase": 8, "accroche": "Test"}
        sep, notes = L.build_short_episode(ep, 0, "x-s1")
        self.assertEqual([s["type"] for s in sep["scenes"]], ["titre-geant", "chiffre", "question"])
        self.assertEqual(len(notes), 1)

    def test_rebase_timings(self):
        tm = make_demo.timings_pour(demo())
        rt, t0, t1 = L.rebase_timings(tm, 10, 16)
        self.assertAlmostEqual(rt["lines"][0]["start"], L.LEAD_S, places=3)
        self.assertAlmostEqual(rt["total"], t1 - t0, places=3)
        self.assertAlmostEqual(rt["lines"][-1]["end"] + L.TAIL_S, rt["total"], places=2)
        self.assertEqual(len(rt["lines"]), 7)
        self.assertEqual(rt["lines"][0]["words"][0]["w"], tm["lines"][9]["words"][0]["w"])

    def test_faits_renumerotes(self):
        f = L.faits_du_short(make_demo.FAITS, 10, 16)
        self.assertEqual([x["phrase"] for x in f], [1])
        self.assertEqual(L.faits_du_short(None, 1, 2), [])

    def test_publication_du_short(self):
        p = L.publication_du_short({"tags": ["a"]}, demo(), "x" * 90, None)
        self.assertLessEqual(len(p["titre"]), 70)
        self.assertEqual(p["tags"], ["a"])
        self.assertTrue(p["contenu_ia"])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg absent")
class DecoupeComplete(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="long-test-"))
        self.patch = mock.patch.object(common, "EPISODES", self.tmp)
        self.patch.start()
        self.tm = make_demo.build(self.tmp / "L")

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_trois_shorts_valides_avec_voix_decoupee(self):
        r = cut_shorts.cut("L")
        self.assertEqual([s["id"] for s in r["shorts"]], ["L-s1", "L-s2", "L-s3"])
        self.assertEqual(r["ignores"], [])
        for s in r["shorts"]:
            d = self.tmp / s["id"]
            ep = json.loads((d / "episode.json").read_text(encoding="utf-8"))
            tm = json.loads((d / "timings.json").read_text(encoding="utf-8"))
            self.assertEqual(make_short.validate(ep), [])
            self.assertEqual(len(tm["lines"]), len(ep["phrases"]))
            self.assertAlmostEqual(L.duree(d / "voice.wav"), tm["total"], delta=0.06)
            self.assertLessEqual(tm["total"], 58)
            self.assertEqual(common.get_status(s["id"])["etat"], "ecrit")
            self.assertEqual(common.get_status(s["id"])["origine"], "L")
            self.assertTrue((d / "origine.json").exists())
            self.assertTrue((d / "voice_report.json").exists())
            self.assertEqual(json.loads((d / "publication.json").read_text(encoding="utf-8"))["langue"], "fr")
        # le timbre de la voix collée au texte : le mot calé à 0,15 s est bien là et l'audio est sonore
        m = L.mesure(self.tmp / "L-s2" / "voice.wav", -16, -1.5, 7)
        self.assertAlmostEqual(float(m["input_i"]), -16.0, delta=1.0)

    def test_maximum_de_shorts(self):
        r = cut_shorts.cut("L", maximum=2)
        self.assertEqual(len(r["shorts"]), 2)
        self.assertEqual(len(r["ignores"]), 1)
        self.assertFalse((self.tmp / "L-s3").exists())

    def test_un_short_avance_nest_pas_ecrase(self):
        cut_shorts.cut("L")
        common.set_status("L-s1", "controle")
        marque = self.tmp / "L-s1" / "episode.json"
        marque.write_text(json.dumps({"id": "modifie"}), encoding="utf-8")
        r = cut_shorts.cut("L")
        self.assertEqual({s["id"] for s in r["shorts"]}, {"L-s2", "L-s3"})
        self.assertIn("déjà", r["ignores"][0]["raison"][0])
        self.assertEqual(json.loads(marque.read_text(encoding="utf-8"))["id"], "modifie")
        r = cut_shorts.cut("L", force=True)
        self.assertEqual(len(r["shorts"]), 3)

    def test_short_trop_long_est_ignore(self):
        ep = json.loads((self.tmp / "L" / "episode-long.json").read_text(encoding="utf-8"))
        tm = json.loads((self.tmp / "L" / "timings.json").read_text(encoding="utf-8"))
        tm["lines"][15]["end"] += 60  # la dernière phrase du Short du chapitre 2 dure une minute de plus
        common.write_json(self.tmp / "L" / "timings.json", tm)
        common.write_json(self.tmp / "L" / "episode-long.json", ep)
        r = cut_shorts.cut("L")
        self.assertEqual(len(r["shorts"]), 2)
        self.assertTrue(any("58" in x for i in r["ignores"] for x in i["raison"]))

    def test_dossier_incomplet(self):
        (self.tmp / "L" / "voice.wav").unlink()
        self.assertIn("erreur", cut_shorts.cut("L"))
        self.assertIn("erreur", cut_shorts.cut("inconnu"))

    def test_audio_de_demo_a_la_duree_des_timings(self):
        self.assertAlmostEqual(L.duree(self.tmp / "L" / "voice.wav"), self.tm["total"], delta=0.05)


class ReprisesDeVoix(unittest.TestCase):
    """make_long sans GPU : le code retour de voice.py pilote l'état de l'épisode."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="long-voix-"))
        self.patches = [mock.patch.object(common, "EPISODES", self.tmp / "e"), mock.patch.object(common, "EXPORTS", self.tmp / "x")]
        for p in self.patches:
            p.start()
        d = self.tmp / "e" / "L"
        d.mkdir(parents=True)
        common.write_json(d / "episode-long.json", demo())
        (d / "voice.log").write_text("[1/24] cache (1.00) a\n[2/24] [1.0] -> 1.00 | b\n[3/24] [0.9] -> 0.95 | c\n", encoding="utf-8")

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lancer(self, rc):
        with mock.patch.object(make_long, "lancer_voix", return_value=rc) as m:
            return make_long.main(["L", "--souple"]), m

    def test_budget_atteint_libere_le_gpu_et_reprend_plus_tard(self):
        code, m = self.lancer(3)
        self.assertEqual(code, 3)
        st = common.get_status("L")
        self.assertEqual(st["etat"], "ecrit")
        self.assertEqual(st["voix_progression"]["faites"], 3)
        self.assertEqual(st["voix_progression"]["total"], 24)
        self.assertEqual(m.call_args[0][3], 90 * 60)  # budget par défaut : 90 minutes
        self.assertTrue((self.tmp / "e" / "L" / "voix-entree.json").exists())

    def test_gpu_occupe_est_une_reprise_pas_une_panne(self):
        with mock.patch.object(make_long, "lancer_voix", side_effect=TimeoutError("verrou occupé")):
            self.assertEqual(make_long.main(["L", "--souple"]), 3)
        self.assertEqual(common.get_status("L")["etat"], "ecrit")

    def test_trois_echecs_de_voix_mettent_en_quarantaine(self):
        for attendu in (3, 3, 2):
            code, _ = self.lancer(1)
            self.assertEqual(code, attendu)
        st = common.get_status("L")
        self.assertEqual(st["etat"], "quarantaine")
        self.assertIn("voice.py", st["raison"])

    def test_episode_invalide_va_en_quarantaine_sans_voix(self):
        ep = demo()
        ep["chapitres"][0]["scenes"][0]["type"] = "inconnu"
        common.write_json(self.tmp / "e" / "L" / "episode-long.json", ep)
        code, m = self.lancer(0)
        self.assertEqual(code, 2)
        m.assert_not_called()
        self.assertEqual(common.get_status("L")["etat"], "quarantaine")

    def test_budget_en_minutes_transmis(self):
        with mock.patch.object(make_long, "lancer_voix", return_value=3) as m:
            make_long.main(["L", "--souple", "--budget-min", "45"])
        self.assertEqual(m.call_args[0][3], 45 * 60)

    def test_voix_a_jour_depend_du_texte(self):
        d = self.tmp / "e" / "L"
        entree = L.voix_entree(demo())
        self.assertFalse(make_long.voix_a_jour(d, entree))
        make_demo.build(d)
        (d / "voix.sha").write_text(L.sha(entree), encoding="utf-8")
        self.assertTrue(make_long.voix_a_jour(d, entree))
        entree["phrases"][0] += " Modifiée."
        self.assertFalse(make_long.voix_a_jour(d, entree))


class Integration(unittest.TestCase):
    def test_scripts_compilent(self):
        for f in ("voice.py", "make_short.py", "make_long.py", "cut_shorts.py"):
            py_compile.compile(str(AUTOPILOT / f), doraise=True, cfile=str(Path(tempfile.gettempdir()) / f"{f}.pyc"))

    def test_voice_py_a_ses_options_longues(self):
        src = (AUTOPILOT / "voice.py").read_text(encoding="utf-8")
        for needle in ("--episode-file", "--budget-s", "pauses", "sys.exit(3)"):
            self.assertIn(needle, src)

    def test_make_short_refuse_une_voix_prete_absente(self):
        """Un Short dérivé sans voice.wav ne doit jamais retomber sur voice.py : qa.json en erreur, code 2."""
        ep_id = "_test-voix-prete"
        d, out = common.ROOT / "episodes-b" / ep_id, common.ROOT / "exports-b" / ep_id
        try:
            sep, _ = L.build_short_episode(demo(), 0, ep_id)
            common.write_json(d / "episode.json", sep)
            r = subprocess.run([sys.executable, str(AUTOPILOT / "make_short.py"), ep_id, "--voix-prete"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertTrue(any("voix prête" in p for p in qa["problemes"]))
            self.assertNotIn("voice.py", r.stdout)
            # même sécurité avec origine.json seul (aucun drapeau)
            common.write_json(d / "origine.json", {"long": "x"})
            r = subprocess.run([sys.executable, str(AUTOPILOT / "make_short.py"), ep_id], capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertNotIn("voice.py", r.stdout)
        finally:
            shutil.rmtree(d, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
