"""Tests du publieur YouTube : `python -m unittest discover -s autopilot/publish/tests` depuis pixel-faits/."""
import json
import os
import shutil
import struct
import sys
import tempfile
import time
import unittest
import zlib
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
for p in (ICI, ICI.parent, ICI.parent.parent):
    sys.path.insert(0, str(p))

import auth  # noqa: E402
import common  # noqa: E402
import horaire  # noqa: E402
import publish  # noqa: E402
import reglages  # noqa: E402
import rendre_public  # noqa: E402
from erreurs import ErreurAuth  # noqa: E402
from faux_youtube import FauxYouTube  # noqa: E402
from quota import RegistreQuota  # noqa: E402
from youtube import YouTube  # noqa: E402

MAINTENANT = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)  # 13h à Paris, 4h du matin à Los Angeles


def png(largeur=1280, hauteur=720, remplissage=0) -> bytes:
    def bloc(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d))
    brut = b"".join(b"\x00" + b"\x10\x20\x30" * largeur for _ in range(1))
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(brut)) + bloc(b"IEND", b"") + b"\x00" * remplissage)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(common, "ROOT", self.tmp),
                        mock.patch.object(common, "EPISODES", self.tmp / "episodes-b"),
                        mock.patch.object(common, "EXPORTS", self.tmp / "exports-b"),
                        mock.patch.object(common, "STATE", self.tmp / "autopilot" / "state")]
        for p in self.patches:
            p.start()
        self.faux = FauxYouTube()
        self.cfg = reglages.charger(surcharge={
            "urls": {"api": self.faux.base + "/youtube/v3", "upload": self.faux.base + "/upload/youtube/v3"},
            "chunk_octets": 262144, "reseau": {"tentatives_max": 4, "attente_initiale_s": 0.01}})
        (self.tmp / "autopilot" / "secrets").mkdir(parents=True)
        common.write_json(auth.chemin_client(), {"installed": {
            "client_id": "id-test", "client_secret": "secret-test", "token_uri": self.faux.base + "/token"}})
        self.ecrire_jeton(expiry=time.time() + 3600, access="jeton-initial")
        self.pauses: list[float] = []
        self.quota = RegistreQuota(self.cfg, horloge=lambda: MAINTENANT)
        self.yt = YouTube(auth.Jeton(), self.cfg, self.quota, dormir=self.pauses.append)

    def tearDown(self):
        self.faux.arreter()
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ecrire_jeton(self, expiry, access="vieux"):
        common.write_json(auth.chemin_jeton(), {"access_token": access, "refresh_token": "refresh-test", "expiry": expiry})

    def episode(self, ep_id="ep1", etat="pret", pub=None, taille_video=600_000, miniature=True):
        d = common.ep_dir(ep_id)
        d.mkdir(parents=True)
        common.write_json(d / "episode.json", {"id": ep_id, "titre": "Comment Costco gagne de l'argent", "phrases": ["a", "b", "c"]})
        (common.EXPORTS / ep_id).mkdir(parents=True)
        self.octets_video = os.urandom(taille_video)
        (common.EXPORTS / ep_id / f"{ep_id}.mp4").write_bytes(self.octets_video)
        if miniature:
            (d / "miniature.png").write_bytes(png())
        common.write_json(d / "publication.json", pub or {
            "titre": "Le secret de Costco", "description": "Une explication simple.", "tags": ["business", "costco"],
            "question_commentaires": "Tu as la carte ?", "langue": "fr", "contenu_ia": True})
        common.set_status(ep_id, etat)
        return ep_id

    def publier(self, ep_id="ep1"):
        return publish.publier(ep_id, self.yt, self.cfg, maintenant=lambda: MAINTENANT, afficher=lambda *a: None)


