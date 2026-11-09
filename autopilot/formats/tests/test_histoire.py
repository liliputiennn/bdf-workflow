import copy
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE))
from autopilot.formats import histoire  # noqa: E402

PROFIL = {"id": "histoire"}


def long_ok():
    ch = lambda titre, n: {"titre": titre, "phrases": [f"Phrase {i} du récit sans nombre." for i in range(n)],
                           "scenes": [{"type": "titre-geant", "phrase": 1, "params": {}}]}
    ep = {"id": "histoire-x", "titre": "Le navire qui a coulé en dix minutes", "theme": "parchemin", "chaine": "Histoire",
          "chapitres": [ch("Le départ", 3), ch("La chute", 3)]}
    faits = [{"claim": "a", "valeur": "1628", "phrase": 2, "sources": ["https://a.org/x", "https://b.org/y"], "check": "1628"},
             {"claim": "b", "valeur": "x", "phrase": 5, "sources": ["https://a.org/x", "https://b.org/y"], "check": "x"}]
    return ep, faits


class Valider(unittest.TestCase):
    def v(self, ep, faits):
        return histoire.valider_episode(ep, faits, None, PROFIL)

    def test_episode_correct(self):
        self.assertEqual(self.v(*long_ok()), ([], []))

    def test_chapitre_sans_fait(self):
        ep, faits = long_ok()
        faits[1]["phrase"] = 1  # plus aucun fait dans le chapitre 2
        err, _ = self.v(ep, faits)
        self.assertTrue(any("chapitre 2" in e and "fait" in e for e in err))

    def test_annee_dans_le_futur(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Tout a changé en 2150 pour eux."
        self.assertTrue(any("2150" in e for e in self.v(ep, faits)[0]))

    def test_dirigeant_apres_1945(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "En 1972 le président a parlé."
        self.assertTrue(any("1945" in e for e in self.v(ep, faits)[0]))

    def test_violence_et_crimes_de_masse(self):
        ep, faits = long_ok()
        ep["chapitres"][1]["phrases"][1] = "Ce fut un massacre."
        self.assertTrue(any("massacre" in e for e in self.v(ep, faits)[0]))

    def test_religion_dans_le_titre(self):
        ep, faits = long_ok()
        ep["titre"] = "La croisade oubliée"
        self.assertTrue(any("religi" in e.lower() for e in self.v(ep, faits)[0]))

    def test_fait_incertain_sans_prudence(self):
        ep, faits = long_ok()
        faits[0]["statut"] = "legende"
        self.assertTrue(any("prudence" in e for e in self.v(ep, faits)[0]))
        ep["chapitres"][0]["phrases"][1] = "Selon la tradition, tout s'est passé ainsi."
        self.assertEqual(self.v(ep, faits)[0], [])

    def test_scenes_neuves(self):
        ep, faits = long_ok()
        sc = ep["chapitres"][0]["scenes"]
        sc.append({"type": "frise", "phrase": 2, "params": {"reperes": [{"date": "1628", "label": "Départ"}]}})
        sc.append({"type": "carte", "phrase": 3, "params": {"lieux": [{"nom": "A", "x": 10, "y": 10}, {"nom": "B", "x": 120, "y": 5}]}})
        sc.append({"type": "citation", "phrase": 3, "params": {"texte": "court", "auteur": ""}})
        err, _ = self.v(ep, faits)
        self.assertTrue(any("frise" in e and "reperes" in e for e in err))
        self.assertTrue(any("carte" in e and "lieux" in e for e in err))
        self.assertTrue(any("citation" in e and "texte" in e for e in err))

    def test_citation_sans_fait(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["scenes"].append({"type": "citation", "phrase": 3, "params": {"texte": "Une phrase assez longue pour passer.", "auteur": "Quelqu'un"}})
        self.assertTrue(any("citation" in e and "source" in e for e in self.v(ep, faits)[0]))

    def test_scenes_valides(self):
        ep, faits = long_ok()
        faits.append({"claim": "c", "valeur": "x", "phrase": 3, "sources": ["https://a.org/x", "https://b.org/y"], "check": "x"})
        sc = ep["chapitres"][0]["scenes"]
        sc.append({"type": "frise", "phrase": 2, "params": {"reperes": [{"date": "1628", "label": "Départ"}, {"date": "1629", "label": "Fin"}]}})
        sc.append({"type": "carte", "phrase": 3, "params": {"lieux": [{"nom": "A", "x": 0, "y": 100}, {"nom": "B", "x": 50.5, "y": 5}]}})
        sc.append({"type": "citation", "phrase": 3, "params": {"texte": "Une phrase assez longue pour passer.", "auteur": "Quelqu'un"}})
        self.assertEqual(self.v(ep, faits), ([], []))

    def test_carte_un_seul_defaut(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["scenes"].append({"type": "carte", "phrase": 3, "params": {"lieux": [{"nom": "A", "x": 10, "y": 10}, {"nom": "B", "x": 120, "y": 5}]}})
        err, _ = self.v(ep, faits)
        self.assertEqual(len(err), 1)
        self.assertIn("lieux", err[0])

    def test_quantites_et_avant_jc_ne_sont_pas_des_annees(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Ils marchent depuis 3000 ans et en 3000 av. J.-C. déjà."
        self.assertEqual(self.v(ep, faits), ([], []))

    def test_dates_avec_mois(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Le 8 mai 1981, le président a parlé."
        self.assertTrue(any("1945" in e for e in self.v(ep, faits)[0]))
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Tout a changé en mai 2150 pour eux."
        self.assertTrue(any("2150" in e for e in self.v(ep, faits)[0]))
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Le navire part le 10 août 1628 et le président du port salue."
        self.assertEqual(self.v(ep, faits), ([], []))
        ep["chapitres"][0]["phrases"][0] = "En mai 3000 pas ils marchent, puis en mai 1628 ils arrivent."
        self.assertEqual(self.v(ep, faits), ([], []))

    def test_frise_label_trop_long(self):
        ep, faits = long_ok()
        long = "x" * 41
        ep["chapitres"][0]["scenes"].append({"type": "frise", "phrase": 1, "params": {"reperes": [{"date": "1628", "label": long}, {"date": "1629", "label": "ok"}]}})
        err, _ = self.v(ep, faits)
        self.assertTrue(any("40" in e for e in err))
        ep["chapitres"][0]["scenes"][-1]["params"]["reperes"][0] = {"date": "d" * 41, "label": "ok"}
        self.assertTrue(any("40" in e for e in self.v(ep, faits)[0]))
        ep["chapitres"][0]["scenes"][-1]["params"]["reperes"][0] = {"date": "1628", "label": "x" * 40}
        self.assertEqual(self.v(ep, faits)[0], [])

    def test_apostrophe_typographique(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Jusqu’en 2100 tout ira bien."
        self.assertTrue(any("2100" in e for e in self.v(ep, faits)[0]))
        ep, faits = long_ok()
        faits[0]["statut"] = "incertain"
        ep["chapitres"][0]["phrases"][1] = "D’après un témoin, c’était ainsi."
        self.assertEqual(self.v(ep, faits)[0], [])

    def test_pluriels_et_titre_de_chapitre(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "En 1990 les ministres se sont réunis."
        self.assertTrue(any("1945" in e for e in self.v(ep, faits)[0]))
        ep, faits = long_ok()
        ep["chapitres"][1]["titre"] = "Les dieux en colère"
        self.assertTrue(any("chapitre 2" in e and "religi" in e for e in self.v(ep, faits)[0]))

    def test_mots_ordinaires_sans_faux_positif(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Il ouvre le papier, dit adieu à la tortue et lit le bibelot."
        ep["titre"] = "Le papier de l'adieu"
        self.assertEqual(self.v(ep, faits), ([], []))

    def test_unites_ne_masquent_pas_les_mots_proches(self):
        for phrase, motif in (("En 1972 Antoine, le président a parlé.", "1945"),
                              ("En 1989 France le gouvernement tomba.", "1945"),
                              ("En 2150 anneaux et bijoux.", "2150"),
                              ("En 2150 avant la fin du monde.", "2150"),
                              ("En 2150 avant que tout change.", "2150")):
            ep, faits = long_ok()
            ep["chapitres"][0]["phrases"][0] = phrase
            self.assertTrue(any(motif in e for e in self.v(ep, faits)[0]), phrase)

    def test_quantites_diverses(self):
        ep, faits = long_ok()
        ep["chapitres"][0]["phrases"][0] = "Il fait 3000 pas, puis en 4000 pieds, avant 5000 hommes, en 3000 avant J.-C. et en 2500 av J.-C."
        self.assertEqual(self.v(ep, faits), ([], []))

    def test_carte_x_bool_nan_inf(self):
        for bad in (True, float("nan"), float("inf"), "10"):
            ep, faits = long_ok()
            ep["chapitres"][0]["scenes"].append({"type": "carte", "phrase": 3, "params": {"lieux": [{"nom": "A", "x": bad, "y": 10}, {"nom": "B", "x": 5, "y": 5}]}})
            self.assertTrue(any("lieux" in e for e in self.v(ep, faits)[0]), bad)

    def test_citation_phrase_non_entiere(self):
        for bad in ("3", None, 2.5):
            ep, faits = long_ok()
            ep["chapitres"][0]["scenes"].append({"type": "citation", "phrase": bad, "params": {"texte": "Une phrase assez longue pour passer.", "auteur": "Q"}})
            try:
                err, _ = self.v(ep, faits)
            except Exception as e:  # noqa: BLE001
                self.fail(f"exception pour {bad!r}: {e!r}")

    def test_consignes(self):
        c = histoire.consignes(PROFIL)
        for mot in ("accroche", "2 sources", "parchemin", "frise", "carte", "citation", "légende"):
            self.assertIn(mot, c)
        self.assertIn('"format": "long"', c)

    def test_short_ignore(self):
        self.assertEqual(histoire.valider_episode({"id": "x", "phrases": ["a"]}, [], None, PROFIL), ([], []))


if __name__ == "__main__":
    unittest.main()
