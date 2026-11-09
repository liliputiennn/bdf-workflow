"""Libération du disque après publication (common.liberer_disque)."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _charger(racine: Path):
    os.environ["BDF_ROOT"] = str(racine)
    from autopilot import common
    return importlib.reload(common)


class LibererDisque(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = _charger(Path(self.tmp.name))

    def tearDown(self):
        os.environ.pop("BDF_ROOT", None)
        importlib.reload(self.c)
        self.tmp.cleanup()

    def _episode(self, ep, long=False):
        d = self.c.ep_dir(ep)
        d.mkdir(parents=True)
        (d / "episode.json").write_text("{}", encoding="utf-8")
        (d / "publication.json").write_text("{}", encoding="utf-8")
        (d / "voice.wav").write_bytes(b"x" * 10)
        (d / "cache").mkdir()
        (d / "cache" / "a.wav").write_bytes(b"x")
        if long:
            (d / "episode-long.json").write_text("{}", encoding="utf-8")
        x = self.c.EXPORTS / ep
        x.mkdir(parents=True)
        (x / f"{ep}.mp4").write_bytes(b"x" * 10)
        (x / "qa.json").write_text("{}", encoding="utf-8")
        (x / "miniature.jpg").write_bytes(b"x")
        return d, x

    def test_court_publie_supprime_le_lourd_garde_le_reste(self):
        d, x = self._episode("a")
        self.c.set_status("a", "publie", None, youtube={"video_id": "v", "url": "u", "visibilite": "public", "publie_a": None})
        self.assertFalse((x / "a.mp4").exists())
        self.assertFalse((d / "voice.wav").exists())
        self.assertFalse((d / "cache").exists())
        self.assertTrue((d / "publication.json").exists() and (x / "qa.json").exists() and (x / "miniature.jpg").exists())

    def test_rien_sans_identifiant_youtube(self):
        d, x = self._episode("b")
        self.c.set_status("b", "publie")
        self.assertTrue((x / "b.mp4").exists())

    def test_rien_si_pas_publie(self):
        d, x = self._episode("c")
        self.c.set_status("c", "programme", None, youtube={"video_id": "v"})
        self.assertTrue((x / "c.mp4").exists())

    def test_short_attend_tiktok_si_configure(self):
        d, x = self._episode("s1")
        sec = self.c.ROOT / "autopilot" / "secrets"
        sec.mkdir(parents=True)
        (sec / "tiktok_token.json").write_text("{}", encoding="utf-8")
        self.c.set_status("s1", "publie", None, youtube={"video_id": "v"})
        self.assertTrue((x / "s1.mp4").exists())
        self.c.write_json(self.c.STATE / "tiktok.json", {"envoyes": {"s1": {"statut": "SEND_TO_USER_INBOX"}}})
        self.assertTrue(self.c.liberer_tout_publie())
        self.assertFalse((x / "s1.mp4").exists())

    def test_long_attend_le_decoupage_des_shorts(self):
        d, x = self._episode("L", long=True)
        (x / "qa.json").write_text(json.dumps({"shorts": ["L-s1"]}), encoding="utf-8")
        self.c.set_status("L", "publie", None, youtube={"video_id": "v"})
        self.assertTrue((x / "L.mp4").exists())  # le Short n'existe pas encore
        s = self.c.ep_dir("L-s1")
        s.mkdir(parents=True)
        (s / "voice.wav").write_bytes(b"x")
        self.assertTrue(self.c.liberer_disque("L"))
        self.assertFalse((x / "L.mp4").exists())


if __name__ == "__main__":
    unittest.main()