class TestEnvoi(Base):
    def test_envoi_reussi(self):
        ep = self.episode()
        r = self.publier(ep)
        self.assertEqual(r["resultat"], "programme", r)
        st = common.get_status(ep)
        self.assertEqual(st["etat"], "programme")
        self.assertEqual(st["youtube"]["video_id"], "vids1")
        self.assertEqual(st["youtube"]["visibilite"], "programme")
        self.assertEqual(st["youtube"]["publie_a"], "2026-11-02T17:00:00Z")  # 18h à Paris (heure d'hiver)
        v = self.faux.videos["vids1"]
        self.assertEqual(v["octets"], self.octets_video)
        self.assertEqual(v["miniature"], (common.ep_dir(ep) / "miniature.png").read_bytes())
        s, sn = v["status"], v["snippet"]
        self.assertEqual((s["privacyStatus"], s["publishAt"]), ("private", "2026-11-02T17:00:00Z"))
        self.assertIs(s["selfDeclaredMadeForKids"], False)
        self.assertIs(s["containsSyntheticMedia"], False)  # badge IA YouTube désactivé par défaut (badge_ia_youtube) : la mention est dans la description
        self.assertEqual((sn["categoryId"], sn["defaultLanguage"]), ("27", "fr"))
        self.assertIn("Tu as la carte ?", sn["description"])
        reg = self.quota.etat()
        self.assertEqual((reg["envois"], reg["unites"]), (1, 51))  # 1 envoi, miniature 50 + relecture 1
        self.assertFalse((common.ep_dir(ep) / "youtube_upload.json").exists())
        self.assertFalse((common.ep_dir(ep) / ".lock").exists())

    def test_contenu_ia_faux(self):
        ep = self.episode(pub={"titre": "T", "description": "D", "tags": [], "langue": "fr", "contenu_ia": False})
        self.publier(ep)
        self.assertIs(self.faux.videos["vids1"]["status"]["containsSyntheticMedia"], False)

    def test_miniature_manuelle_prioritaire(self):
        ep = self.episode()
        (self.tmp / "miniatures-manuelles").mkdir()
        manuelle = png(remplissage=77)
        (self.tmp / "miniatures-manuelles" / f"{ep}.png").write_bytes(manuelle)
        self.publier(ep)
        self.assertEqual(self.faux.videos["vids1"]["miniature"], manuelle)

    def test_un_creneau_par_jour(self):
        a, b = self.episode("a"), self.episode("b")
        self.publier(a)
        self.publier(b)
        self.assertEqual(common.get_status(a)["youtube"]["publie_a"], "2026-11-02T17:00:00Z")
        self.assertEqual(common.get_status(b)["youtube"]["publie_a"], "2026-11-03T17:00:00Z")

    def test_miniature_refusee_ne_perd_pas_la_video(self):
        ep = self.episode()
        self.faux.miniature_refusee = True
        r = self.publier(ep)
        self.assertEqual(r["resultat"], "programme")
        self.assertIs(common.get_status(ep)["youtube"]["miniature"], False)

    def test_contenu_refuse_par_youtube(self):
        ep = self.episode()
        self.faux.erreur_ouverture = (400, "invalidTitle", "titre refusé")
        r = self.publier(ep)
        st = common.get_status(ep)
        self.assertEqual((r["resultat"], st["etat"]), ("quarantaine", "quarantaine"))
        self.assertIn("invalidTitle", st["raison"])

    def test_panne_serveur_passagere(self):
        ep = self.episode()
        self.faux.pannes_ouverture = 2
        self.assertEqual(self.publier(ep)["resultat"], "programme")
        self.assertEqual(len(self.pauses), 2)
        self.assertGreater(self.pauses[1], self.pauses[0] * 1.2)  # attente exponentielle


class TestQuota(Base):
    def test_plafond_unites_reporte_sans_toucher_au_reseau(self):
        ep = self.episode()
        self.quota.depenser("test", unites=9960)  # il reste 40 < 51
        r = self.publier(ep)
        self.assertEqual(r["resultat"], "reporte")
        self.assertEqual(common.get_status(ep)["etat"], "pret")
        self.assertEqual(self.faux.appels("/upload"), [])

    def test_plafond_envois_reporte(self):
        ep = self.episode()
        self.quota.depenser("test", envois=100)
        self.assertEqual(self.publier(ep)["resultat"], "reporte")
        self.assertEqual(common.get_status(ep)["etat"], "pret")

    def test_remise_a_zero_a_minuit_pacifique(self):
        self.quota.depenser("test", unites=9999, envois=100)
        lendemain = RegistreQuota(self.cfg, horloge=lambda: datetime(2026, 11, 3, 8, 30, tzinfo=timezone.utc))  # 00h30 à LA
        self.assertEqual(lendemain.etat()["unites"], 0)
        encore = RegistreQuota(self.cfg, horloge=lambda: datetime(2026, 11, 3, 7, 30, tzinfo=timezone.utc))  # 23h30 à LA
        self.assertEqual(encore.etat()["unites"], 9999)
        self.assertEqual(self.quota.prochain_essai(), "2026-11-03T08:00:00Z")

    def test_quota_refuse_par_youtube(self):
        ep = self.episode()
        self.faux.quota_ouverture = True
        r = self.publier(ep)
        self.assertEqual(r["resultat"], "reporte")
        self.assertEqual(common.get_status(ep)["etat"], "pret")
        self.assertTrue(self.quota.etat()["epuise"])
        self.assertEqual(self.publier(ep)["resultat"], "reporte")
        self.assertEqual(len(self.faux.appels("/upload/youtube/v3/videos")), 1)  # pas d'insistance


