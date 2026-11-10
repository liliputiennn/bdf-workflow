"""Cadence : les vidéos déjà programmées avancent sur la grille serrée ; le total d'envois par jour reste sous le plafond YouTube."""
import sys, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ICI)); sys.path.insert(0, str(ICI.parent))
import publish as P  # noqa: E402
import chaines, reglages  # noqa: E402

MAINT = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)


def faux_etat(eps):
    return mock.patch.multiple(P.common, list_episodes=lambda etat=None, chaine=None: [e for e, st in eps.items() if etat in (None, st["etat"])],
                               get_status=lambda e: eps[e])


class Cadence(unittest.TestCase):
    def test_programmees_une_par_jour_avancent_et_gardent_l_ordre(self):
        cfg = reglages.charger()
        eps = {f"s{i}": {"etat": "programme", "youtube": {"video_id": f"v{i}", "publie_a": f"2026-11-{12 + i}T17:00:00Z"}} for i in range(6)}
        with faux_etat(eps), mock.patch.object(P, "est_long", lambda e: False):
            plan = P.plan_rapprochement(cfg, "fr", MAINT)
        self.assertEqual([p[0] for p in plan], [f"s{i}" for i in range(6)])
        self.assertTrue(all(p[2] < p[1] for p in plan))
        self.assertEqual(len({p[2] for p in plan}), 6)
        self.assertLess(max(p[2] for p in plan), "2026-11-11T23")  # 6 Shorts tiennent en une journée et demie, pas en 6 jours

    def test_ne_repousse_jamais_et_respecte_les_publiees(self):
        cfg = reglages.charger()
        eps = {"a": {"etat": "programme", "youtube": {"video_id": "v", "publie_a": "2026-11-10T11:00:00Z"}},
               "b": {"etat": "publie", "youtube": {"video_id": "w", "publie_a": "2026-11-10T11:30:00Z"}}}
        with faux_etat(eps), mock.patch.object(P, "est_long", lambda e: False):
            self.assertEqual(P.plan_rapprochement(cfg, "fr", MAINT), [])

    def test_quota_total_par_jour_sous_le_plafond(self):
        total = 0
        for f in sorted((ICI.parent / "chaines").glob("*.json")):
            if f.name.startswith("_"):
                continue
            prof = chaines.charger(f.stem) if hasattr(chaines, "charger") else None
            if not prof:
                import json
                prof = json.loads(f.read_text(encoding="utf-8"))
            cfg = reglages.charger_chaine(prof)
            heures, _ = P.heures_du_format(False, cfg)
            total += len(heures) + 1
        self.assertLessEqual(total, 100)
        self.assertLessEqual(2 * reglages.charger()["max_envois_par_execution"], 100)


if __name__ == "__main__":
    unittest.main()
