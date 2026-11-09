import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "autopilot"))
import make_short  # noqa: E402


class Types(unittest.TestCase):
    def test_theme_parchemin_connu(self):
        self.assertIn("parchemin", make_short.THEMES)

    def test_nouvelles_scenes_connues(self):
        for t in ("frise", "carte", "citation"):
            self.assertIn(t, make_short.SCENE_TYPES)


if __name__ == "__main__":
    unittest.main()