class TestAuth(Base):
    def test_jeton_expire_rafraichi(self):
        self.ecrire_jeton(expiry=time.time() - 10)
        self.assertEqual(self.publier(self.episode())["resultat"], "programme")
        self.assertEqual(self.faux.appels_jeton, 1)
        self.assertEqual(common.read_json(auth.chemin_jeton())["access_token"], "jeton-1")

    def test_401_en_cours_de_route_rafraichit_une_fois(self):
        ep = self.episode()
        self.faux.exiger_jeton_recent = True
        self.faux.jeton_courant = "autre"  # le jeton « jeton-initial » est refusé
        self.assertEqual(self.publier(ep)["resultat"], "programme")
        self.assertGreaterEqual(self.faux.appels_jeton, 1)

    def test_jeton_revoque_leve_erreur_auth_sans_quarantaine(self):
        ep = self.episode()
        self.ecrire_jeton(expiry=0)
        self.faux.refus_jeton = True
        with self.assertRaises(ErreurAuth):
            self.publier(ep)
        self.assertEqual(common.get_status(ep)["etat"], "pret")

    def test_main_ecrit_etat_auth_et_sort_en_3(self):
        ep = self.episode()
        self.ecrire_jeton(expiry=0)
        self.faux.refus_jeton = True
        with mock.patch.object(reglages, "charger", return_value=self.cfg):
            code = publish.main(["--en-attente"])
        self.assertEqual(code, 3)
        self.assertEqual(common.read_json(auth.chemin_etat_auth())["etat"], "a_refaire")
        self.assertEqual(common.get_status(ep)["etat"], "pret")

    def test_absence_de_jeton(self):
        auth.chemin_jeton().unlink()
        with self.assertRaises(ErreurAuth):
            auth.Jeton().acces()


class TestReprise(Base):
    def test_envoi_interrompu_puis_repris(self):
        ep = self.episode(taille_video=900_000)
        self.faux.coupure_au_morceau = 2
        r = self.publier(ep)
        self.assertEqual(r["resultat"], "programme", r)
        self.assertEqual(len(self.faux.sessions), 1)  # même session, pas de recommencement
        self.assertEqual(self.faux.videos["vids1"]["octets"], self.octets_video)
        self.assertGreaterEqual(len(self.pauses), 1)
        self.assertEqual(self.quota.etat()["envois"], 1)  # la reprise ne recompte pas l'envoi

    def test_reprise_apres_arret_du_processus(self):
        ep = self.episode(taille_video=900_000)
        self.faux.coupure_au_morceau = 2
        self.cfg["reseau"]["tentatives_max"] = 1  # la première exécution abandonne
        yt1 = YouTube(auth.Jeton(), self.cfg, self.quota, dormir=lambda s: None)
        r = publish.publier(ep, yt1, self.cfg, maintenant=lambda: MAINTENANT, afficher=lambda *a: None)
        self.assertEqual(r["resultat"], "reseau")
        self.assertEqual(common.get_status(ep)["etat"], "pret")
        self.assertTrue((common.ep_dir(ep) / "youtube_upload.json").exists())
        self.cfg["reseau"]["tentatives_max"] = 4
        self.assertEqual(self.publier(ep)["resultat"], "programme")
        self.assertEqual(len(self.faux.sessions), 1)
        self.assertEqual(self.faux.videos["vids1"]["octets"], self.octets_video)

    def test_reseau_trop_longtemps_coupe_finit_en_quarantaine(self):
        ep = self.episode()
        self.cfg["tentatives_max_avant_quarantaine"] = 2
        self.faux.pannes_ouverture = 999
        self.assertEqual(self.publier(ep)["resultat"], "reseau")
        self.assertEqual(common.get_status(ep)["tentatives"], 1)
        self.assertEqual(self.publier(ep)["resultat"], "quarantaine")


