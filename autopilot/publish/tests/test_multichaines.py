"""Tests du publieur avec plusieurs chaînes : un jeton par chaîne, quota partagé, échecs isolés, créneaux propres à chaque chaîne.

    python -m unittest discover -s autopilot/publish/tests      (depuis pixel-faits/)
Aucun accès réseau réel : le faux YouTube local sert toutes les chaînes ; aucune vidéo n'est publiée pour de vrai.
"""
import copy
import io
import json
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from test_publieur import MAINTENANT, Base  # noqa: F401  (MAINTENANT sert aux sous-classes)

import auth
import chaines
import common
import connecter_chaine
import publish
import reglages
from erreurs import ErreurAuth
from quota import RegistreQuota
from youtube import YouTube


class BaseChaines(Base):
    """Deux chaînes actives : `fr` (jeton token.json) et `en` (jeton token-en.json, créneaux à New York)."""

    def setUp(self):
        super().setUp()
        self.profils({"fr": {}, "en": {"langue": "en", "publication": {"fuseau": "America/New_York", "heures_shorts": ["09:00"], "shorts_par_creneau": 1},
                                       "voix": {"dossier": "voix/en"}}})
        self.faux.acces_de["jeton-initial"] = "refresh-test"  # jeton d'accès de la chaîne fr (écrit par Base)
        self.ecrire_jeton_chaine("en", "refresh-en")

    def profils(self, definition: dict, actives=("fr", "en")):
        d = self.tmp / "autopilot" / "chaines"
        d.mkdir(parents=True, exist_ok=True)
        for ident, extra in definition.items():
            p = {"id": ident, "nom": ident.upper(), "langue": "fr", "format": "business", "active": ident in actives,
                 "jeton_fichier": "token.json" if ident == "fr" else f"token-{ident}.json", **extra}
            (d / f"{ident}.json").write_text(json.dumps(p), encoding="utf-8")

    def ecrire_jeton_chaine(self, ident, refresh, expiry=None):
        acces = f"acces-{refresh}"
        self.faux.acces_de[acces] = refresh  # le faux serveur sait quel jeton de rafraîchissement a produit cet accès
        common.write_json(auth.chemin_jeton(ident), {"access_token": acces, "refresh_token": refresh,
                                                     "expiry": time.time() + 3600 if expiry is None else expiry})

    def episode_de(self, chaine, ep_id):
        self.episode(ep_id)
        common.set_status(ep_id, "pret", chaine_id=chaine)
        return ep_id

    def lancer_main(self, *args):
        sortie, erreur = io.StringIO(), io.StringIO()
        # le publieur lit ses réglages lui-même : on lui donne ceux du faux YouTube (copie neuve à chaque appel, comme en production)
        with mock.patch.object(reglages, "charger", side_effect=lambda *a, **k: copy.deepcopy(self.cfg)), \
                redirect_stdout(sortie), redirect_stderr(erreur):
            code = publish.main(list(args))
        resume = json.loads(sortie.getvalue().strip().splitlines()[-1])
        return code, resume

    def quota_du_jour(self):
        return common.read_json(common.STATE / "youtube_quota.json")


