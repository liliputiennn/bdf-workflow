"""Référencement (hashtags, mots-clés), variété (gabarits, formes de titre) et banc d'idées.

Lancer :  python -m unittest autopilot.tests.test_referencement      (depuis section3-motion/pixel-faits)
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "autopilot"))
from autopilot import seo  # noqa: E402
from autopilot.writer import gabarits, sujets, valider  # noqa: E402


class Seo(unittest.TestCase):
    def test_hashtags_du_texte_sans_doublon_ni_chiffres_seuls(self):
        self.assertEqual(seo.hashtags_du_texte("a #Argent b #argent #12 #1er https://x.fr/#top #Café"), ["#Argent", "#1er", "#Café"])

    def test_limiter_garde_les_premiers(self):
        self.assertEqual(seo.hashtags_du_texte(seo.limiter_hashtags("#aa1 #bb2 #cc3 #dd4 #ee5", 3)), ["#aa1", "#bb2", "#cc3"])

    def test_hashtag_depuis_un_tag(self):
        self.assertEqual(seo.hashtag("graveuse laser"), "#GraveuseLaser")
        self.assertEqual(seo.hashtag("idée d'été"), "#IdéeÉté")
        self.assertIsNone(seo.hashtag("2026"))
        self.assertIsNone(seo.hashtag("x" * 40))

    def test_completer_vise_une_dizaine_sans_depasser_quinze(self):
        ligne = seo.completer_hashtags("Texte #Business", ["graveuse laser", "argent", "revendre", "idée"], "Graveuse laser et gain par jour",
                                       chaine=["#LaDébrouille", "#Argent", "#Entrepreneur", "#IdéesBusiness", "#Astuces"], reserves=["#Shorts"])
        total = seo.hashtags_du_texte("Texte #Business " + ligne)
        self.assertEqual(len(total), seo.HASHTAGS_CIBLE)
        self.assertEqual(total[-1], "#Shorts")
        self.assertEqual(len(set(h.lower() for h in total)), len(total))

    def test_deja_assez_de_hashtags_rien_a_ajouter(self):
        texte = " ".join(f"#mot{i}" for i in range(12))
        self.assertEqual(seo.completer_hashtags(texte, ["a b c"], "titre", chaine=["#X1"]), "")

    def test_bloc_de_mots_cles(self):
        b = seo.bloc_mots_cles("Vendre des modèles Canva", ["canva", "vendre canva", "business"])
        self.assertTrue(b.startswith("Mots-clés : canva, vendre canva, business"))
        self.assertLessEqual(len(b), seo.MOTS_CLES_MAX_CAR + 12)
        self.assertTrue(seo.a_bloc_mots_cles("x\n" + b))
        self.assertFalse(seo.a_bloc_mots_cles("pas de bloc"))

    def test_mentions_interdites(self):
        for t in ("Voix de synthèse (IA).", "contenu généré par IA", "Ceci n'est pas un conseil financier", "je ne garantis rien"):
            self.assertTrue(seo.RE_MENTION_INTERDITE.search(t), t)
        for t in ("Les 7 services d'IA que les commerces paient", "Un business avec ChatGPT"):
            self.assertIsNone(seo.RE_MENTION_INTERDITE.search(t), t)

    def test_formes_de_titre(self):
        self.assertEqual(seo.forme_du_titre("5 machines à acheter"), "liste")
        self.assertEqual(seo.forme_du_titre("Combien rapporte ce job ?"), "question")
        self.assertEqual(seo.forme_du_titre("Arrête de revendre sans calculer"), "interdit")
        self.assertEqual(seo.forme_du_titre("Le secret des vide-greniers"), "affirmation")
        self.assertEqual(seo.forme_du_titre("Vinted contre Leboncoin"), "comparaison")
        self.assertEqual(seo.forme_identique_de_suite(["5 a", "7 b", "Combien ?"]), [(1, "liste")])
        self.assertEqual(seo.forme_identique_de_suite(["5 a", "Combien ?", "7 b"]), [])

    def test_relier_au_long(self):
        d = "Accroche\n\n▶ Vidéo complète : 7 machines\n\nSuite"
        self.assertIn("▶ Vidéo complète : https://youtu.be/A", seo.relier_au_long(d, "https://youtu.be/A"))
        self.assertEqual(seo.relier_au_long(d, None), d)


class Validation(unittest.TestCase):
    def pub(self, **kw):
        return {"titre": "Canva gratuit : 4 produits à vendre", "description": "Canva gratuit : quatre produits.\n#Business #Canva #Argent #Idées #Astuces #Freelance #Revenus #Outils",
                "tags": ["canva", "business", "argent"], "contenu_ia": True, **kw}

    def test_titre_de_short_court(self):
        self.assertEqual(valider.controles_publication(self.pub(), court=True), [])
        e = valider.controles_publication(self.pub(titre="x" * 65), court=True)
        self.assertTrue(any("titre de Short" in x for x in e), e)
        self.assertEqual(valider.controles_publication(self.pub(titre="x" * 65), court=False), [])

    def test_plus_de_quinze_hashtags_refuse(self):
        d = "Résumé. " + " ".join(f"#mot{chr(97 + i)}x" for i in range(16))
        e = valider.controles_publication(self.pub(description=d))
        self.assertTrue(any("hashtags" in x and "TOUS" in x for x in e), e)
        d = "Résumé. " + " ".join(f"#mot{chr(97 + i)}x" for i in range(15))
        self.assertEqual(valider.controles_publication(self.pub(description=d)), [])

    def test_avertissements_de_referencement(self):
        av = valider.avertissements_publication(self.pub(description="Texte seul."), court=True)
        self.assertTrue(any("hashtag" in a for a in av))
        self.assertTrue(any("Mots-clés" in a for a in av))
        bon = self.pub(description="Canva gratuit : quatre produits à vendre.\nMots-clés : canva, business\n" + " ".join(f"#mot{i}" for i in range(10)))
        self.assertEqual(valider.avertissements_publication(bon, court=True), [])

    def test_pas_de_mention_d_ia_ni_de_loi_ni_d_avertissement(self):
        phrases = ["Ça rapporte cinquante euros par jour.", "Cette voix est une voix de synthèse.", "Attention à la loi dans ce cas.",
                   "Selon la loi, il faut un statut.", "Ceci n'est pas un conseil financier."]
        e = valider.controles_texte_public(phrases, None)
        self.assertEqual(len(e), 4)
        self.assertFalse(any("phrase 1 " in x for x in e))
        # l'IA comme SUJET d'un business reste permise
        self.assertEqual(valider.controles_texte_public(["Vends des services avec l'IA dès ce soir."], self.pub()), [])
        e = valider.controles_texte_public([], self.pub(description="Voix de synthèse (IA). Merci."))
        self.assertTrue(e and "description" in e[0])

    def test_chapitres_vagues(self):
        ep = {"chapitres": [{"titre": "Accroche"}, {"titre": "Business n°3"}, {"titre": "Vendre des bougies sur Vinted"}, {"titre": "3"}, {"titre": "x" * 70}]}
        av = valider.avertissements_chapitres(ep)
        self.assertEqual(len(av), 4)
        self.assertFalse(any("chapitre 3" in a for a in av))


class Gabarits(unittest.TestCase):
    def scenes(self, *types):
        return [{"type": t, "phrase": i + 1, "params": {}} for i, t in enumerate(types)]

    def test_chaque_gabarit_est_realisable_avec_les_scenes_existantes(self):
        from autopilot.make_short import SCENE_TYPES
        for nom, spec in gabarits.GABARITS.items():
            for t in spec["exige"]:
                self.assertIn(t, SCENE_TYPES, nom)
            for famille, _ in spec["familles"]:
                self.assertTrue(set(famille) <= SCENE_TYPES, nom)

    def test_controle_des_scenes(self):
        ok = {"gabarit": "annonces", "scenes": self.scenes("annonce", "chiffre", "annonce")}
        self.assertEqual(gabarits.controler(ok), ([], []))
        manque = {"gabarit": "annonces", "scenes": self.scenes("annonce", "chiffre")}
        self.assertTrue(gabarits.controler(manque)[0])
        self.assertTrue(gabarits.controler({"gabarit": "inconnu", "scenes": []})[0])
        err, av = gabarits.controler({"scenes": []})
        self.assertEqual(err, [])
        self.assertTrue(av)

    def test_gabarit_clips_demande_un_clip_et_deux_images(self):
        self.assertEqual(gabarits.controler({"gabarit": "clips", "scenes": self.scenes("clip", "chiffre", "photo")})[0], [])
        self.assertTrue(gabarits.controler({"gabarit": "clips", "scenes": self.scenes("photo", "chiffre", "photo")})[0])

    def test_rotation_jamais_deux_fois_de_suite(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(gabarits, "STATE", Path(tmp)):
            sujets_ = [{"id": f"s{i}", "format": "short"} for i in range(12)]
            gabarits.attribuer(sujets_)
            for cle in ("gabarit", "forme_titre", "style_miniature"):
                vals = [s[cle] for s in sujets_]
                self.assertTrue(all(a != b for a, b in zip(vals, vals[1:])), (cle, vals))
            # les 5 gabarits servent tous avant qu'un revienne
            self.assertEqual(len({s["gabarit"] for s in sujets_[:5]}), 5)
            # la suite reprend après le dernier : pas de répétition d'un passage à l'autre
            suite = gabarits.attribuer([{"id": "x", "format": "short"}])
            self.assertNotEqual(suite[0]["gabarit"], sujets_[-1]["gabarit"])

    def test_un_long_n_a_pas_de_gabarit_mais_une_forme_de_titre(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(gabarits, "STATE", Path(tmp)):
            s = gabarits.attribuer([{"id": "l", "format": "long"}])[0]
            self.assertNotIn("gabarit", s)
            self.assertIn(s["forme_titre"], gabarits.FORMES_TITRE)
            self.assertIn(s["style_miniature"], gabarits.STYLES_MINIATURE)

    def test_les_formes_de_titre_attribuees_sont_reconnues_par_seo(self):
        # chaque forme demandée au rédacteur correspond à une forme que le publieur sait reconnaître
        self.assertTrue(set(gabarits.FORMES_TITRE) <= {"liste", "question", "comparaison", "interdit", "affirmation", "chiffre"})


class BancIdees(unittest.TestCase):
    def test_le_score_vient_des_leviers(self):
        self.assertEqual(sujets.score({"leviers": ["objet", "calcul"]}), 40)
        self.assertEqual(sujets.score({"leviers": ["objet"], "score": 5}), 5)
        self.assertEqual(sujets.score({}), 0)

    def test_les_mieux_classes_passent_d_abord_dans_leur_theme(self):
        libres = [{"id": "a", "theme": "T", "score": 10}, {"id": "b", "theme": "T", "score": 70}, {"id": "c", "theme": "T", "score": 40}]
        self.assertEqual([x["id"] for x in sujets.alterner(libres, 3)], ["b", "c", "a"])

    def test_la_banque_de_shorts_est_riche_et_sans_doublon(self):
        shorts = [b for b in sujets.banque() if b["format"] == "short" and b["theme"] != "Business"]
        self.assertGreaterEqual(len(shorts), 50)
        ids = [b["id"] for b in shorts]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len({b["theme"] for b in shorts}), 6)
        self.assertTrue(all(b["score"] > 0 for b in shorts))

    def test_les_sujets_juridiques_sont_ecartes_et_les_angles_nettoyes(self):
        titres = [b["titre"] for b in sujets.banque()]
        self.assertFalse(any("ce que la loi exige" in t for t in titres))
        self.assertTrue(sujets.RE_JURIDIQUE_TITRE.search("10 business : ce que la loi exige"))
        self.assertFalse(sujets.RE_JURIDIQUE_TITRE.search("Vendre des modèles Canva : combien d'achats ?"))
        angles = [b["angle"] for b in sujets.banque() if sujets.RE_JURIDIQUE_ANGLE.search(b["angle"].replace(sujets.NOTE_CAP, ""))]
        self.assertTrue(all(sujets.NOTE_CAP in a for a in angles))

    def test_reapprovisionnement(self):
        with mock.patch.object(sujets, "restants", side_effect=lambda f=None, chaine=None: {"short": 10, "long": 50}.get(f, 60)):
            self.assertTrue(sujets.a_reapprovisionner())
        with mock.patch.object(sujets, "restants", side_effect=lambda f=None, chaine=None: {"short": 80, "long": 20}.get(f, 100)):
            self.assertFalse(sujets.a_reapprovisionner())


if __name__ == "__main__":
    unittest.main()
