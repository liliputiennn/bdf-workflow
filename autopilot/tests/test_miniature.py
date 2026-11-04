"""Tests de la brique miniatures (logique de contrôle, priorité manuelle, transitions d'état).

Lancer :  python -m unittest discover -s autopilot/tests -v      (depuis section3-motion/pixel-faits)
Aucun rendu Remotion : `fabriquer` est remplacé par un faux ; seul ffmpeg sert au test de recompression.
"""
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402
import miniature as mini  # noqa: E402

W, H = mini.VW, mini.VH


def png(w: int, h: int, rgb=(40, 40, 40), bruit: bool = False) -> bytes:
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d))
    raw = b"".join(b"\x00" + (os.urandom(w * 3) if bruit else bytes(rgb) * w) for _ in range(h))
    return mini.PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b"")


def scene(fond, texte, rect, canal=0):
    """Vignette 168×94 de couleur `fond` + masque noir portant un rectangle `rect` = (x0, y0, x1, y1) de pur rouge/vert/bleu."""
    x0, y0, x1, y1 = rect
    vign = [[fond for _ in range(W)] for _ in range(H)]
    masque = [[(0, 0, 0) for _ in range(W)] for _ in range(H)]
    for y in range(y0, y1):
        for x in range(x0, x1):
            vign[y][x] = texte
            masque[y][x] = tuple(255 if i == canal else 0 for i in range(3))
    return vign, masque


class Contraste(unittest.TestCase):
    def test_noir_sur_blanc_vaut_21(self):
        self.assertAlmostEqual(mini.ratio_contraste(mini.luminance((255, 255, 255)), mini.luminance((0, 0, 0))), 21.0, places=1)

    def test_symetrique_et_identique_vaut_1(self):
        a, b = mini.luminance((10, 90, 60)), mini.luminance((240, 240, 230))
        self.assertEqual(mini.ratio_contraste(a, b), mini.ratio_contraste(b, a))
        self.assertEqual(mini.ratio_contraste(a, a), 1.0)


class Controle(unittest.TestCase):
    def test_bon_texte_passe(self):
        v, m = scene((245, 240, 230), (18, 32, 26), (10, 30, 100, 70))
        r = mini.controler(v, m)
        self.assertTrue(r["ok"], r["raisons"])
        self.assertGreater(r["canaux"]["principal"]["contraste"], 10)
        self.assertGreater(r["canaux"]["principal"]["largeur"], 0.5)

    def test_contraste_faible_echoue(self):
        v, m = scene((120, 130, 125), (140, 150, 145), (10, 30, 100, 70))
        r = mini.controler(v, m)
        self.assertFalse(r["ok"])
        self.assertTrue(any("contraste" in x for x in r["raisons"]))

    def test_texte_trop_etroit_echoue(self):
        v, m = scene((245, 240, 230), (18, 32, 26), (10, 30, 50, 70))  # 40 px sur 168 = 24 %
        r = mini.controler(v, m)
        self.assertFalse(r["ok"])
        self.assertTrue(any("étroit" in x for x in r["raisons"]))

    def test_juste_au_tiers_passe(self):
        v, m = scene((245, 240, 230), (18, 32, 26), (10, 30, 10 + 57, 70))  # 57 px = 33,9 %
        self.assertTrue(mini.controler(v, m)["ok"])

    def test_texte_coupe_par_le_bord_echoue(self):
        v, m = scene((245, 240, 230), (18, 32, 26), (0, 30, 100, 70))
        r = mini.controler(v, m)
        self.assertTrue(any("coupé" in x for x in r["raisons"]))

    def test_texte_sous_la_duree_youtube_echoue(self):
        v, m = scene((245, 240, 230), (18, 32, 26), (60, 60, 160, 92))
        r = mini.controler(v, m)
        self.assertTrue(any("durée" in x for x in r["raisons"]))

    def test_aucun_texte_principal_echoue(self):
        v, m = scene((245, 240, 230), (18, 32, 26), (10, 30, 100, 70), canal=2)  # seulement des légendes
        r = mini.controler(v, m)
        self.assertFalse(r["ok"])
        self.assertTrue(any("introuvable" in x for x in r["raisons"]))

    def test_les_legendes_ne_bloquent_pas(self):
        v, m = scene((245, 240, 230), (18, 32, 26), (10, 30, 100, 70))
        for y in range(80, 86):  # une légende pâle : mesurée, jamais bloquante
            for x in range(10, 60):
                v[y][x] = (240, 238, 228)
                m[y][x] = (0, 0, 255)
        self.assertTrue(mini.controler(v, m)["ok"])


