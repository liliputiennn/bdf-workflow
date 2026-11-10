"""Tests du moteur « planificateur » (Upload-Post) : faux serveur injecté, aucun réseau réel, aucune vraie clé.
Lancer :  python -m unittest discover -s autopilot/tiktok/tests
"""
import io
import json
import unittest
from contextlib import redirect_stdout

import test_tiktok as T  # noqa: E402
from test_multichaines import profil, short  # noqa: E402

C, common, envoi, TMP = T.C, T.common, T.envoi, T.TMP
import planificateur as PL  # noqa: E402

CLE = "cle-de-test"


class FauxService:
    def __init__(self):
        self.appels = []
        self.statut = {"request_id": "r1", "status": "completed", "results": [{"platform": "tiktok", "success": True, "message": "Published"}]}
        self.code_envoi = 200

    def __call__(self, methode, url, entetes, corps, timeout=60.0):
        self.appels.append((methode, url, dict(entetes), corps))
        if url.endswith("/api/upload"):
            return self.code_envoi, {}, json.dumps({"request_id": "r1"}).encode()
        if "/uploadposts/status" in url:
            return 200, {}, json.dumps(self.statut).encode()
        return 404, {}, b""


def poser_cle():
    d = C.SECRETS
    d.mkdir(parents=True, exist_ok=True)
    (d / "upload_post.json").write_text(json.dumps({"api_key": CLE}), encoding="utf-8")


def retirer_cle():
    (C.SECRETS / "upload_post.json").unlink(missing_ok=True)


class Reglage(unittest.TestCase):
    def test_defaut_inchange(self):
        profil("pl_defaut", {"actif": True})
        r = common.tiktok_reglage("pl_defaut")
        self.assertEqual((r["moteur"], r["mode"]), ("boite", "boite"))

    def test_planificateur_demande_explicite(self):
        profil("pl_a", {"moteur": "planificateur", "planificateur": {"profil": "monprofil"}})
        r = common.tiktok_reglage("pl_a")
        self.assertEqual((r["moteur"], r["mode"], r["planificateur"]["profil"]), ("planificateur", "planificateur", "monprofil"))
        self.assertEqual(r["max_par_24h"], 12)

    def test_valeur_inconnue_retombe_sur_boite(self):
        profil("pl_b", {"moteur": "robot-navigateur"})
        self.assertEqual(common.tiktok_reglage("pl_b")["moteur"], "boite")

    def test_nom_de_fichier_de_cle_refuse_les_chemins(self):
        profil("pl_c", {"moteur": "planificateur", "planificateur": {"cle_fichier": "../x.json"}})
        self.assertEqual(common.tiktok_reglage("pl_c")["planificateur"]["cle_fichier"], "upload_post.json")