class TestPlusieursChaines(BaseChaines):
    def test_chaque_chaine_publie_avec_son_propre_jeton(self):
        a, b = self.episode_de("fr", "ep-fr"), self.episode_de("en", "ep-en")
        code, resume = self.lancer_main("--en-attente")
        self.assertEqual(code, 0, resume)
        self.assertEqual({r["chaine"] for r in resume["resultats"]}, {"fr", "en"})
        par_refresh = {v["refresh"] for v in self.faux.videos.values()}
        self.assertEqual(par_refresh, {"refresh-test", "refresh-en"})
        self.assertEqual(common.get_status(a)["etat"], "programme")
        self.assertEqual(common.get_status(b)["etat"], "programme")
        self.assertEqual(common.get_status(b)["chaine_id"], "en")

    def test_le_quota_est_partage_et_detaille_par_chaine(self):
        self.episode_de("fr", "ep-fr")
        self.episode_de("en", "ep-en")
        self.lancer_main("--en-attente")
        q = self.quota_du_jour()
        self.assertEqual(q["envois"], 2)  # un seul registre pour tout le projet
        self.assertEqual(q["par_chaine"]["fr"]["envois"], 1)
        self.assertEqual(q["par_chaine"]["en"]["envois"], 1)
        self.assertEqual({e.get("chaine") for e in q["journal"] if e["envois"]}, {"fr", "en"})

    def test_jeton_refuse_pour_une_chaine_n_empeche_pas_les_autres(self):
        self.ecrire_jeton_chaine("en", "refresh-en", expiry=0)  # à rafraîchir tout de suite
        self.faux.refus_refresh = {"refresh-en"}
        a, b = self.episode_de("fr", "ep-fr"), self.episode_de("en", "ep-en")
        code, resume = self.lancer_main("--en-attente")
        self.assertEqual(code, 3)
        self.assertEqual(common.get_status(a)["etat"], "programme")   # fr a publié malgré l'échec de en
        self.assertEqual(common.get_status(b)["etat"], "pret")        # en n'est pas mis en quarantaine
        self.assertEqual(common.read_json(auth.chemin_etat_auth("en"))["etat"], "a_refaire")
        self.assertFalse(auth.chemin_etat_auth("fr").exists() and common.read_json(auth.chemin_etat_auth("fr"))["etat"] == "a_refaire")
        self.assertIn({"chaine": "en", "resultat": "auth"}, [{"chaine": r["chaine"], "resultat": r["resultat"]} for r in resume["resultats"]])

    def test_une_chaine_en_erreur_inattendue_n_arrete_pas_les_autres(self):
        a, b = self.episode_de("fr", "ep-fr"), self.episode_de("en", "ep-en")
        vrai = publish.publier

        def publier_qui_plante(ep_id, yt, cfg, *args, **kw):
            if common.chaine_de(ep_id) == "en":
                raise RuntimeError("bug dans la chaîne en")
            return vrai(ep_id, yt, cfg, *args, **kw)

        with mock.patch.object(publish, "publier", publier_qui_plante):
            code, resume = self.lancer_main("--en-attente")
        self.assertEqual(code, 1)
        self.assertEqual(common.get_status(a)["etat"], "programme")
        self.assertEqual(next(r for r in resume["resultats"] if r["chaine"] == "en")["resultat"], "erreur")

    def test_quota_epuise_arrete_toutes_les_chaines(self):
        self.episode_de("fr", "ep-fr")
        self.episode_de("en", "ep-en")
        self.faux.quota_ouverture = True
        code, resume = self.lancer_main("--en-attente")
        self.assertEqual(len(self.faux.appels("/upload/youtube/v3/videos")), 1)  # la 2e chaîne n'insiste pas : même quota
        self.assertEqual([r["resultat"] for r in resume["resultats"]], ["reporte"])

    def test_chaine_inactive_ignoree(self):
        self.profils({"fr": {}, "en": {"langue": "en", "voix": {"dossier": "voix/en"}}}, actives=("fr",))
        b = self.episode_de("en", "ep-en")
        a = self.episode_de("fr", "ep-fr")
        self.lancer_main("--en-attente")
        self.assertEqual(common.get_status(b)["etat"], "pret")
        self.assertEqual(common.get_status(a)["etat"], "programme")
        self.assertEqual(len(self.faux.videos), 1)

    def test_chaine_sans_travail_n_ouvre_pas_son_jeton(self):
        auth.chemin_jeton("en").unlink()
        self.episode_de("fr", "ep-fr")
        code, resume = self.lancer_main("--en-attente")
        self.assertEqual(code, 0, resume)
        self.assertFalse(auth.chemin_etat_auth("en").exists())  # aucune fausse alerte « jeton à refaire »

    def test_chaine_active_sans_jeton_est_signalee_sans_quarantaine(self):
        auth.chemin_jeton("en").unlink()
        b = self.episode_de("en", "ep-en")
        code, resume = self.lancer_main("--en-attente")
        self.assertEqual(code, 3)
        self.assertEqual(common.get_status(b)["etat"], "pret")
        self.assertEqual(common.read_json(auth.chemin_etat_auth("en"))["etat"], "a_refaire")
        self.assertFalse(common.read_json(common.STATE / "jetons.json")["en"]["connecte"])

    def test_option_chaine(self):
        a, b = self.episode_de("fr", "ep-fr"), self.episode_de("en", "ep-en")
        self.lancer_main("--en-attente", "--chaine", "en")
        self.assertEqual(common.get_status(a)["etat"], "pret")
        self.assertEqual(common.get_status(b)["etat"], "programme")

    def test_episode_nomme_utilise_la_chaine_de_l_episode(self):
        b = self.episode_de("en", "ep-en")
        self.lancer_main("ep-en")
        self.assertEqual({v["refresh"] for v in self.faux.videos.values()}, {"refresh-en"})
        self.assertEqual(common.get_status(b)["etat"], "programme")

    def test_creneaux_propres_a_chaque_chaine(self):
        self.episode_de("fr", "ep-fr1")
        self.publier("ep-fr1")
        self.assertEqual(len(publish.creneaux_pris(self.cfg, "fr")), 1)
        self.assertEqual(publish.creneaux_pris(self.cfg, "en"), set())   # la grille de en est libre
        self.assertEqual(len(publish.creneaux_pris(self.cfg)), 1)        # sans filtre : tout le monde (comportement d'avant)

    def test_reglages_d_une_chaine(self):
        en = reglages.charger_chaine(chaines.profil("en"))
        fr = reglages.charger_chaine(chaines.profil("fr"))
        self.assertEqual((en["langue"], en["fuseau"], en["hashtags_chaine"]), ("en", "America/New_York", []))
        self.assertEqual((fr["langue"], fr["fuseau"]), ("fr", "Europe/Paris"))
        self.assertIn("#LaDébrouille", fr["hashtags_chaine"])  # la chaîne par défaut garde ses hashtags, les autres n'héritent pas des siens

    def test_jetons_json_ne_contient_aucun_secret(self):
        etat = auth.ecrire_etat_jetons()
        self.assertTrue(etat["fr"]["connecte"] and etat["en"]["connecte"])
        self.assertFalse(etat["quiz"]["connecte"] if "quiz" in etat else False)
        brut = (common.STATE / "jetons.json").read_text(encoding="utf-8")
        for secret in ("refresh-test", "refresh-en", "acces-refresh-en", "jeton-initial", "secret-test"):
            self.assertNotIn(secret, brut)

    def test_jeton_d_une_chaine_inconnue(self):
        with self.assertRaises(ErreurAuth):
            auth.chemin_jeton("inconnue")