class TestAudit(Base):
    def test_video_forcee_en_prive(self):
        ep = self.episode()
        self.faux.force_prive = True
        r = self.publier(ep)
        st = common.get_status(ep)
        self.assertEqual(r["resultat"], "programme")
        self.assertEqual(st["etat"], "programme")  # surtout pas de quarantaine
        self.assertEqual(st["youtube"]["visibilite"], "prive_force")
        self.assertEqual(st["youtube"]["video_id"], "vids1")
        audit = common.read_json(common.STATE / "youtube_audit.json")
        self.assertEqual(audit["etat"], "non_audite")
        self.assertEqual(audit["constats"][0]["video_id"], "vids1")

    def test_rendre_public_apres_audit(self):
        ep = self.episode()
        self.faux.force_prive = True
        self.publier(ep)
        self.faux.force_prive = False
        self.faux.videos["vids1"]["status"].pop("publishAt", None)
        autre = {"status": {"privacyStatus": "private"}, "snippet": {}}
        self.faux.videos["perso"] = autre  # vidéo hors workflow : à ne pas toucher
        bilan = rendre_public.rendre_public(self.yt, self.cfg, maintenant=lambda: MAINTENANT, afficher=lambda *a: None)
        self.assertEqual(bilan["publiees"], ["vids1"])
        self.assertEqual(bilan["ignorees"], ["perso"])
        self.assertEqual(self.faux.videos["perso"]["status"]["privacyStatus"], "private")
        st = common.get_status(ep)
        self.assertEqual((st["etat"], st["youtube"]["visibilite"]), ("publie", "public"))
        self.assertEqual(common.read_json(common.STATE / "youtube_audit.json")["etat"], "audite")

    def test_rendre_public_sans_audit_signale_le_blocage(self):
        ep = self.episode()
        self.faux.force_prive = True
        self.publier(ep)
        self.faux.maj_ignoree = True
        bilan = rendre_public.rendre_public(self.yt, self.cfg, maintenant=lambda: MAINTENANT, afficher=lambda *a: None)
        self.assertEqual(bilan["toujours_privees"], ["vids1"])
        self.assertEqual(common.get_status(ep)["etat"], "programme")
        self.assertEqual(common.read_json(common.STATE / "youtube_audit.json")["etat"], "non_audite")

    def test_synchronisation_programme_vers_publie(self):
        ep = self.episode()
        self.publier(ep)
        apres = datetime(2026, 11, 2, 17, 5, tzinfo=timezone.utc)
        self.faux.deja_public = True
        res = publish.synchroniser(self.yt, self.cfg, maintenant=lambda: apres, afficher=lambda *a: None)
        self.assertEqual(res[0]["resultat"], "publie")
        self.assertEqual(common.get_status(ep)["etat"], "publie")

    def test_synchronisation_attend_l_heure(self):
        ep = self.episode()
        self.publier(ep)
        self.faux.deja_public = True
        self.assertEqual(publish.synchroniser(self.yt, self.cfg, maintenant=lambda: MAINTENANT), [])
        self.assertEqual(common.get_status(ep)["etat"], "programme")


