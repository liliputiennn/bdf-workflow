"""Garde-fou : tous les profils de chaîne du dépôt doivent être valides (un réglage inconnu rend la chaîne inactive en silence)."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

AP = Path(__file__).resolve().parents[1]
CODE = ("import sys, json; sys.path.insert(0, %r); import chaines; "
        "print(json.dumps({k: v.get('erreurs') for k, v in chaines.charger_profils().items() if not v.get('valide')}))" % str(AP))


class ProfilsReels(unittest.TestCase):
    def test_tous_les_profils_du_depot_sont_valides(self):
        env = {k: v for k, v in os.environ.items() if k != "BDF_ROOT"}
        env["BDF_ROOT"] = str(AP.parent)
        r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True, env=env, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1]), {})


if __name__ == "__main__":
    unittest.main()
