import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.writer import sujets  # noqa: E402


def s(i, theme="Ordinaire", prio=0, fmt="short"):
    return {"id": i, "titre": i, "theme": theme, "angle": "", "idee": None, "priorite": prio, "format": fmt}


class Choisir(unittest.TestCase):
    def test_les_prioritaires_passent_en_premier_et_gardent_leur_ordre(self):
        libres = [s("a", "X"), s("p1", "T10", 1), s("p2", "T10", 1), s("p3", "T10", 1), s("b", "Y"), s("p4", "T10", 1)]
        ids = [x["id"] for x in sujets.choisir(libres, 3)]
        self.assertEqual(ids, ["p1", "p2", "p3"])

    def test_une_place_sur_quatre_reste_ordinaire(self):
        libres = [s(f"p{i}", "T10", 1) for i in range(6)] + [s("a", "X"), s("b", "Y")]
        ids = [x["id"] for x in sujets.choisir(libres, 8)]
        self.assertEqual(ids[:4], ["p0", "p1", "p2", ids[3]])
        self.assertIn(ids[3], {"a", "b"})
        self.assertEqual(len(ids), 8)

    def test_sans_ordinaire_ou_sans_prioritaire_on_complete(self):
        self.assertEqual([x["id"] for x in sujets.choisir([s("p1", "T", 1), s("p2", "T", 1)], 4)], ["p1", "p2"])
        self.assertEqual([x["id"] for x in sujets.choisir([s("a", "X"), s("b", "Y")], 4)], ["a", "b"])

    def test_un_seul_long_par_passage(self):
        libres = [s(f"p{i}", "T10", 1, "long") for i in range(5)] + [s("a", "X"), s("b", "Y"), s("c", "Z")]
        ids = [x["id"] for x in sujets.choisir(libres, 4)]
        self.assertEqual(sum(i.startswith("p") for i in ids), 1)
        self.assertEqual(len(ids), 4)
        self.assertEqual(sujets.choisir(libres, 4, max_longs=0)[0]["id"] in {"a", "b", "c"}, True)

    def test_la_banque_donne_le_format_long_aux_top_10(self):
        t10 = [b for b in sujets.banque() if b["theme"] == "Top 10 business"]
        self.assertTrue(t10 and all(b["format"] == "long" for b in t10))

    def test_la_banque_lit_la_priorite(self):
        t10 = [b for b in sujets.banque() if b["theme"] == "Top 10 business"]
        self.assertGreaterEqual(len(t10), 10)
        self.assertTrue(all(b["priorite"] == 1 and b["titre"].startswith("10 ") for b in t10))


if __name__ == "__main__":
    unittest.main()