class TestValidation(Base):
    def test_dry_run_valide_sans_reseau(self):
        ep = self.episode()
        self.faux.arreter()  # tout appel réseau échouerait
        with mock.patch("builtins.print"):
            self.assertEqual(publish.dry_run([ep], self.cfg), 0)

    def test_titre_trop_long_met_en_quarantaine(self):
        ep = self.episode(pub={"titre": "x" * 71, "description": "D", "tags": [], "langue": "fr", "contenu_ia": True})
        pb, _, _ = publish.valider(ep, self.cfg)
        self.assertTrue(any("titre trop long" in p for p in pb))
        r = self.publier(ep)
        self.assertEqual(r["resultat"], "quarantaine")
        self.assertEqual(self.faux.appels("/upload"), [])

    def test_miniature_trop_lourde_et_fichiers_manquants(self):
        ep = self.episode(miniature=False)
        (common.ep_dir(ep) / "miniature.png").write_bytes(png(remplissage=2_200_000))
        self.assertTrue(any("trop lourde" in p for p in publish.valider(ep, self.cfg)[0]))
        (common.ep_dir(ep) / "miniature.png").unlink()
        (common.EXPORTS / ep / f"{ep}.mp4").unlink()
        pb = publish.valider(ep, self.cfg)[0]
        self.assertTrue(any("vidéo absente" in p for p in pb) and any("miniature absente" in p for p in pb))

    def test_signes_interdits_et_exemple(self):
        ep = self.episode(pub={"titre": "a < b", "description": "D", "tags": ["x>y"], "langue": "fr", "contenu_ia": True, "_exemple": True})
        pb = publish.valider(ep, self.cfg)[0]
        self.assertGreaterEqual(len(pb), 3)

    def test_exemple_n_ecrase_pas(self):
        ep = self.episode()
        avant = (common.ep_dir(ep) / "publication.json").read_text(encoding="utf-8")
        publish.creer_exemple(ep)
        self.assertEqual((common.ep_dir(ep) / "publication.json").read_text(encoding="utf-8"), avant)
        autre = self.episode("ep2")
        (common.ep_dir(autre) / "publication.json").unlink()
        publish.creer_exemple(autre)
        self.assertTrue(common.read_json(common.ep_dir(autre) / "publication.json")["_exemple"])

    def test_etat_autre_que_pret_ignore(self):
        ep = self.episode(etat="controle")
        self.assertEqual(self.publier(ep)["resultat"], "ignore")


class TestHoraire(unittest.TestCase):
    def test_decalages(self):
        self.assertEqual(horaire.decalage("Europe/Paris", datetime(2026, 11, 2, tzinfo=timezone.utc)).total_seconds(), 3600)
        self.assertEqual(horaire.decalage("Europe/Paris", datetime(2026, 7, 1, tzinfo=timezone.utc)).total_seconds(), 7200)
        self.assertEqual(horaire.decalage("America/Los_Angeles", datetime(2026, 7, 1, tzinfo=timezone.utc)).total_seconds(), -7 * 3600)
        self.assertEqual(horaire.decalage("America/Los_Angeles", datetime(2026, 11, 3, tzinfo=timezone.utc)).total_seconds(), -8 * 3600)

    def test_creneau_saute_les_jours_pris_et_l_heure_passee(self):
        tard = datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc)  # 18h à Paris : le créneau du jour est trop proche
        c = horaire.prochain_creneau("18:00", "Europe/Paris", tard, set(), 30)
        self.assertEqual(horaire.iso_utc(c), "2026-11-03T17:00:00Z")
        pris = {datetime(2026, 11, 3).date()}
        self.assertEqual(horaire.iso_utc(horaire.prochain_creneau("18:00", "Europe/Paris", tard, pris, 30)), "2026-11-04T17:00:00Z")


class TestFluxOAuth(Base):
    def test_flux_pkce_complet(self):
        """Le « navigateur » est simulé : il suit l'URL d'autorisation et rappelle la redirection locale."""
        import threading
        import urllib.parse
        import urllib.request
        import hashlib, base64

        vu = {}
        faux = self.faux

        def faux_navigateur(url):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
            vu.update(q)

            def rappel():
                urllib.request.urlopen(f"{q['redirect_uri']}/?code=code-test&state={q['state']}").read()
            threading.Thread(target=rappel, daemon=True).start()

        # le faux serveur de jetons accepte aussi authorization_code : on le simule ici
        import faux_youtube
        original = faux_youtube.FauxYouTube
        echange = {}

        def poster(url, champs, timeout=30.0):
            echange.update(champs)
            return 200, {"access_token": "acc", "refresh_token": "ref", "expires_in": 3600}

        with mock.patch.object(auth.webbrowser, "open", faux_navigateur), mock.patch.object(auth, "_poster", poster):
            auth.chemin_jeton().unlink()
            jeton = auth.autoriser(attente_s=10, afficher=lambda *a: None)
        self.assertEqual(vu["code_challenge_method"], "S256")
        self.assertTrue(vu["redirect_uri"].startswith("http://127.0.0.1:"))
        defi = base64.urlsafe_b64encode(hashlib.sha256(echange["code_verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(defi, vu["code_challenge"])  # le vérificateur envoyé correspond au défi PKCE
        self.assertEqual(jeton["refresh_token"], "ref")
        self.assertEqual(common.read_json(auth.chemin_jeton())["refresh_token"], "ref")


if __name__ == "__main__":
    unittest.main()