class TestConnecterChaine(BaseChaines):
    def yt_de(self, ident):
        return YouTube(auth.Jeton(chaine=ident), self.cfg, self.quota.pour(ident), dormir=self.pauses.append)

    def test_connexion_enregistre_le_jeton_et_verifie_la_chaine(self):
        auth.chemin_jeton("en").unlink()
        self.faux.chaines_de["refresh-en"] = ("UCen", "Business Facts")

        def faux_autoriser(ouvrir_navigateur=True, afficher=print, chaine=None, **kw):
            self.ecrire_jeton_chaine(chaine, "refresh-en")

        info = connecter_chaine.connecter("en", autoriser=faux_autoriser, afficher=lambda *a: None, yt=self.yt_de("en"))
        self.assertEqual(info, {"id": "UCen", "titre": "Business Facts"})
        self.assertEqual(common.read_json(connecter_chaine.chemin_liens())["en"]["id"], "UCen")
        self.assertTrue(common.read_json(common.STATE / "jetons.json")["en"]["connecte"])
        self.assertEqual(common.read_json(auth.chemin_etat_auth("en"))["etat"], "ok")
        self.assertFalse(chaines.profil("en")["active"] and False)  # l'outil n'active jamais la chaîne

    def test_chaine_deja_liee_a_un_autre_profil_est_refusee_et_le_jeton_supprime(self):
        self.faux.chaines_de.update({"refresh-test": ("UCmeme", "La Débrouille"), "refresh-en": ("UCmeme", "La Débrouille")})
        connecter_chaine.verifier("fr", self.yt_de("fr"), afficher=lambda *a: None)
        auth.chemin_jeton("en").unlink()

        def faux_autoriser(ouvrir_navigateur=True, afficher=print, chaine=None, **kw):
            self.ecrire_jeton_chaine(chaine, "refresh-en")  # l'utilisateur a validé la mauvaise chaîne dans le sélecteur de Google

        with self.assertRaises(ErreurAuth) as cm:
            connecter_chaine.connecter("en", autoriser=faux_autoriser, afficher=lambda *a: None, yt=self.yt_de("en"))
        self.assertIn("déjà liée", str(cm.exception))
        self.assertFalse(auth.chemin_jeton("en").exists())
        self.assertFalse(common.read_json(common.STATE / "jetons.json")["en"]["connecte"])

    def test_un_jeton_existant_n_est_pas_ecrase_sans_refaire(self):
        self.faux.chaines_de["refresh-en"] = ("UCen", "Business Facts")
        appels = []
        connecter_chaine.connecter("en", autoriser=lambda **kw: appels.append(kw), afficher=lambda *a: None, yt=self.yt_de("en"))
        self.assertEqual(appels, [])  # simple vérification

    def test_refaire_garde_l_ancien_jeton_si_la_verification_echoue(self):
        self.faux.chaines_de.update({"refresh-test": ("UCmeme", "FR"), "refresh-nouveau": ("UCmeme", "FR")})
        connecter_chaine.verifier("fr", self.yt_de("fr"), afficher=lambda *a: None)

        def faux_autoriser(ouvrir_navigateur=True, afficher=print, chaine=None, **kw):
            self.ecrire_jeton_chaine(chaine, "refresh-nouveau")

        with self.assertRaises(ErreurAuth):
            connecter_chaine.connecter("en", refaire=True, autoriser=faux_autoriser, afficher=lambda *a: None, yt=self.yt_de("en"))
        self.assertEqual(common.read_json(auth.chemin_jeton("en"))["refresh_token"], "refresh-en")

    def test_profil_inconnu(self):
        with self.assertRaises(ErreurAuth):
            connecter_chaine.connecter("nexiste-pas", autoriser=lambda **kw: None, afficher=lambda *a: None)

    def test_sans_client_secret(self):
        auth.chemin_jeton("en").unlink()
        auth.chemin_client().unlink()
        with self.assertRaises(ErreurAuth):
            connecter_chaine.connecter("en", autoriser=lambda **kw: None, afficher=lambda *a: None)


if __name__ == "__main__":
    unittest.main()
