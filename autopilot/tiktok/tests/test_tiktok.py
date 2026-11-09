"""Tests du publieur TikTok : aucun accès réseau, dossier temporaire (BDF_ROOT).  Lancer :  python -m unittest discover -s autopilot/tiktok/tests"""
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="bdf-tiktok-"))
os.environ["BDF_ROOT"] = str(TMP)
AUTOPILOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AUTOPILOT))
sys.path.insert(0, str(AUTOPILOT / "tiktok"))

import auth  # noqa: E402
import client as C  # noqa: E402
import common  # noqa: E402
import envoi  # noqa: E402

MO = 1024 * 1024
# Jamais les vrais secrets : tout passe par le dossier temporaire (aucun réseau réel).
C.SECRETS = TMP / "autopilot" / "secrets"
C.FICHIER_CLIENT = C.SECRETS / "tiktok_client.json"
C.FICHIER_JETON = C.SECRETS / "tiktok_token.json"


def reponse(code=200, **corps):
    return code, {}, json.dumps(corps).encode()


class Faux:
    """Faux serveur TikTok : enregistre les appels et rejoue des réponses prévues."""

    def __init__(self, taille_blocs_ok=True):
        self.appels = []
        self.statut = "SEND_TO_USER_INBOX"

    def __call__(self, methode, url, entetes, corps, timeout=60.0):
        self.appels.append((methode, url, dict(entetes), corps))
        if url.endswith("/inbox/video/init/"):
            return reponse(data={"publish_id": "v_pub_123", "upload_url": "https://upload.example/x?y=1"}, error={"code": "ok"})
        if url.startswith("https://upload.example/"):
            deb, fin = entetes["Content-Range"].split(" ")[1].split("/")[0].split("-")
            return (201 if int(fin) + 1 == int(entetes["Content-Range"].split("/")[1]) else 206), {}, b""
        if url.endswith("/status/fetch/"):
            return reponse(data={"status": self.statut}, error={"code": "ok"})
        if url.endswith("/oauth/token/"):
            return reponse(access_token="neuf", expires_in=7200, refresh_token="refresh2", refresh_expires_in=15552000, open_id="o", scope="video.upload", token_type="Bearer")
        return 404, {}, b""


class Blocs(unittest.TestCase):
    def test_petit_fichier_un_seul_bloc(self):
        self.assertEqual(C.plan_blocs(20 * MO), [(0, 20 * MO - 1)])

    def test_gros_fichier_respecte_les_regles_de_tiktok(self):
        t = 300 * MO + 12345
        b = C.plan_blocs(t)
        self.assertLessEqual(len(b), 1000)
        self.assertEqual(b[0][0], 0)
        self.assertEqual(b[-1][1], t - 1)
        for (a1, b1), (a2, _) in zip(b, b[1:]):
            self.assertEqual(b1 + 1, a2)
        for a, f in b[:-1]:
            self.assertTrue(C.BLOC_MIN <= f - a + 1 <= C.BLOC_MAX)
        self.assertLessEqual(b[-1][1] - b[-1][0] + 1, C.BLOC_FINAL_MAX)

    def test_fichier_vide_refuse(self):
        with self.assertRaises(C.ErreurTikTok):
            C.plan_blocs(0)


class Pkce(unittest.TestCase):
    def test_defi_et_url(self):
        v, ch = auth.defi_pkce()
        self.assertEqual(ch, hashlib.sha256(v.encode()).hexdigest())
        self.assertTrue(43 <= len(v) <= 128)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(auth.url_autorisation("CK", "http://127.0.0.1:5000/callback/", "etat", ch)).query))
        self.assertEqual((q["scope"], q["code_challenge_method"], q["response_type"], q["client_key"]), ("video.upload", "S256", "code", "CK"))
        self.assertEqual(q["redirect_uri"], "http://127.0.0.1:5000/callback/")


