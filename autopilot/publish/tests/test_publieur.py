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
import seo  # noqa: E402
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

    def test_huit_shorts_par_jour_sur_quatre_creneaux(self):
        """Créneaux 08:00, 12:00, 18:00, 21:00 (Paris) x 2 Shorts espacés de 15 min : les premiers libres après 13h sont 18:00, 18:15, 21:00, 21:15."""
        ids = [self.episode(f"s{i}") for i in range(5)]
        for i in ids:
            self.publier(i)
        pris = [common.get_status(i)["youtube"]["publie_a"] for i in ids]
        self.assertEqual(pris, ["2026-11-02T17:00:00Z", "2026-11-02T17:15:00Z", "2026-11-02T20:00:00Z", "2026-11-02T20:15:00Z",
                                "2026-11-03T07:00:00Z"])
        self.assertEqual(len(set(pris)), 5)

    def test_un_long_part_a_l_heure_des_longs_les_jours_de_longs(self):
        """Le 2 novembre 2026 est un lundi : le long prend 17:00 Paris (16:00 UTC), encore dans le futur à 13h."""
        lg = self.episode("lg")
        common.write_json(common.ep_dir(lg) / "episode-long.json", {"id": lg})
        self.publier(lg)
        self.assertEqual(common.get_status(lg)["youtube"]["publie_a"], "2026-11-02T16:00:00Z")

    def test_un_long_ne_prend_jamais_un_jour_sans_long(self):
        mardi = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(horaire.iso_utc(publish.prochain_creneau_pour(True, self.cfg, mardi, set())), "2026-11-04T16:00:00Z")  # mercredi

    def test_ordre_des_shorts_derives_d_abord_et_en_alternant_les_longs(self):
        for i in ("solo1", "a-s1", "a-s2", "b-s1", "b-s2", "solo2"):
            self.episode(i)
        for i, longue in (("a-s1", "a"), ("a-s2", "a"), ("b-s1", "b"), ("b-s2", "b")):
            common.write_json(common.ep_dir(i) / "origine.json", {"long": longue})
        for longue in ("a", "b"):
            self.episode(longue)
            common.write_json(common.ep_dir(longue) / "episode-long.json", {"id": longue})
        ordre = publish.ordonner_par_rythme(["solo1", "a-s1", "a-s2", "b-s1", "b-s2", "solo2"], self.cfg, maintenant=lambda: MAINTENANT)
        self.assertEqual(ordre, ["a-s1", "b-s1", "a-s2", "b-s2", "solo1", "solo2"])

    def test_long_et_shorts_se_melangent_dans_l_ordre_des_creneaux(self):
        lg = self.episode("lg")
        common.write_json(common.ep_dir(lg) / "episode-long.json", {"id": lg})
        for i in range(3):
            self.episode(f"s{i}")
        ordre = publish.ordonner_par_rythme(["s0", "s1", "s2", "lg"], self.cfg, maintenant=lambda: MAINTENANT)
        self.assertEqual(ordre[0], "lg")  # 17:00 Paris précède 18:00
        self.assertEqual(ordre[1:], ["s0", "s1", "s2"])

    def test_jamais_deux_titres_de_meme_forme_de_suite(self):
        titres = {"a": "5 machines à acheter", "b": "7 business sans stock", "c": "Combien rapporte une presse à chaud ?", "d": "Le secret des pros"}
        for i, t in titres.items():
            self.episode(i, pub={"titre": t, "description": "d", "tags": [], "langue": "fr", "contenu_ia": True})
        ordre = publish.diversifier(["a", "b", "c", "d"])
        formes = [seo.forme_du_titre(titres[i]) for i in ordre]
        self.assertTrue(all(x != y for x, y in zip(formes, formes[1:])), (ordre, formes))
        self.assertEqual(ordre[0], "a")  # le premier de la file ne bouge pas

    def test_jamais_deux_gabarits_identiques_de_suite(self):
        for i, g in (("a", "fiche"), ("b", "fiche"), ("c", "clips")):
            self.episode(i, pub={"titre": f"Titre {i}", "description": "d", "tags": [], "langue": "fr", "contenu_ia": True})
            common.write_json(common.ep_dir(i) / "episode.json", {"id": i, "gabarit": g, "phrases": []})
        self.assertEqual(publish.diversifier(["a", "b", "c"]), ["a", "c", "b"])

    def test_sans_alternative_l_ordre_est_garde(self):
        for i in "abc":
            self.episode(i, pub={"titre": "5 machines", "description": "d", "tags": [], "langue": "fr", "contenu_ia": True})
        self.assertEqual(publish.diversifier(["a", "b", "c"]), ["a", "b", "c"])

    def test_repli_sur_une_seule_heure_sans_heures_shorts(self):
        cfg = reglages.charger(surcharge={"heures_shorts": [], "shorts_par_creneau": 1})
        a = publish.prochain_creneau_pour(False, cfg, MAINTENANT, set())
        b = publish.prochain_creneau_pour(False, cfg, MAINTENANT, {a})
        self.assertEqual((horaire.iso_utc(a), horaire.iso_utc(b)), ("2026-11-02T17:00:00Z", "2026-11-03T17:00:00Z"))

    def test_creneaux_pris_ignorent_la_quarantaine(self):
        a, b = self.episode("a"), self.episode("b")
        self.publier(a)
        self.publier(b)
        common.set_status(b, "quarantaine", "test")
        self.assertEqual(publish.creneaux_pris(self.cfg), {horaire.lire_iso("2026-11-02T17:00:00Z")})

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


