import copy
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from autopilot.writer import valider  # noqa: E402

DEMO = RACINE / "episodes-b" / "_demo-long" / "episode-long.json"


class Miniature(unittest.TestCase):
    def test_tous_les_styles_sont_acceptes(self):
        for st in ("createur", "telephone", "pile", "chiffre", "question", "contraste"):
            m = {"style": st, "texte_haut": "QUI PAIE VRAIMENT ?", "gros": "0,15 %", "icone": "pieces", "contraste": [{"valeur": "1", "label": "A"}, {"valeur": "2", "label": "B"}]}
            self.assertEqual(valider.controles_miniature(m), [], st)

    def test_style_inconnu_et_champs_manquants(self):
        e = valider.controles_miniature({"style": "arc-en-ciel", "texte_haut": "", "icone": "bateau"})
        self.assertGreaterEqual(len(e), 3)
        self.assertTrue(valider.controles_miniature(None))


class Long(unittest.TestCase):
    @unittest.skipUnless(DEMO.exists(), "démo du format long absente")
    def test_vue_a_plat_et_controles_du_long(self):
        ep = json.loads(DEMO.read_text(encoding="utf-8"))
        ep["theme_accent"] = "chocolat-caramel"
        plat = valider.vue_a_plat(ep)
        self.assertEqual(plat["format"], "long")
        self.assertEqual(plat["theme_accent"], "chocolat-caramel")
        self.assertEqual(len(plat["phrases"]), sum(len(c["phrases"]) for c in ep["chapitres"]))
        err, _, _ = valider.controles_long(copy.deepcopy(ep), [], {"titre": "x"}, reseau=False)
        # la démo est trop courte pour un vrai long : la validation le dit, sans planter
        self.assertTrue(any("6 à 12 minutes" in e or "phrases" in e for e in err), err)
        self.assertTrue(any("faits.json" in e for e in err))

    def test_phrase_trop_longue_en_long(self):
        ep = {"id": "x", "titre": "t", "theme": "chocolat-lait", "chaine": "c", "chapitres": [
            {"titre": "A", "phrases": [" ".join(["mot"] * 30)], "scenes": [{"type": "titre-geant", "phrase": 1, "params": {}}]}]}
        err, _, _ = valider.controles_long(ep, [], {}, reseau=False)
        self.assertTrue(any("30 mots" in e for e in err), err)


class Cadeau(unittest.TestCase):
    MSG = "Bonjour, je fais des planches gravées au laser à partir de vingt euros. Je peux t'en montrer une cette semaine ?"

    def pub(self, n=3, dans_description=True, **extra):
        msgs = [f"{self.MSG} Variante {i}" for i in range(n)]
        suite = "Mardi : les dix messages pour décrocher tes premiers clients en entreprise. Abonne-toi pour ne pas le rater."
        return {"titre": "t", "description": "Résumé.\n" + ("\n".join(msgs) + "\n" + suite if dans_description else ""),
                "cadeau": {"titre": "Messages prêts à envoyer", "messages": msgs, "suite": suite}, **extra}

    def test_cadeau_valide(self):
        self.assertEqual(valider.controles_cadeau(self.pub()), [])

    def test_cadeau_absent(self):
        self.assertTrue(any("cadeau" in e for e in valider.controles_cadeau({"titre": "t", "description": "x"})))

    def test_pas_assez_de_messages(self):
        self.assertTrue(any("au moins" in e for e in valider.controles_cadeau(self.pub(n=2))))

    def test_message_absent_de_la_description(self):
        self.assertTrue(any("description" in e for e in valider.controles_cadeau(self.pub(dans_description=False))))

    def test_message_trop_long_et_titre_manquant(self):
        p = self.pub()
        p["cadeau"]["messages"][0] = "x" * 500
        p["cadeau"]["titre"] = ""
        e = valider.controles_cadeau(p)
        self.assertTrue(any("500 caractères" in x for x in e), e)
        self.assertTrue(any("titre" in x for x in e), e)

    def test_la_suite_donne_la_raison_de_s_abonner(self):
        p = self.pub()
        p["cadeau"]["suite"] = ""
        self.assertTrue(any("suite" in e for e in valider.controles_cadeau(p)))
        p = self.pub()
        p["description"] = p["description"].replace(p["cadeau"]["suite"], "")
        self.assertTrue(any("suite" in e and "description" in e for e in valider.controles_cadeau(p)))

    def test_le_long_exige_le_cadeau(self):
        ep = {"id": "x", "titre": "t", "theme": "chocolat-lait", "chaine": "c", "chapitres": [
            {"titre": "A", "phrases": ["Un deux trois."], "scenes": [{"type": "titre-geant", "phrase": 1, "params": {}}]}]}
        err, _, _ = valider.controles_long(ep, [], {"titre": "t", "description": "d"}, reseau=False)
        self.assertTrue(any("cadeau" in e for e in err), err)


if __name__ == "__main__":
    unittest.main()