class Manuelle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_valide(self):
        f = self.tmp / "a.png"
        f.write_bytes(png(1280, 720))
        self.assertEqual(mini.verifier_manuelle(f), [])

    def test_mauvaise_taille(self):
        f = self.tmp / "a.png"
        f.write_bytes(png(1920, 1080))
        self.assertIn("1920×1080", mini.verifier_manuelle(f)[0])

    def test_trop_lourde(self):
        f = self.tmp / "a.png"
        f.write_bytes(png(1280, 720))
        with mock.patch.object(mini, "MAX_OCTETS", 100):
            self.assertTrue(any("Mo" in r for r in mini.verifier_manuelle(f)))

    def test_pas_un_png(self):
        f = self.tmp / "a.png"
        f.write_bytes(b"GIF89a....")
        self.assertIn("illisible", mini.verifier_manuelle(f)[0])


class Styles(unittest.TestCase):
    def test_ordre(self):
        self.assertEqual(mini.ordre_styles("contraste", True), ["contraste", "createur", "telephone", "pile", "chiffre", "question"])
        self.assertEqual(mini.ordre_styles(None, True)[0], "createur")
        self.assertEqual(mini.ordre_styles(None, False)[0], "question")
        self.assertEqual(sorted(mini.ordre_styles("inconnu", True)), sorted(mini.STYLES))