class Client(unittest.TestCase):
    def test_envoi_dans_la_boite_de_reception(self):
        f = Faux()
        fichier = TMP / "v.mp4"
        fichier.write_bytes(b"x" * (3 * MO))
        pid = C.TikTok("JETON", appel=f).envoyer(fichier, afficher=lambda *a: None)
        self.assertEqual(pid, "v_pub_123")
        init = json.loads(f.appels[0][3])["source_info"]
        self.assertEqual((init["source"], init["video_size"], init["chunk_size"], init["total_chunk_count"]), ("FILE_UPLOAD", 3 * MO, 3 * MO, 1))
        self.assertEqual(f.appels[0][2]["Authorization"], "Bearer JETON")
        put = f.appels[1]
        self.assertEqual(put[0], "PUT")
        self.assertEqual(put[2]["Content-Range"], f"bytes 0-{3 * MO - 1}/{3 * MO}")
        self.assertEqual(put[2]["Content-Type"], "video/mp4")

    def test_erreurs_traduites(self):
        def faux(code, corps):
            return lambda *a, **k: (code, {}, json.dumps(corps).encode())
        with self.assertRaises(C.ErreurAuth):
            C.TikTok("j", appel=faux(401, {"error": {"code": "access_token_invalid"}}))._api("/x", {})
        with self.assertRaises(C.ErreurApi) as cm:
            C.TikTok("j", appel=faux(403, {"error": {"code": "spam_risk_too_many_pending_share", "message": "trop"}}))._api("/x", {})
        self.assertEqual(cm.exception.code, "spam_risk_too_many_pending_share")
        with self.assertRaises(C.ErreurReseau):
            C.TikTok("j", appel=faux(503, {}))._api("/x", {})

    def test_upload_refuse_apres_expiration(self):
        def appel(methode, url, entetes, corps, timeout=60.0):
            if url.endswith("/init/"):
                return reponse(data={"publish_id": "p", "upload_url": "https://u/x"}, error={"code": "ok"})
            return 403, {}, b""
        fichier = TMP / "w.mp4"
        fichier.write_bytes(b"x" * 1000)
        with self.assertRaises(C.ErreurApi):
            C.TikTok("j", appel=appel).envoyer(fichier, afficher=lambda *a: None)

    def test_jeton_renouvele_et_remplace(self):
        chemin = TMP / "tok.json"
        now = time.time()
        C.ecrire_atomique(chemin, {"access_token": "vieux", "expire_a": int(now + 60), "refresh_token": "refresh1", "refresh_expire_a": int(now + 86400 * 100)})
        j = C.jeton_valide({"client_key": "k", "client_secret": "s"}, chemin, appel=Faux())
        self.assertEqual(j, "neuf")
        stocke = json.loads(chemin.read_text(encoding="utf-8"))
        self.assertEqual(stocke["refresh_token"], "refresh2")  # le jeton de renouvellement change à chaque fois
        self.assertGreater(stocke["expire_a"], now + 7000)

    def test_jeton_de_renouvellement_expire(self):
        chemin = TMP / "tok2.json"
        C.ecrire_atomique(chemin, {"access_token": "a", "expire_a": 1, "refresh_token": "r", "refresh_expire_a": 2})
        with self.assertRaises(C.ErreurAuth):
            C.jeton_valide({"client_key": "k", "client_secret": "s"}, chemin, appel=Faux())

    def test_sans_jeton(self):
        with self.assertRaises(C.ErreurAuth):
            C.jeton_valide({"client_key": "k", "client_secret": "s"}, TMP / "absent.json")


def faux_short(ep, etat="pret", publiable=True, long=False, titre="Un titre"):
    d = common.ep_dir(ep)
    d.mkdir(parents=True, exist_ok=True)
    (d / "episode.json").write_text(json.dumps({"id": ep, "titre": titre}), encoding="utf-8")
    (d / "publication.json").write_text(json.dumps({"titre": titre, "tags": ["business", "micro-entreprise"]}), encoding="utf-8")
    if long:
        (d / "episode-long.json").write_text("{}", encoding="utf-8")
    common.set_status(ep, etat)
    x = common.EXPORTS / ep
    x.mkdir(parents=True, exist_ok=True)
    (x / f"{ep}.mp4").write_bytes(b"v" * 1000)
    common.write_json(x / "qa.json", {"publiable": publiable})