class Connecteur(unittest.TestCase):
    def test_publier_envoie_les_bons_champs(self):
        f = FauxService()
        v = TMP / "v.mp4"
        v.write_bytes(b"x" * 500)
        reg = {"visibilite": "PUBLIC_TO_EVERYONE", "ia": True}
        rid = PL.UploadPost(CLE, "prof", f).publier(v, "Titre #a", reg, lambda *_: None)
        self.assertEqual(rid, "r1")
        m, url, ent, corps = f.appels[0]
        self.assertEqual((m, url), ("POST", "https://api.upload-post.com/api/upload"))
        self.assertEqual(ent["Authorization"], f"Apikey {CLE}")
        self.assertTrue(ent["Content-Type"].startswith("multipart/form-data; boundary="))
        for morceau in (b'name="user"\r\n\r\nprof', b'name="platform[]"\r\n\r\ntiktok', b"PUBLIC_TO_EVERYONE", b"DIRECT_POST",
                        b'name="async_upload"\r\n\r\ntrue', b'filename="v.mp4"', b"Titre #a"):
            self.assertIn(morceau, corps)

    def test_plan_gratuit_refuse(self):
        f = FauxService()
        f.code_envoi = 403
        v = TMP / "v2.mp4"
        v.write_bytes(b"x")
        with self.assertRaises(C.ErreurApi) as cm:
            PL.UploadPost(CLE, "p", f).publier(v, "t", {"visibilite": "PUBLIC_TO_EVERYONE"}, lambda *_: None)
        self.assertEqual(cm.exception.code, "plan")

    def test_cle_refusee_demande_de_reconnecter(self):
        f = FauxService()
        f.code_envoi = 401
        v = TMP / "v3.mp4"
        v.write_bytes(b"x")
        with self.assertRaises(C.ErreurAuth):
            PL.UploadPost(CLE, "p", f).publier(v, "t", {"visibilite": "SELF_ONLY"}, lambda *_: None)

    def test_traduction_des_statuts(self):
        self.assertEqual(PL.traduire_statut({"status": "in_progress"})["status"], "PROCESSING_UPLOAD")
        self.assertEqual(PL.traduire_statut({"status": "completed", "results": [{"platform": "tiktok"}]})["status"], "PUBLISH_COMPLETE")
        self.assertEqual(PL.traduire_statut({"status": "completed", "results": [{"platform": "tiktok", "fallback_to_inbox": True}]})["status"],
                         "SEND_TO_USER_INBOX")
        r = PL.traduire_statut({"status": "failed", "results": [{"platform": "tiktok", "message": "tiktok_media_rejected"}]})
        self.assertEqual((r["status"], r["fail_reason"]), ("FAILED", "video_rejected"))
        self.assertEqual(PL.traduire_statut({"status": "failed", "results": []})["fail_reason"], "internal")

    def test_cle_absente(self):
        retirer_cle()
        with self.assertRaises(C.ErreurAuth):
            PL.lire_cle(PL.chemin_cle())


class DeBoutEnBout(unittest.TestCase):
    def setUp(self):
        T_state = common.STATE / "tiktok.json"
        T_state.unlink(missing_ok=True)

    def test_envoi_public_puis_suivi_sans_jeton_tiktok(self):
        profil("pl_e2e", {"moteur": "planificateur", "planificateur": {"profil": "pe"}})
        short("pl_e2e_ep", "pl_e2e")
        poser_cle()
        f = FauxService()
        reg = common.tiktok_reglage("pl_e2e")
        clients, refus, pannes = envoi.clients_pour(["pl_e2e"], charger_client=lambda: self.fail("jeton TikTok inutile"), appel=f)
        self.assertEqual((refus, pannes), ({}, {}))
        with redirect_stdout(io.StringIO()):
            b = envoi.envoyer_file(clients, 4, "pl_e2e_ep", False)
        self.assertEqual(b["envoyes"], ["pl_e2e_ep"])
        e = envoi.lire_etat()["envoyes"]["pl_e2e_ep"]
        self.assertEqual((e["mode"], e["statut"], e["publish_id"]), ("planificateur", "PROCESSING_UPLOAD", "r1"))
        # le suivi passe l'envoi à « publié » et la vidéo peut être libérée
        etat = envoi.lire_etat()
        envoi.mettre_a_jour_statuts(clients, etat)
        envoi.ecrire_etat(etat)
        self.assertEqual(envoi.lire_etat()["envoyes"]["pl_e2e_ep"]["statut"], "PUBLISH_COMPLETE")
        self.assertTrue(common._tiktok_actif("pl_e2e"))
        self.assertTrue(common._tiktok_envoye("pl_e2e_ep"))

    def test_sans_cle_la_chaine_est_a_reconnecter_et_les_autres_continuent(self):
        profil("pl_nokey", {"moteur": "planificateur"})
        retirer_cle()
        clients, refus, _ = envoi.clients_pour(["pl_nokey"], appel=FauxService())
        self.assertEqual(clients, {})
        self.assertIn("pl_nokey", refus)