class TestCommentaire(Base):
    CADEAU = {"titre": "Messages prêts à envoyer", "messages": ["Bonjour, je lave les voitures à domicile.", "Salut, je monte vos meubles."],
              "suite": "Mardi : le pack entreprises. Abonne-toi pour ne pas le rater."}

    def long(self):
        return self.episode(pub={"titre": "7 business à copier", "description": "Résumé.", "tags": ["a", "b", "c"], "langue": "fr",
                                 "contenu_ia": True, "cadeau": self.CADEAU, "question_commentaires": "Lequel tu testes ?"})

    def synchro(self):
        apres = datetime(2026, 11, 2, 17, 5, tzinfo=timezone.utc)
        return publish.synchroniser(self.yt, self.cfg, maintenant=lambda: apres, afficher=lambda *a: None)

    def test_commentaire_poste_quand_la_video_devient_publique_une_seule_fois(self):
        ep = self.long()
        self.publier(ep)
        self.assertEqual(self.faux.commentaires, [])  # vidéo encore programmée : rien
        self.faux.deja_public = True
        self.synchro()
        self.assertEqual(len(self.faux.commentaires), 1)
        c = self.faux.commentaires[0]
        self.assertEqual(c["video"], "vids1")
        self.assertIn("1. Bonjour, je lave les voitures à domicile.", c["texte"])
        self.assertIn("Abonne-toi pour ne pas le rater.", c["texte"])
        yt = common.get_status(ep)["youtube"]
        self.assertEqual((yt["commentaire_id"], yt["commentaire_a_epingler"]), ("c1", True))
        self.synchro()
        self.assertEqual(len(self.faux.commentaires), 1)  # jamais deux fois

    def test_sans_cadeau_aucun_commentaire(self):
        ep = self.episode()
        self.publier(ep)
        self.faux.deja_public = True
        self.synchro()
        self.assertEqual(self.faux.commentaires, [])
        self.assertNotIn("commentaire_id", common.get_status(ep)["youtube"])

    def test_commentaire_refuse_ne_gene_pas_la_video_puis_nouvel_essai(self):
        ep = self.long()
        self.publier(ep)
        self.faux.deja_public = True
        self.faux.commentaires_refuses = True
        self.synchro()
        st = common.get_status(ep)
        self.assertEqual(st["etat"], "publie")
        self.assertIn("insufficientPermissions", st["youtube"]["commentaire_erreur"])
        self.assertTrue((common.ep_dir(ep) / "commentaire-epingle.txt").exists())  # secours : à coller à la main
        self.faux.commentaires_refuses = False  # connexion refaite
        self.assertTrue(any(r["resultat"] == "commentaire_poste" for r in self.synchro()))
        self.assertEqual(len(self.faux.commentaires), 1)
        self.assertIsNone(common.get_status(ep)["youtube"]["commentaire_erreur"])

    def test_option_desactivee(self):
        ep = self.long()
        self.cfg["commentaire_auto"] = False
        self.publier(ep)
        self.faux.deja_public = True
        self.synchro()
        self.assertEqual(self.faux.commentaires, [])


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


