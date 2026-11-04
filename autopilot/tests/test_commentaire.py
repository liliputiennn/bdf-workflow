import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import commentaire  # noqa: E402

PUB = {"question_commentaires": "Lequel tu testes en premier ?",
       "cadeau": {"titre": "Messages prêts à envoyer", "messages": ["Bonjour, je fais des photos produit.", "Salut, je repasse le linge à domicile."],
                  "suite": "Mardi : les dix messages pour décrocher des clients en entreprise. Abonne-toi pour ne pas le rater."}}


class Commentaire(unittest.TestCase):
    def test_contient_messages_suite_et_question(self):
        t = commentaire.texte(PUB)
        self.assertIn("1. Bonjour, je fais des photos produit.", t)
        self.assertIn("2. Salut, je repasse le linge à domicile.", t)
        self.assertIn("Abonne-toi pour ne pas le rater.", t)
        self.assertIn("Lequel tu testes en premier ?", t)

    def test_pas_de_cadeau_pas_de_commentaire(self):
        self.assertIsNone(commentaire.texte({"titre": "t"}))
        self.assertIsNone(commentaire.texte({"cadeau": {"messages": []}}))
        self.assertIsNone(commentaire.texte(None))

    def test_question_par_defaut_et_limite_de_taille(self):
        pub = {"cadeau": {"messages": ["x " * 400] * 30}}
        t = commentaire.texte(pub)
        self.assertLessEqual(len(t), commentaire.MAX_CAR)


if __name__ == "__main__":
    unittest.main()