class FauxZernio:
    def __init__(self):
        self.appels = []
        self.etat = {"post": {"_id": "p9", "status": "published", "platforms": [{"platform": "tiktok", "status": "published"}]}}

    def __call__(self, methode, url, entetes, corps, timeout=60.0):
        self.appels.append((methode, url, dict(entetes), corps))
        if url.endswith("/media/presign"):
            return 200, {}, json.dumps({"uploadUrl": "https://stockage.example/u?sig=1", "publicUrl": "https://media.example/v.mp4"}).encode()
        if url.startswith("https://stockage.example/"):
            return 200, {}, b""
        if methode == "POST" and url.endswith("/posts"):
            return 201, {}, json.dumps({"post": {"_id": "p9", "status": "scheduled"}}).encode()
        if "/posts/p9" in url:
            return 200, {}, json.dumps(self.etat).encode()
        return 404, {}, b""


class MoteurZernio(unittest.TestCase):
    def reg(self, **pl):
        return {"visibilite": "PUBLIC_TO_EVERYONE"}

    def test_reglage_zernio(self):
        profil("zn_a", {"moteur": "planificateur", "planificateur": {"service": "zernio", "compte": "acc1", "consentement": True}})
        p = common.tiktok_reglage("zn_a")["planificateur"]
        self.assertEqual((p["service"], p["cle_fichier"], p["compte"], p["consentement"]), ("zernio", "zernio.json", "acc1", True))

    def test_publier_sequence_et_champs(self):
        f = FauxZernio()
        v = TMP / "z.mp4"
        v.write_bytes(b"x" * 300)
        rid = PL.Zernio("sk_test", "acc1", True, f).publier(v, "Titre", self.reg(), lambda *_: None)
        self.assertEqual(rid, "p9")
        self.assertEqual([(a[0], a[1].split("/")[-1].split("?")[0]) for a in f.appels], [("POST", "presign"), ("PUT", "u"), ("POST", "posts")])
        corps = json.loads(f.appels[2][3])
        self.assertEqual(f.appels[2][2]["Authorization"], "Bearer sk_test")
        self.assertTrue(corps["publishNow"])
        self.assertEqual(corps["mediaItems"][0]["url"], "https://media.example/v.mp4")
        self.assertEqual(corps["platforms"], [{"platform": "tiktok", "accountId": "acc1"}])
        self.assertEqual(corps["tiktokSettings"]["privacy_level"], "PUBLIC_TO_EVERYONE")
        self.assertNotIn("Authorization", f.appels[1][2])  # le dépôt va au stockage, sans la clé

    def test_sans_consentement_rien_ne_part(self):
        f = FauxZernio()
        v = TMP / "z2.mp4"
        v.write_bytes(b"x")
        with self.assertRaises(C.ErreurAuth):
            PL.Zernio("sk", "acc1", False, f).publier(v, "t", self.reg(), lambda *_: None)
        self.assertEqual(f.appels, [])

    def test_sans_compte_rien_ne_part(self):
        f = FauxZernio()
        v = TMP / "z3.mp4"
        v.write_bytes(b"x")
        with self.assertRaises(C.ErreurAuth):
            PL.Zernio("sk", "", True, f).publier(v, "t", self.reg(), lambda *_: None)
        self.assertEqual(f.appels, [])

    def test_statuts(self):
        self.assertEqual(PL.traduire_statut_zernio({"post": {"status": "publishing"}})["status"], "PROCESSING_UPLOAD")
        self.assertEqual(PL.traduire_statut_zernio({"post": {"status": "published"}})["status"], "PUBLISH_COMPLETE")
        self.assertEqual(PL.traduire_statut_zernio({"post": {"status": "scheduled", "platforms": [{"platform": "tiktok", "status": "failed"}]}})["status"], "FAILED")

    def test_cle_refusee(self):
        class Refus(FauxZernio):
            def __call__(self, *a, **k):
                return 401, {}, b"{}"
        v = TMP / "z4.mp4"
        v.write_bytes(b"x")
        with self.assertRaises(C.ErreurAuth):
            PL.Zernio("sk", "a", True, Refus()).publier(v, "t", self.reg(), lambda *_: None)

    def test_de_bout_en_bout_via_envoi(self):
        profil("zn_e2e", {"moteur": "planificateur", "planificateur": {"service": "zernio", "compte": "acc1", "consentement": True}})
        short("zn_e2e_ep", "zn_e2e")
        (C.SECRETS).mkdir(parents=True, exist_ok=True)
        (C.SECRETS / "zernio.json").write_text(json.dumps({"api_key": "sk_t"}), encoding="utf-8")
        envoi.FICHIER_ETAT.unlink(missing_ok=True)
        f = FauxZernio()
        clients, refus, _ = envoi.clients_pour(["zn_e2e"], charger_client=lambda: self.fail("jeton TikTok inutile"), appel=f)
        self.assertEqual(refus, {})
        with redirect_stdout(io.StringIO()):
            b = envoi.envoyer_file(clients, 4, "zn_e2e_ep", False)
        self.assertEqual(b["envoyes"], ["zn_e2e_ep"])
        etat = envoi.lire_etat()
        envoi.mettre_a_jour_statuts(clients, etat)
        self.assertEqual(etat["envoyes"]["zn_e2e_ep"]["statut"], "PUBLISH_COMPLETE")


