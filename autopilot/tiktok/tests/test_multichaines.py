"""Tests TikTok multi-chaînes (un jeton par compte, choix par chaîne, boîte de réception / publication directe).

Aucun réseau réel, aucun vrai secret : faux serveur TikTok local + dossier temporaire partagé avec test_tiktok.py.
Lancer :  python -m unittest discover -s autopilot/tiktok/tests
"""
import io
import json
import shutil
import sys
import time
import unittest
from contextlib import redirect_stdout

import test_tiktok as T  # noqa: E402  (met en place BDF_ROOT et les chemins de secrets temporaires)

C, common, envoi, TMP = T.C, T.common, T.envoi, T.TMP
sys.path.insert(0, str(T.AUTOPILOT))
import chaines  # noqa: E402


class FauxDirect(T.Faux):
    """Ajoute la publication directe et les réglages du compte au faux serveur."""

    def __init__(self):
        super().__init__()
        self.visibilites = ["SELF_ONLY"]  # compte privé / application non auditée

    def __call__(self, methode, url, entetes, corps, timeout=60.0):
        if url.endswith("/creator_info/query/"):
            self.appels.append((methode, url, dict(entetes), corps))
            return T.reponse(data={"privacy_level_options": self.visibilites, "comment_disabled": False}, error={"code": "ok"})
        if url.endswith("/post/publish/video/init/"):
            self.appels.append((methode, url, dict(entetes), corps))
            return T.reponse(data={"publish_id": "v_direct_9", "upload_url": "https://upload.example/d?y=1"}, error={"code": "ok"})
        return super().__call__(methode, url, entetes, corps, timeout)


def court(**kw):
    return C.TikTok(kw.get("jeton", "j"), appel=kw["appel"], pause=lambda s: None)


def profil(ident, tiktok="absent"):
    d = TMP / "autopilot" / "chaines"
    d.mkdir(parents=True, exist_ok=True)
    p = {"id": ident}
    if tiktok != "absent":
        p["tiktok"] = tiktok
    common.write_json(d / f"{ident}.json", p)


def short(ep, chaine=None, titre="Un titre"):
    d = common.ep_dir(ep)
    d.mkdir(parents=True, exist_ok=True)
    common.write_json(d / "episode.json", {"id": ep, "titre": titre})
    common.set_status(ep, "pret", **({"chaine_id": chaine} if chaine else {}))
    x = common.EXPORTS / ep
    x.mkdir(parents=True, exist_ok=True)
    (x / f"{ep}.mp4").write_bytes(b"v" * 1000)
    common.write_json(x / "qa.json", {"publiable": True})


def envoyer(clients, **kw):
    return envoi.envoyer_file(clients, 4, None, False, afficher=lambda *a: None, **kw)