class File(unittest.TestCase):
    def setUp(self):
        import shutil
        for d in ("episodes-b", "exports-b", "exports-tiktok", "autopilot/state"):
            shutil.rmtree(TMP / d, ignore_errors=True)
        (TMP / "autopilot" / "state").mkdir(parents=True, exist_ok=True)

    def test_eligibilite(self):
        faux_short("ok")
        faux_short("pas-pret", etat="ecrit")
        faux_short("non-publiable", publiable=False)
        faux_short("un-long", long=True)
        self.assertEqual(envoi.candidats({}), ["ok"])

    def test_legende(self):
        faux_short("a", titre="Revendre : quand le fisc est prévenu")
        t = envoi.legende("a")
        self.assertTrue(t.startswith("Revendre : quand le fisc est prévenu"))
        self.assertIn("#Business", t)
        self.assertIn("#MicroEntreprise", t)
        self.assertEqual(t.lower().count("#business"), 1)

    def test_quatre_envois_par_24_heures_et_pas_de_doublon(self):
        for i in range(7):
            faux_short(f"s{i}")
        f = Faux()
        bilan = envoi.envoyer_file(C.TikTok("j", appel=f, pause=lambda s: None), 4, None, False, afficher=lambda *a: None)
        self.assertEqual(len(bilan["envoyes"]), 4)
        self.assertEqual(bilan["ignores"], 3)
        bilan2 = envoi.envoyer_file(C.TikTok("j", appel=f, pause=lambda s: None), 4, None, False, afficher=lambda *a: None)
        self.assertEqual(bilan2["envoyes"], [])  # déjà 4 en 24 h
        self.assertEqual(len(envoi.lire_etat()["envoyes"]), 4)

    def test_dry_run_n_envoie_rien(self):
        faux_short("a")
        f = Faux()
        bilan = envoi.envoyer_file(C.TikTok("j", appel=f), 4, None, True, afficher=lambda *a: None)
        self.assertEqual(bilan["envoyes"], ["a"])
        self.assertEqual(f.appels, [])
        self.assertEqual(envoi.lire_etat()["envoyes"], {})

    def test_statut_mis_a_jour_et_echec_temporaire_rejoue(self):
        faux_short("a")
        f = Faux()
        tt = C.TikTok("j", appel=f, pause=lambda s: None)
        envoi.envoyer_file(tt, 4, None, False, afficher=lambda *a: None)
        self.assertEqual(envoi.lire_etat()["envoyes"]["a"]["statut"], "PROCESSING_UPLOAD")
        envoi.envoyer_file(tt, 4, None, False, afficher=lambda *a: None)
        self.assertEqual(envoi.lire_etat()["envoyes"]["a"]["statut"], "SEND_TO_USER_INBOX")
        f.statut = "PUBLISH_COMPLETE"
        envoi.envoyer_file(tt, 4, None, False, afficher=lambda *a: None)
        self.assertEqual(envoi.lire_etat()["envoyes"]["a"]["statut"], "PUBLISH_COMPLETE")

    def test_paquet_de_secours_sans_jeton(self):
        faux_short("a", titre="Mon titre")
        from contextlib import redirect_stdout
        import io
        with redirect_stdout(io.StringIO()) as sortie:
            code = envoi.main([])
        self.assertEqual(code, 3)  # connexion TikTok à refaire
        d = TMP / "exports-tiktok" / "a"
        self.assertTrue((d / "a.mp4").exists())
        self.assertIn("Mon titre", (d / "legende.txt").read_text(encoding="utf-8"))
        self.assertIn("auth", json.loads(sortie.getvalue()))


if __name__ == "__main__":
    unittest.main()
