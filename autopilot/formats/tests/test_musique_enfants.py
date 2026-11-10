"""Format musique pour enfants : sécurité des paroles, mélodie originale et chantable, rendu, déclaration « conçu pour les enfants ». Aucun réseau."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from autopilot.formats import musique_enfants as m

RACINE = Path(__file__).resolve().parents[3]
DESC = {"description": "Une petite chanson sur le jardin. Chanson originale à chanter avec les paroles à l'écran.", "langue": "fr"}


def lg(par, notes, r):
    return {"paroles": par, "notes": notes, "rythme": r}


def episode():
    return {"id": "musique-test", "titre": "Chanson du petit jardin pour enfants", "chaine": "Musique", "theme": "musique", "video": "short",
            "format_contenu": "musique_enfants", "pour_enfants": True,
            "chanson": {"tempo": 90, "tonalite": "sol", "instrument": "boite", "ordre": ["c1", "r"], "strophes": {
                "c1": {"lignes": [lg("Le so|leil se lè|ve", [1, 1, 3, 3, 5, 3], [1, 1, 1, 1, 2, 2]), lg("Les fleurs sou|rient au ma|tin", [5, 6, 5, 3, 2, 3, 1], [1, 1, 1, 1, 1, 1, 2]),
                                lg("Les a|beil|les chan|tent", [3, 3, 5, 6, 5, 3], [1, 1, 1, 1, 2, 2]), lg("Zou zou zou, bon|jour", [6, 5, 3, 1, 2], [1, 1, 2, 2, 2])]},
                "r": {"lignes": [lg("Ta|pe des mains tra la la", [1, 3, 5, 3, 1, 5, 3], [1, 1, 1, 1, 1, 1, 2]), lg("Sau|te sau|te dans l'her|be", [5, 6, 5, 3, 2, 1, 3], [1, 1, 1, 1, 1, 1, 2])]}}},
            "miniature": {"texte_haut": "Chanson", "gros": "Le jardin"}}


def valider(ep, pub=None):
    return m.valider_episode(ep, None, DESC if pub is None else pub, {}, reseau=False)


def lignes(ep):
    return [l for s in ep["chanson"]["strophes"].values() for l in s["lignes"]]


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau, pub=None):
        err, _ = valider(ep, pub)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_chanson_valide(self):
        self.assertEqual(valider(episode())[0], [])

    def test_une_note_par_syllabe(self):
        ep = episode()
        ep["chanson"]["strophes"]["c1"]["lignes"][0]["notes"] = [1, 1, 3]
        self.refuse(ep, "une note et une durée par syllabe")

    def test_ligne_de_4_ou_8_temps(self):
        ep = episode()
        ep["chanson"]["strophes"]["c1"]["lignes"][2]["rythme"] = [1, 1, 1, 1, 1, 2]
        self.refuse(ep, "il en faut 4 ou 8")

    def test_chantable(self):
        ep = episode()
        ep["chanson"]["strophes"]["c1"]["lignes"][0]["notes"] = [1, 8, 1, 8, 1, 8]
        self.refuse(ep, "saut de plus de 5 degrés")
        ep = episode()
        ep["chanson"]["strophes"]["r"]["lignes"][0]["notes"] = [1, 3, 5, 3, 1, 5, 12]
        self.refuse(ep, "tessiture")

    def test_melodie_connue_refusee(self):
        ep = episode()  # « Ah ! vous dirai-je, maman » : 1 1 5 5 6 6 5
        ep["chanson"]["strophes"]["r"]["lignes"][0] = lg("Tou|jours tou|jours tou|jours là", [1, 1, 5, 5, 6, 6, 5], [1, 1, 1, 1, 1, 1, 2])
        self.refuse(ep, "ressemble à")
        ep = episode()  # « Frère Jacques » : 1 2 3 1 1 2 3 1
        ep["chanson"]["strophes"]["r"]["lignes"][0] = lg("Lu|ne le so|leil et le vent", [1, 2, 3, 1, 1, 2, 3, 1], [0.5, 0.5, 1, 1, 1, 1, 1, 2])
        self.refuse(ep, "ressemble à")

    def test_mots_interdits_pour_enfants(self):
        ep = episode()
        ep["titre"] = "Chanson du monstre pour enfants"
        self.refuse(ep, "interdit sur une chaîne pour enfants")
        ep = episode()
        ep["chanson"]["strophes"]["c1"]["lignes"][3]["paroles"] = "Zou zou zou, ar|gent"
        self.refuse(ep, "interdit sur une chaîne pour enfants")

    def test_mot_trop_long_et_chiffres(self):
        ep = episode()
        ep["chanson"]["strophes"]["c1"]["lignes"][3] = lg("Zou zou, ex|tra|or|di|naire", [6, 5, 3, 1, 2, 3, 4], [1, 1, 1, 0.5, 0.5, 2, 2])
        self.refuse(ep, "3 syllabes")
        ep = episode()
        ep["titre"] = "Chanson des 3 petits chats pour enfants"
        self.refuse(ep, "pas de chiffres")

    def test_pour_enfants_obligatoire(self):
        ep = episode()
        ep["pour_enfants"] = False
        self.refuse(ep, "pour_enfants")

    def test_durees_et_pauvrete(self):
        ep = episode()
        ep["chanson"]["ordre"] = ["r"]
        self.refuse(ep, "la chanson dure")
        ep = episode()
        ep["chanson"]["tempo"] = 200
        self.refuse(ep, "tempo")

    def test_description_sans_lien_ni_appel(self):
        self.refuse(episode(), "aucun lien", pub={"description": "Chanson originale. Voir https://exemple.com", "langue": "fr"})
        self.refuse(episode(), "interdit", pub={"description": "Chanson originale. Abonne-toi !", "langue": "fr"})
        self.refuse(episode(), "mention", pub={"description": "Une chanson.", "langue": "fr"})

    def test_titre_et_miniature(self):
        ep = episode()
        ep["titre"] = "Le petit jardin"
        self.refuse(ep, "chanson")
        ep = episode()
        del ep["miniature"]
        self.refuse(ep, "miniature")

    def test_forme_illisible(self):
        self.assertTrue(valider({"id": "x"})[0])
        self.assertTrue(m.valider_episode(None, None, None, {})[0])
        ep = episode()
        ep["chanson"]["ordre"] = ["zzz"]
        self.assertTrue(valider(ep)[0])


class Partition(unittest.TestCase):
    def test_calendrier(self):
        ep = episode()
        p = m.partition(ep["chanson"])
        self.assertEqual(len(p["lignes"]), 6)
        self.assertAlmostEqual(p["lignes"][0]["debut"], 4 * 60 / 90)
        self.assertAlmostEqual(p["fin"], m.duree_chanson_s(ep["chanson"]))
        self.assertEqual(m.syllabes("Le pe|tit chat"), [("Le", 0), ("pe", 1), ("tit", 1), ("chat", 2)])

    def test_pas_de_voix(self):
        self.assertEqual(m.script_voix(episode())["phrases"], [])


class Rendu(unittest.TestCase):
    def test_rendu_complet(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-mus-"))
        try:
            qa = {}
            final = m.rendre(episode(), tmp, tmp, {"nom": "Musique (nom à choisir)"}, qa, fps=8)
            self.assertTrue(final.exists())
            self.assertTrue(20 <= qa["duree_s"] <= 60, qa)
            self.assertTrue(-17.5 <= qa["lufs"] <= -14.5, qa)
            self.assertTrue(qa["pour_enfants"])
            self.assertEqual(m.miniature(episode(), {}).size, (1280, 720))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Banque(unittest.TestCase):
    def test_sujets_de_depart(self):
        s = json.loads((RACINE / "subjects" / "musique-enfants" / "00-sujets-de-depart.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s), 25)
        self.assertEqual(len({x["titre"] for x in s}), len(s))
        txt = " ".join(x["titre"] + x.get("angle", "") for x in s)
        self.assertIsNone(m.RE_MOT_INTERDIT.search(txt), m.RE_MOT_INTERDIT.search(txt))  # les sujets eux-mêmes respectent la sécurité enfants


if __name__ == "__main__":
    unittest.main()