class Transitions(unittest.TestCase):
    """Un faux dossier d'épisodes ; `fabriquer` (Remotion) est remplacé."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p1 = mock.patch.object(common, "ROOT", self.tmp)
        self.p2 = mock.patch.object(common, "EPISODES", self.tmp / "episodes-b")
        self.p1.start(), self.p2.start()
        self.d = self.tmp / "episodes-b" / "ep"
        self.d.mkdir(parents=True)
        (self.d / "episode.json").write_text("{}", encoding="utf-8")
        common.set_status("ep", "controle")

    def tearDown(self):
        self.p1.stop(), self.p2.stop()

    def faux_ok(self):
        img = self.tmp / "essai.png"
        img.write_bytes(png(1280, 720, (200, 220, 200)))
        ess = {"style": "chiffre", "image": img, "ok": True, "raisons": [], "canaux": {"principal": {"present": True, "contraste": 9.0, "largeur": 0.5}}}
        return {"ok": True, "essais": [ess], "retenu": ess}

    def test_priorite_manuelle_copie_telle_quelle_sans_rendu(self):
        man = self.tmp / "miniatures-manuelles"
        man.mkdir()
        contenu = png(1280, 720, (1, 2, 3))
        (man / "ep.png").write_bytes(contenu)
        with mock.patch.object(mini, "fabriquer", side_effect=AssertionError("ne doit pas rendre")):
            self.assertEqual(mini.traiter("ep"), 0)
        self.assertEqual((self.d / "miniature.png").read_bytes(), contenu)
        st = common.get_status("ep")
        self.assertEqual(st["etat"], "pret")
        self.assertEqual(st["miniature"]["source"], "manuelle")

    def test_manuelle_invalide_met_en_quarantaine_avec_raison(self):
        man = self.tmp / "miniatures-manuelles"
        man.mkdir()
        (man / "ep.png").write_bytes(png(800, 600))
        self.assertEqual(mini.traiter("ep"), 2)
        st = common.get_status("ep")
        self.assertEqual(st["etat"], "quarantaine")
        self.assertIn("800×600", st["raison"])

    def test_auto_ok_passe_a_pret(self):
        with mock.patch.object(mini, "fabriquer", return_value=self.faux_ok()):
            self.assertEqual(mini.traiter("ep"), 0)
        self.assertTrue((self.d / "miniature.png").exists())
        st = common.get_status("ep")
        self.assertEqual((st["etat"], st["miniature"]["source"], st["miniature"]["fichier"]), ("pret", "auto", "miniature.png"))
        self.assertTrue((self.d / "miniature_report.json").exists())

    def test_echec_de_toutes_les_mises_en_page_quarantaine(self):
        res = self.faux_ok()
        ess = {**res["retenu"], "ok": False, "raisons": ["contraste trop faible"]}
        res = {"ok": False, "essais": [ess], "meilleur": ess, "raison": "chiffre : contraste trop faible"}
        with mock.patch.object(mini, "fabriquer", return_value=res):
            self.assertEqual(mini.traiter("ep"), 2)
        st = common.get_status("ep")
        self.assertEqual(st["etat"], "quarantaine")
        self.assertIn("contraste", st["raison"])
        self.assertFalse((self.d / "miniature.png").exists())

    def test_erreur_technique_ne_plante_pas_mais_met_en_quarantaine(self):
        with mock.patch.object(mini, "fabriquer", side_effect=RuntimeError("remotion absent")):
            self.assertEqual(mini.traiter("ep"), 2)
        self.assertIn("remotion absent", common.get_status("ep")["raison"])

    def test_n_agit_que_sur_controle(self):
        common.set_status("ep", "rendu")
        with mock.patch.object(mini, "fabriquer", side_effect=AssertionError("ne doit pas rendre")):
            self.assertEqual(mini.traiter("ep"), 1)
        self.assertEqual(common.get_status("ep")["etat"], "rendu")

    def test_sans_etat_ne_touche_pas_au_statut(self):
        common.set_status("ep", "rendu")
        with mock.patch.object(mini, "fabriquer", return_value=self.faux_ok()):
            self.assertEqual(mini.traiter("ep", sans_etat=True), 0)
        self.assertEqual(common.get_status("ep")["etat"], "rendu")
        self.assertTrue((self.d / "miniature.png").exists())


class Variantes(unittest.TestCase):
    """Un long reçoit jusqu'à deux autres miniatures pour le test A/B de YouTube ; un Short n'en reçoit pas."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.d = self.tmp / "ep"
        (self.d).mkdir()
        self.n = 0

    def faux_essayer(self, base, style, work):
        self.n += 1
        img = self.tmp / f"{style}.png"
        img.write_bytes(png(1280, 720, (10 * self.n, 20, 30)))
        return {"style": style, "image": img, "hash": style, "ok": style != "question", "raisons": []}

    def res(self):
        return {"essais": [{"style": "createur", "hash": "retenue"}]}

    def test_un_short_n_a_pas_de_variantes(self):
        with mock.patch.object(mini, "essayer", side_effect=AssertionError("ne doit pas rendre")):
            self.assertEqual(mini.ecrire_variantes("ep", self.res(), self.d), [])

    def test_un_long_recoit_deux_variantes_differentes_qui_passent_le_controle(self):
        (self.d / "episode-long.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(mini, "essayer", side_effect=self.faux_essayer):
            v = mini.ecrire_variantes("ep", self.res(), self.d)
        self.assertEqual([x["fichier"] for x in v], ["miniature_b.png", "miniature_c.png"])
        self.assertEqual([x["style"] for x in v], ["chiffre", "contraste"])  # « question » a échoué au contrôle : sautée
        self.assertTrue((self.d / "miniature_b.png").exists() and (self.d / "miniature_c.png").exists())

    def test_une_variante_identique_ou_en_erreur_est_ignoree(self):
        (self.d / "episode-long.json").write_text("{}", encoding="utf-8")
        res = {"essais": [{"style": "createur", "hash": "chiffre"}]}  # « chiffre » ressemble à la retenue
        def essayer(base, style, work):
            if style == "contraste":
                raise RuntimeError("remotion")
            return self.faux_essayer(base, style, work)
        with mock.patch.object(mini, "essayer", side_effect=essayer):
            v = mini.ecrire_variantes("ep", res, self.d)
        self.assertNotIn("chiffre", [x["style"] for x in v])
        self.assertNotIn("contraste", [x["style"] for x in v])


class Compression(unittest.TestCase):
    def test_trop_lourd_donne_un_jpeg_sous_la_limite(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "gros.png"
        src.write_bytes(png(1280, 720, bruit=True))
        with mock.patch.object(mini, "MAX_OCTETS", 600 * 1024):
            fin = mini.ecrire_finale(src, tmp)
            self.assertEqual(fin.name, "miniature.jpg")
            self.assertLessEqual(fin.stat().st_size, 600 * 1024)
            self.assertFalse((tmp / "miniature.png").exists())

    def test_leger_reste_png(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "petit.png"
        src.write_bytes(png(1280, 720))
        self.assertEqual(mini.ecrire_finale(src, tmp).name, "miniature.png")


if __name__ == "__main__":
    unittest.main()