class TestCreneaux(unittest.TestCase):
    def test_etaler_heures(self):
        self.assertEqual(horaire.etaler_heures(["08:00", "12:00"], 2, 15), ["08:00", "08:15", "12:00", "12:15"])
        self.assertEqual(horaire.etaler_heures(["23:50"], 2, 15), ["00:05", "23:50"])
        self.assertEqual(len(horaire.etaler_heures(reglages.DEFAUTS["heures_shorts"], reglages.DEFAUTS["shorts_par_creneau"],
                                                    reglages.DEFAUTS["ecart_creneau_minutes"])), 8)

    def test_creneau_libre_saute_les_heures_prises_et_passees(self):
        tard = datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc)  # 18h à Paris
        heures = ["08:00", "18:00", "21:00"]
        self.assertEqual(horaire.iso_utc(horaire.prochain_creneau_libre(heures, "Europe/Paris", tard, set(), 30)), "2026-11-02T20:00:00Z")
        pris = {datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)}
        self.assertEqual(horaire.iso_utc(horaire.prochain_creneau_libre(heures, "Europe/Paris", tard, pris, 30)), "2026-11-03T07:00:00Z")

    def test_jours_de_la_semaine(self):
        lundi_soir = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)
        c = horaire.prochain_creneau_libre(["17:00"], "Europe/Paris", lundi_soir, set(), 30, {2})  # mercredi
        self.assertEqual(horaire.iso_utc(c), "2026-11-04T16:00:00Z")

    def test_heure_d_ete(self):
        ete = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(horaire.iso_utc(horaire.prochain_creneau_libre(["08:00"], "Europe/Paris", ete, set(), 30)), "2026-07-01T06:00:00Z")

    def test_seize_creneaux_sont_tous_differents(self):
        pris, now = set(), datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
        heures = horaire.etaler_heures(["08:00", "12:00", "18:00", "21:00"], 2, 15)
        for _ in range(16):
            pris.add(horaire.prochain_creneau_libre(heures, "Europe/Paris", now, pris, 30))
        self.assertEqual(len(pris), 16)


class TestReferencement(Base):
    def pub(self, **kw):
        return {"titre": "Graveuse laser : 57 € par jour", "description": "Une graveuse laser peut rapporter du cash.\n\n#Business",
                "tags": ["graveuse laser", "business", "argent", "idée business", "revendre"], "question_commentaires": "Tu en as déjà une ?",
                "langue": "fr", "contenu_ia": True, **kw}

    def test_un_short_recoit_une_dizaine_de_hashtags_et_un_bloc_de_mots_cles(self):
        ep = self.episode("sh")
        d = publish.description_finale(self.pub(), self.cfg, ep)
        h = seo.hashtags_du_texte(d)
        self.assertGreaterEqual(len(h), 8, h)
        self.assertLessEqual(len(h), 15)
        self.assertIn("#Shorts", h)
        self.assertIn("Mots-clés :", d)
        self.assertEqual(h[0], "#Business")  # ceux du rédacteur restent en tête

    def test_jamais_plus_de_quinze_hashtags(self):
        ep = self.episode("sh")
        trop = " ".join(f"#mot{chr(97 + i)}x" for i in range(20))
        d = publish.description_finale(self.pub(description="Résumé. " + trop), self.cfg, ep)
        self.assertLessEqual(len(seo.hashtags_du_texte(d)), 15)

    def test_un_long_n_a_pas_de_shorts_mais_a_ses_hashtags(self):
        ep = self.episode("lg")
        common.write_json(common.ep_dir(ep) / "episode-long.json", {"id": ep})
        d = publish.description_finale(self.pub(), self.cfg, ep)
        self.assertNotIn("#Shorts", d)
        self.assertGreaterEqual(len(seo.hashtags_du_texte(d)), 8)

    def test_chapitres_et_mots_cles_ne_sautent_pas_meme_si_la_description_est_longue(self):
        ep = self.episode("lg")
        common.write_json(common.ep_dir(ep) / "episode-long.json", {"id": ep})
        common.write_json(common.ep_dir(ep) / "chapitres.json", [{"titre": "Intro", "debut_s": 0}, {"titre": "Vendre sur Vinted", "borne_s": 40},
                                                                  {"titre": "Graver du bois", "borne_s": 100}])
        d = publish.description_finale(self.pub(description="Mot. " * 2000), self.cfg, ep)
        self.assertLessEqual(len(d.encode("utf-8")), self.cfg["description_max_octets"])
        self.assertIn("00:40 Vendre sur Vinted", d)
        self.assertIn("Mots-clés :", d)
        self.assertLessEqual(len(seo.hashtags_du_texte(d)), 15)

    def test_un_short_renvoie_vers_l_adresse_du_long_quand_elle_existe(self):
        lg, sh = self.episode("lg"), self.episode("lg-s1")
        common.write_json(common.ep_dir(sh) / "origine.json", {"long": lg})
        desc = "Accroche.\n\n▶ Vidéo complète : 7 machines à acheter"
        d1 = publish.description_finale(self.pub(description=desc), self.cfg, sh)
        self.assertIn("▶ Vidéo complète : 7 machines à acheter", d1)
        common.set_status(lg, "publie", None, youtube={"video_id": "L1", "url": "https://youtu.be/L1"})
        d2 = publish.description_finale(self.pub(description=desc), self.cfg, sh)
        self.assertIn("▶ Vidéo complète : https://youtu.be/L1", d2)

    def test_aucune_mention_d_ia_n_est_ajoutee(self):
        ep = self.episode("sh")
        d = publish.description_finale(self.pub(), self.cfg, ep).lower()
        self.assertNotIn("synthèse", d)
        self.assertIsNone(seo.RE_MENTION_INTERDITE.search(d))


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
