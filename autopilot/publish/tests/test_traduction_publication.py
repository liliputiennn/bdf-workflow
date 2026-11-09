"""Publication d'une adaptation : jamais pour une chaîne seulement « en préparation », et jamais avant la version source + le décalage du profil.

    python -m unittest discover -s autopilot/publish/tests      (depuis pixel-faits/)
Faux YouTube local seulement : rien n'est publié pour de vrai.
"""
from datetime import datetime, timedelta, timezone

from test_multichaines import BaseChaines

import common
from quota import maintenant_utc  # noqa: F401


class TestAdaptationEtPublication(BaseChaines):
    def adaptation(self, source_publiee_il_y_a_h=None, active=True):
        """Une chaîne `en` (active ou non) dont l'épisode `ep-en` est l'adaptation de `ep-fr`."""
        self.profils({"fr": {}, "en": {"langue": "en", "voix": {"dossier": "voix/en"}, "preparation": True,
                                        "source": {"chaine": "fr", "mode": "traduction", "decalage_heures": 48},
                                        "publication": {"fuseau": "America/New_York", "heures_shorts": ["09:00"], "shorts_par_creneau": 1}}},
                     actives=("fr", "en") if active else ("fr",))
        src = self.episode_de("fr", "ep-fr")
        if source_publiee_il_y_a_h is None:
            common.set_status(src, "pret")
        else:
            quand = (datetime.now(timezone.utc) - timedelta(hours=source_publiee_il_y_a_h)).isoformat()
            common.set_status(src, "publie", youtube={"video_id": "vid-fr", "url": "https://youtu.be/vid-fr", "visibilite": "public", "publie_a": quand})
        cible = self.episode_de("en", "ep-en")
        common.write_json(common.ep_dir(cible) / "traduction.json", {"source": src, "moteur": "claude"})
        return src, cible

    def test_chaine_en_preparation_n_est_jamais_publiee(self):
        _, cible = self.adaptation(source_publiee_il_y_a_h=100, active=False)
        code, resume = self.lancer_main("--en-attente")
        self.assertEqual(common.get_status(cible)["etat"], "pret")
        self.assertNotIn("en", {r["chaine"] for r in resume["resultats"]})
        self.assertNotIn("refresh-en", {v["refresh"] for v in self.faux.videos.values()})

    def test_la_version_source_non_publiee_retient_l_adaptation(self):
        src, cible = self.adaptation(source_publiee_il_y_a_h=None)
        self.lancer_main("--en-attente")
        self.assertEqual(common.get_status(cible)["etat"], "pret")
        self.assertNotIn("refresh-en", {v["refresh"] for v in self.faux.videos.values()})

    def test_decalage_de_48_heures_apres_la_source(self):
        _, cible = self.adaptation(source_publiee_il_y_a_h=10)
        self.lancer_main("--en-attente")
        self.assertEqual(common.get_status(cible)["etat"], "pret")  # 10 h < 48 h

    def test_apres_le_decalage_l_adaptation_part_a_l_heure_de_new_york(self):
        _, cible = self.adaptation(source_publiee_il_y_a_h=60)
        code, resume = self.lancer_main("--en-attente")
        self.assertEqual(common.get_status(cible)["etat"], "programme", resume)
        self.assertIn("refresh-en", {v["refresh"] for v in self.faux.videos.values()})
