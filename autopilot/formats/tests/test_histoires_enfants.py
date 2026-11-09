"""Format histoires pour enfants : histoire originale et douce, leçon finale, ressemblance entre histoires, voix, rendu court, banque de sujets. Aucun réseau."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from autopilot import chaines
from autopilot.formats import histoires_enfants as h
from autopilot.formats import rendu
from autopilot.formats.tests import faux

RACINE = Path(__file__).resolve().parents[3]
DESC = {"description": "Lila partage ses carottes. Histoire originale pour les enfants de 3 à 7 ans. Voix et images créées avec des outils informatiques.",
        "langue": "fr", "contenu_ia": True}
LECON = "Quand on partage, la joie devient plus grande."


def episode(**plus):
    ep = {"id": "histoires-test", "titre": "Histoire pour enfants : Lila partage ses carottes", "chaine": "Histoires", "theme": "histoire", "video": "short",
          "format_contenu": "histoires_enfants", "pour_enfants": True, "origine": "originale", "lieu": "jardin",
          "situation": "Une petite lapine partage ses carottes avec un hérisson qui a faim.", "lecon": LECON,
          "personnage": {"nom": "Lila", "type": "lapin", "couleur": "gris"}, "ami": {"nom": "Tom", "type": "herisson", "couleur": "brun"},
          "scenes": [
              {"decor": "jardin", "mouvement": "marche", "avec": ["perso"], "phrases": ["Dans un joli jardin, vit une petite lapine qui s'appelle Lila.",
                                                                                        "Ce matin, le soleil brille et Lila trouve trois belles carottes."]},
              {"decor": "jardin", "mouvement": "saute", "avec": ["perso"], "phrases": ["Lila est très contente et elle saute dans l'herbe.",
                                                                                       "Soudain, elle voit Tom le hérisson, assis près d'une fleur."]},
              {"decor": "foret", "phrases": ["Tom a l'air un peu triste.", "Son ventre fait gargouille, gargouille.", "Lila regarde ses carottes, puis elle regarde Tom."]},
              {"decor": "jardin", "mouvement": "balance", "phrases": ["Elle pense un petit moment.", "Puis elle donne une carotte à son ami.", "Tom sourit et dit merci.",
                                                                       "Maintenant, Tom est tout content et ses yeux brillent."]},
              {"decor": "jardin", "phrases": ["Ils croquent les carottes ensemble, sous le beau soleil du matin.", "Lila se sent toute chaude dans son petit coeur.",
                                              "Tom rit et Lila rit aussi, dans le jardin.", LECON]}],
          "miniature": {"texte_haut": "Histoire douce", "gros": "Lila partage"}}
    ep.update(plus)
    return ep


def valider(ep, pub=None, autres=()):
    return h.valider_episode(ep, None, DESC if pub is None else pub, {}, reseau=False, autres=list(autres))


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau, pub=None, autres=()):
        err, _ = valider(ep, pub, autres)
        self.assertTrue(any(morceau in e for e in err), err)

    def phrase(self, texte, scene=1, i=0):
        ep = episode()
        ep["scenes"][scene]["phrases"][i] = texte
        return ep

    def test_episode_valide(self):
        err, av = valider(episode())
        self.assertEqual(err, [], err)

    def test_constantes_du_moteur(self):
        self.assertIs(h.CONTROLES_STANDARD, False)
        self.assertEqual(h.DUREE_S["short"], (30, 55))
        self.assertTrue(h.consignes({}))

    def test_pour_enfants_et_contenu_ia(self):
        self.refuse(episode(pour_enfants=False), "pour_enfants")
        self.refuse(episode(), "contenu_ia", pub={**DESC, "contenu_ia": False})
        self.refuse(episode(), "Histoire originale", pub={**DESC, "description": "Une histoire de lapine."})

    def test_origine_originale_ou_conte_sourcé(self):
        self.refuse(episode(origine="adapté"), "origine")
        self.refuse(episode(origine={"conte": "Le petit tailleur"}), "source")
        self.refuse(episode(origine={"conte": "Le petit tailleur", "source": "http://pas-https.fr/x"}), "source")
        err, av = valider(episode(origine={"conte": "Le petit tailleur", "source": "https://fr.wikisource.org/wiki/Le_Vaillant_Petit_Tailleur"}))
        self.assertEqual(err, [], err)
        self.assertTrue(any("domaine public" in a for a in av))

    def test_conte_classique_seulement_avec_source(self):
        ep = episode()
        ep["scenes"][1]["phrases"][0] = "Lila rencontre Cendrillon près de la fontaine."
        self.refuse(ep, "conte traditionnel")
        ok = {**ep, "origine": {"conte": "Cendrillon", "source": "https://fr.wikisource.org/wiki/Cendrillon"}}
        self.assertEqual(valider(ok)[0], [])

    def test_personnages_et_marques_sous_droits_refuses(self):
        self.refuse(self.phrase("Elle voit Peppa Pig dans le pré."), "droits")
        self.refuse(self.phrase("Elle voit Pikachu dans le pré."), "droits")
        self.refuse(self.phrase("Elle regarde un film de Disney."), "interdit")
        self.refuse(episode(personnage={"nom": "Mickey", "type": "souris", "couleur": "gris"}, titre="Histoire pour enfants : Mickey"), "Mickey")

    def test_douceur_pas_de_peur(self):
        for mot in ("Un grand loup arrive.", "Une sorcière rit fort.", "Il a très peur du noir.", "Un orage gronde au loin.", "Le monstre dort là."):
            self.refuse(self.phrase(mot), "interdit" if "peur" in mot or "monstre" in mot else "effrayer")

    def test_mots_interdits_comme_musique_enfants(self):
        for mot in ("Elle achète un jouet.", "Abonne-toi vite.", "Elle veut gagner de l'argent.", "Il a une arme."):
            err, _ = valider(self.phrase(mot))
            self.assertTrue(err, mot)

    def test_pas_de_chiffres_ni_lien(self):
        self.refuse(self.phrase("Lila a 3 carottes."), "chiffres")
        self.refuse(episode(), "lien", pub={**DESC, "description": DESC["description"] + " https://exemple.com"})
        self.refuse(episode(), "abonne", pub={**DESC, "description": DESC["description"] + " Abonne-toi !"})

    def test_phrases_courtes_et_simples(self):
        self.refuse(self.phrase(" ".join(["petit"] * 16) + "."), "mots")
        self.refuse(self.phrase("Lila (la lapine) saute."), "parenthèses")
        self.refuse(self.phrase("Lila fait de l'anticonstitutionnellement."), "plus de 14 lettres")
        ep = episode()
        ep["scenes"][1]["phrases"] = ["Quelle belle journée !", "Hourra !", "Super !", "Oui !"]
        self.refuse(ep, "exclamation")

    def test_lecon_derniere_phrase(self):
        self.refuse(episode(lecon="Il faut être gentil avec tous ses amis."), "dernière phrase")
        self.refuse(episode(lecon=""), "lecon")
        ep = episode()
        ep["scenes"][-1]["phrases"].append("Et la nuit tombe.")
        self.refuse(ep, "dernière phrase")

    def test_longueur_et_scenes(self):
        ep = episode()
        ep["scenes"] = ep["scenes"][:2] + [{"decor": "jardin", "phrases": [LECON]}]
        self.refuse(ep, "mots")
        ep = episode()
        ep["scenes"] += [copy.deepcopy(ep["scenes"][0]) for _ in range(3)]
        err, _ = valider(ep)
        self.assertTrue(any("scène(s)" in e for e in err) or any("mots" in e for e in err), err)
        self.refuse(episode(video="serie"), "video")

    def test_scenes_et_personnages(self):
        ep = episode()
        ep["scenes"][0]["decor"] = "espace"
        self.refuse(ep, "decor")
        self.refuse(episode(personnage={"nom": "lila", "type": "lapin", "couleur": "gris"}), "personnage.nom")
        self.refuse(episode(personnage={"nom": "Lila", "type": "dragon", "couleur": "gris"}), "personnage.type")
        self.refuse(episode(personnage={"nom": "Lila", "type": "lapin", "couleur": "fluo"}), "couleur")
        self.refuse(episode(ami={"nom": "Tom", "type": "lapin", "couleur": "brun"}), "autre animal")
        self.refuse(episode(lieu="plage"), "lieu")
        ep = episode()
        ep["scenes"][0]["avec"] = ["ami", "fantome"]
        self.refuse(ep, "avec")

    def test_titre_et_miniature(self):
        self.refuse(episode(titre="Lila et ses carottes"), "histoire")
        self.refuse(episode(miniature={"texte_haut": "", "gros": ""}), "miniature")
        self.refuse(episode(titre="Histoire pour enfants : " + "très " * 20 + "longue"), "70")

    def test_deux_histoires_ne_se_ressemblent_pas(self):
        autre = episode(id="autre", titre="Histoire pour enfants : Une autre", personnage={"nom": "Mina", "type": "lapin", "couleur": "blanc"},
                        situation="Une souris aide un ami à ranger sa chambre avant le goûter.", lecon="Autre leçon.")
        self.refuse(episode(), "ressemble", autres=[autre])  # même animal, même lieu
        self.assertEqual(valider(episode(), autres=[{**autre, "lieu": "plage"}])[0], [])
        self.assertIn("même personnage", h.ressemble(episode(), {**autre, "personnage": {"nom": "Lila", "type": "lapin", "couleur": "rose"}, "lieu": "foret"}))
        mem = {**autre, "personnage": {"nom": "Zoé", "type": "chat", "couleur": "bleu"}, "lieu": "maison", "situation": "Une petite lapine partage ses carottes avec un hérisson affamé."}
        self.assertIn("situation", h.ressemble(episode(), mem))
        self.assertIsNone(h.ressemble(episode(), {**autre, "personnage": {"nom": "Zoé", "type": "chat", "couleur": "bleu"}, "lieu": "maison"}))
        self.assertIn("leçon", h.ressemble(episode(), {**autre, "personnage": {"nom": "Zoé", "type": "chat", "couleur": "bleu"}, "lieu": "maison", "lecon": LECON}))

    def test_comparaison_avec_les_histoires_deja_ecrites_sur_disque(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        import os
        os.environ["BDF_ROOT"] = str(tmp)
        try:
            import importlib
            from autopilot import common
            importlib.reload(common)
            d = tmp / "episodes-b" / "histoires-ancienne"
            d.mkdir(parents=True)
            (d / "episode.json").write_text(json.dumps(episode(id="histoires-ancienne", titre="Histoire pour enfants : L'ancienne")), encoding="utf-8")
            (d / "status.json").write_text(json.dumps({"etat": "ecrit", "chaine_id": "histoires-enfants"}), encoding="utf-8")
            err, _ = h.valider_episode(episode(id="histoires-nouvelle"), None, DESC, {"id": "histoires-enfants"}, reseau=False)
            self.assertTrue(any("ressemble" in e for e in err), err)
        finally:
            del os.environ["BDF_ROOT"]
            importlib.reload(common)


class Voix(unittest.TestCase):
    def test_script_voix_lent_avec_pauses_de_scene(self):
        ep = episode()
        s = h.script_voix(ep)
        self.assertEqual(len(s["phrases"]), sum(len(x["phrases"]) for x in ep["scenes"]))
        self.assertEqual(s["phrases"][-1], LECON)
        self.assertTrue(all(0.9 <= v <= 1.0 for v in s["vitesses"].values()))
        debuts = h._debuts_scenes(ep)
        self.assertEqual(debuts[0], 0)
        for i in debuts[1:]:
            self.assertEqual(s["pauses"][str(i + 1)], h.PAUSE_SCENE_S)
        self.assertEqual(s["pauses"]["2"], h.PAUSE_PHRASE_S)

    def test_profil_et_voix_integree(self):
        p = chaines.profil("histoires-enfants")
        self.assertIsNotNone(p)
        self.assertTrue(p["valide"], p.get("erreurs"))
        info = chaines.voix_info(p)
        self.assertEqual(info["mode"], "integree")
        self.assertTrue(info["disponible"])
        v = json.loads((RACINE / "autopilot" / "voix" / "histoires-enfants" / "voix.json").read_text(encoding="utf-8"))
        self.assertTrue(v["a_confirmer"])
        self.assertIn("Apache-2.0", v["licence"])


class Profil(unittest.TestCase):
    def setUp(self):
        self.p = chaines.profil("histoires-enfants")

    def test_inactif_et_pour_enfants(self):
        self.assertIs(self.p["active"], False)
        pub = self.p["publication"]
        self.assertIs(pub["pour_enfants"], True)
        self.assertIs(pub["commentaire_auto"], False)
        self.assertIs(pub["mention_ia_description"], True)
        self.assertEqual(self.p["format"], "histoires_enfants")
        self.assertIn("histoires_enfants", chaines.FORMATS)
        self.assertEqual(self.p["briques"], {"fabrique": "formats/fabrique.py", "miniature": "formats/miniature_formats.py"})
        self.assertIsNotNone(chaines.charger_format(self.p))
        self.assertTrue(self.p["format_statut"]["manque"])
        self.assertTrue(set(pub["jours_longs"]) <= {5, 6})  # le long part le week-end


class Sujets(unittest.TestCase):
    def charger(self):
        dossier = RACINE / "subjects" / "histoires-enfants"
        self.assertTrue(dossier.is_dir())
        out = []
        for f in sorted(dossier.glob("*.json")):
            out += json.loads(f.read_text(encoding="utf-8"))
        return out

    def test_trente_sujets_originaux_et_varies(self):
        s = self.charger()
        self.assertGreaterEqual(len(s), 30)
        titres = [x["titre"] for x in s]
        self.assertEqual(len(set(titres)), len(titres))
        self.assertTrue(all(x["format"] in ("short", "long") for x in s))
        self.assertTrue(any(x["format"] == "long" for x in s) and sum(x["format"] == "short" for x in s) >= 15)
        # personnage + lieu proposés : jamais deux fois la même paire
        paires = [(x["personnage"], x["lieu"]) for x in s]
        self.assertEqual(len(set(paires)), len(paires))
        self.assertTrue(all(x["personnage"] in h.ANIMAUX and x["lieu"] in h.DECORS for x in s))

    def test_sujets_sans_mot_interdit_ni_marque(self):
        for x in self.charger():
            txt = " ".join(str(v) for v in x.values())
            self.assertIsNone(h.RE_MOT_INTERDIT.search(txt), txt)
            self.assertIsNone(h.RE_SOUS_DROITS.search(txt), txt)
            self.assertIsNone(h.RE_EFFRAYANT.search(txt), txt)

    def test_themes_attendus_presents(self):
        t = " ".join(x["theme"] for x in self.charger()).lower()
        for mot in ("amitié", "partage", "courage", "nature", "saisons", "ranger"):
            self.assertIn(mot, t)


class Rendu(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_images_et_sous_titres(self):
        ep = episode()
        tim = faux.fausse_voix(self.tmp, h._phrases(ep), h.script_voix(ep)["pauses"])
        total = tim["total"] + 2
        cal = h._calendrier(ep, tim, total)
        self.assertEqual(len(cal["scenes"]), 5)
        self.assertEqual(cal["scenes"][0], 0.0)
        self.assertTrue(all(a < b for a, b in zip(cal["scenes"], cal["scenes"][1:])))
        r = h._Rendu(ep, cal, 540, 960, total)
        a, b = r.image(1.0), r.image(cal["scenes"][2] + 1.0)
        self.assertEqual(a.size, (540, 960))
        self.assertNotEqual(a.tobytes(), b.tobytes())  # le décor et les personnages changent de scène en scène
        fin = r.image(total - 0.2)
        self.assertEqual(fin.size, (540, 960))

    def test_chaque_personnage_et_chaque_decor_se_dessinent(self):
        for t in h.ANIMAUX:
            sp = h._sprite(t, "orange", 60, False)
            self.assertEqual(sp.size, (300, 300))
            self.assertIsNotNone(sp.getbbox())
            self.assertNotEqual(sp.tobytes(), h._sprite(t, "orange", 60, True).tobytes())  # clignement
        for dec in h.DECORS:
            img = h._fond(dec, 320, 180, 0.7)
            self.assertEqual(img.size, (320, 180))

    def test_miniature(self):
        img = h.miniature(episode(), {})
        self.assertEqual(img.size, (1280, 720))

    def test_rendu_court_de_bout_en_bout(self):
        ep = episode()
        ep_dir, out = self.tmp / "ep", self.tmp / "out"
        ep_dir.mkdir()
        out.mkdir()
        faux.fausse_voix(ep_dir, h._phrases(ep), h.script_voix(ep)["pauses"])
        qa = {}
        final = h.rendre(ep, ep_dir, out, {}, qa, fps=3)
        self.assertTrue(final.exists())
        self.assertGreater(qa["duree_s"], 20)
        self.assertTrue(h.LUFS - 1.5 <= qa["lufs"] <= h.LUFS + 1.5, qa)
        self.assertLess(qa["pic_dbtp"], -0.5)
        self.assertEqual(qa["scenes"], 5)
        self.assertGreater(rendu.duree(final), 20)


if __name__ == "__main__":
    unittest.main()