class Rythme(unittest.TestCase):
    def test_un_seul_envoi_par_creneau(self):
        import calendar
        t = calendar.timegm((2026, 11, 10, 6, 0, 0))  # 07:00 à Paris
        etat = {"envoyes": {}}
        c1 = envoi.prochain_creneau(etat, ["08:30", "12:30"], "fr", lambda: t)
        self.assertEqual(c1, "2026-11-10T08:30:00")
        etat["envoyes"]["a"] = {"chaine": "fr", "programme_pour": c1}
        self.assertEqual(envoi.prochain_creneau(etat, ["08:30", "12:30"], "fr", lambda: t), "2026-11-10T12:30:00")
        etat["envoyes"]["b"] = {"chaine": "fr", "programme_pour": "2026-11-10T12:30:00"}
        self.assertEqual(envoi.prochain_creneau(etat, ["08:30", "12:30"], "fr", lambda: t), "2026-11-11T08:30:00")

    def test_autre_chaine_independante(self):
        import calendar
        t = calendar.timegm((2026, 11, 10, 6, 0, 0))
        etat = {"envoyes": {"a": {"chaine": "fr", "programme_pour": "2026-11-10T08:30:00"}}}
        self.assertEqual(envoi.prochain_creneau(etat, ["08:30"], "quiz", lambda: t), "2026-11-10T08:30:00")

    def test_zernio_programme_au_lieu_de_publier_tout_de_suite(self):
        f = FauxZernio()
        v = TMP / "z5.mp4"
        v.write_bytes(b"x")
        PL.Zernio("sk", "a", True, f).publier(v, "t", {"visibilite": "PUBLIC_TO_EVERYONE"}, lambda *_: None, quand="2026-11-10T18:00:00")
        corps = json.loads(f.appels[2][3])
        self.assertEqual((corps["scheduledFor"], corps["timezone"]), ("2026-11-10T18:00:00", "Europe/Paris"))
        self.assertNotIn("publishNow", corps)

    def test_hashtags_courts_et_utiles(self):
        self.assertEqual(envoi.hashtag("services IA"), "#servicesia")
        self.assertEqual(envoi.hashtag("Éco-pâturage"), "#ecopaturage")
        self.assertIsNone(envoi.hashtag("gagner de l'argent avec l'IA"))
        self.assertIsNone(envoi.hashtag("IA"))


if __name__ == "__main__":
    unittest.main()