class MultiChaines(unittest.TestCase):
    def setUp(self):
        for d in ("episodes-b", "exports-b", "exports-tiktok", "autopilot/state", "autopilot/chaines", "autopilot/secrets"):
            shutil.rmtree(TMP / d, ignore_errors=True)
        (TMP / "autopilot" / "state").mkdir(parents=True, exist_ok=True)

    def test_reglage_par_defaut_et_choix_par_chaine(self):
        profil("fr")
        profil("en")
        profil("quiz", True)
        profil("langues", False)
        profil("sommeil", {"actif": True, "jeton_fichier": "tt-sommeil.json", "hashtags": ["#sommeil"]})
        self.assertTrue(common.tiktok_reglage("fr")["actif"])  # la chaîne par défaut garde son envoi
        self.assertFalse(common.tiktok_reglage("en")["actif"])
        self.assertTrue(common.tiktok_reglage("quiz")["actif"])
        self.assertFalse(common.tiktok_reglage("langues")["actif"])
        self.assertEqual(common.tiktok_reglage("fr")["jeton_fichier"], "tiktok_token.json")
        self.assertEqual(common.tiktok_reglage("quiz")["jeton_fichier"], "tiktok_token-quiz.json")
        self.assertEqual(common.tiktok_reglage("sommeil")["jeton_fichier"], "tt-sommeil.json")
        self.assertEqual(common.tiktok_reglage("fr")["hashtags"], ["#business"])
        self.assertEqual(common.tiktok_reglage("quiz")["hashtags"], [])

    def test_nom_de_jeton_dangereux_refuse(self):
        for mauvais in ("../x.json", "tiktok_client.json", "a/b.json"):
            profil("quiz", {"actif": True, "jeton_fichier": mauvais})
            self.assertEqual(common.tiktok_reglage("quiz")["jeton_fichier"], "tiktok_token-quiz.json")

    def test_direct_exige_l_audit_confirme(self):
        profil("quiz", {"mode": "direct"})
        self.assertEqual(common.tiktok_reglage("quiz")["mode"], "boite")
        profil("quiz", {"mode": "direct", "audit_confirme": "oui"})
        self.assertEqual(common.tiktok_reglage("quiz")["mode"], "boite")
        profil("quiz", {"mode": "direct", "audit_confirme": True})
        self.assertEqual(common.tiktok_reglage("quiz")["mode"], "direct")

    def test_profil_valide(self):
        ok = chaines.normaliser({"id": "quiz", "tiktok": {"actif": True, "mode": "boite"}})
        self.assertEqual([e for e in chaines.valider_profil(ok) if "tiktok" in e], [])
        for mauvais in ({"mode": "bizarre"}, {"max_par_24h": 99}, {"jeton_fichier": "../x"}, {"inconnu": 1}, {"audit_confirme": "oui"}):
            p = chaines.normaliser({"id": "quiz", "tiktok": mauvais})
            self.assertTrue([e for e in chaines.valider_profil(p) if "tiktok" in e], mauvais)

    def test_chaque_chaine_envoie_avec_son_jeton_et_sa_limite(self):
        profil("fr")
        profil("quiz", {"actif": True, "max_par_24h": 1})
        profil("en")
        for i in range(2):
            short(f"f{i}")
        for i in range(3):
            short(f"q{i}", "quiz")
        short("e0", "en")  # chaîne qui n'envoie pas
        f_fr, f_quiz = FauxDirect(), FauxDirect()
        bilan = envoyer({"fr": court(jeton="jfr", appel=f_fr), "quiz": court(jeton="jquiz", appel=f_quiz)})
        self.assertEqual(sorted(bilan["envoyes"]), ["f0", "f1", "q0"])
        self.assertEqual(bilan["ignores"], 2)  # q1 et q2 : limite de 1 par 24 h pour ce compte
        auth_quiz = {a[2]["Authorization"] for a in f_quiz.appels if "Authorization" in a[2]}
        auth_fr = {a[2]["Authorization"] for a in f_fr.appels if "Authorization" in a[2]}
        self.assertEqual((auth_quiz, auth_fr), ({"Bearer jquiz"}, {"Bearer jfr"}))
        e = envoi.lire_etat()["envoyes"]
        self.assertEqual((e["q0"]["chaine"], e["q0"]["mode"], e["f0"]["chaine"]), ("quiz", "boite", "fr"))
        self.assertNotIn("e0", e)

    def test_chaine_sans_client_mise_de_cote_sans_bloquer_les_autres(self):
        profil("fr")
        profil("quiz", True)
        short("f0")
        short("q0", "quiz")
        bilan = envoyer({"fr": court(jeton="jfr", appel=FauxDirect())})
        self.assertEqual(bilan["envoyes"], ["f0"])
        self.assertEqual(bilan["sans_client"], ["quiz"])

    def test_sans_audit_confirme_jamais_de_publication_directe(self):
        profil("quiz", {"actif": True, "mode": "direct"})
        short("q0", "quiz")
        f = FauxDirect()
        envoyer({"quiz": court(appel=f)})
        urls = [a[1] for a in f.appels]
        self.assertTrue(any(u.endswith("/inbox/video/init/") for u in urls))
        self.assertFalse(any(u.endswith("/post/publish/video/init/") or u.endswith("/creator_info/query/") for u in urls))

    def test_publication_directe_apres_audit_confirme(self):
        profil("quiz", {"actif": True, "mode": "direct", "audit_confirme": True, "visibilite": "PUBLIC_TO_EVERYONE"})
        short("q0", "quiz", "Une question")
        f = FauxDirect()
        f.visibilites = ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]
        envoyer({"quiz": court(appel=f)})
        init = [a for a in f.appels if a[1].endswith("/post/publish/video/init/")]
        self.assertEqual(len(init), 1)
        info = json.loads(init[0][3])["post_info"]
        self.assertEqual(info["privacy_level"], "PUBLIC_TO_EVERYONE")
        self.assertTrue(info["is_aigc"])
        self.assertTrue(info["title"].startswith("Une question"))
        self.assertEqual(envoi.lire_etat()["envoyes"]["q0"]["mode"], "direct")

    def test_direct_replie_sur_prive_si_le_compte_ne_propose_que_prive(self):
        profil("quiz", {"actif": True, "mode": "direct", "audit_confirme": True})
        short("q0", "quiz")
        f = FauxDirect()  # compte non audité : SELF_ONLY seulement
        envoyer({"quiz": court(appel=f)})
        init = [a for a in f.appels if a[1].endswith("/post/publish/video/init/")]
        self.assertEqual(json.loads(init[0][3])["post_info"]["privacy_level"], "SELF_ONLY")

    def test_main_une_chaine_sans_jeton_n_arrete_pas_les_autres(self):
        profil("fr")
        profil("quiz", True)
        short("f0")
        short("q0", "quiz")
        common.write_json(C.FICHIER_CLIENT, {"client_key": "k", "client_secret": "s"})
        C.ecrire_atomique(C.FICHIER_JETON, {"access_token": "a", "expire_a": time.time() + 7000, "refresh_token": "r",
                                            "refresh_expire_a": time.time() + 9e6})
        faux = FauxDirect()
        avant = C.appel_http
        C.appel_http = faux
        try:
            with redirect_stdout(io.StringIO()) as sortie:
                code = envoi.main([])
        finally:
            C.appel_http = avant
        self.assertEqual(code, 3)  # quiz n'a pas de jeton
        self.assertIn("quiz", sortie.getvalue())
        self.assertIn("f0", envoi.lire_etat()["envoyes"])
        self.assertTrue((TMP / "exports-tiktok" / "q0" / "q0.mp4").exists())  # paquet de secours pour la chaîne à reconnecter
        self.assertFalse((TMP / "exports-tiktok" / "f0").exists())

    def test_jeton_propre_a_chaque_chaine(self):
        profil("quiz", True)
        self.assertFalse(common._tiktok_actif("quiz"))
        C.ecrire_atomique(C.SECRETS / "tiktok_token-quiz.json", {"access_token": "a"})
        self.assertTrue(common._tiktok_actif("quiz"))
        self.assertFalse(common._tiktok_actif("fr"))


if __name__ == "__main__":
    unittest.main()
