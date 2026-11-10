"""TikTok cloud : clé Zernio dans le workflow, exclusions manuelles fusionnées à la restauration de l'état."""
import json, sys, tempfile, unittest
from pathlib import Path

AP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AP)); sys.path.insert(0, str(AP / "cloud"))
import etat_cloud  # noqa: E402

WF = AP / "cloud" / "github" / "workflows" / "publication.yml"
EXCLUS = ("s2", "s3", "s4", "s10")


class TikTokCloud(unittest.TestCase):
    def test_workflow_utilise_le_secret_zernio_sans_cle_en_dur(self):
        s = WF.read_text(encoding="utf-8")
        self.assertIn("secrets.ZERNIO_API_KEY", s)
        self.assertIn("autopilot/secrets/zernio.json", s)

    def test_exclus_contient_les_quatre_videos(self):
        d = json.loads(etat_cloud.EXCLUS.read_text(encoding="utf-8"))["envoyes"]
        for suf in EXCLUS:
            self.assertIn(f"10-business-a-lancer-avec-moins-de-500-{suf}", d)

    def test_fusion_ne_renvoie_pas_et_respecte_l_existant(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "tiktok.json").write_text(json.dumps({"envoyes": {"x": {"statut": "ok"}}}), encoding="utf-8")
            n = etat_cloud.fusionner_exclus_tiktok(t)
            self.assertEqual(n, 4)
            env = json.loads((t / "tiktok.json").read_text(encoding="utf-8"))["envoyes"]
            self.assertIn("x", env)
            self.assertEqual(len(env), 5)
            self.assertEqual(etat_cloud.fusionner_exclus_tiktok(t), 0)

    def test_fusion_sans_etat_cree_le_fichier(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(etat_cloud.fusionner_exclus_tiktok(Path(t) / "neuf"), 4)


if __name__ == "__main__":
    unittest.main()
