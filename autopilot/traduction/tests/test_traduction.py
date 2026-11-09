"""Traduction / adaptation multilingue : épisode cible valide, parité, localisation, file et stock, repli gratuit, isolation, factcheck, jamais d'activation.

Lancer :  python -m unittest discover -s autopilot/traduction/tests      (depuis pixel-faits/)
"""
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone

from base import (DICO, EN_PHRASES, SOURCE_EP, SOURCE_FAITS, SOURCE_PUB, SRC, TMP, Base, FauxMoteur, adaptation, chaines, common, controle, file_,  # noqa: E402
                  langues, parite, traduire, valider)

CIBLE = f"en-{SRC}"


class Localisation(unittest.TestCase):
    def test_nombres_en_lettres(self):
        f = langues.chiffres_en_lettres_en
        self.assertEqual(f("12,500 dollars"), "twelve thousand five hundred dollars")
        self.assertEqual(f("$12,500"), "twelve thousand five hundred dollars")
        self.assertEqual(f("€1"), "one euro")
        self.assertEqual(f("5% of sales"), "five percent of sales")
        self.assertEqual(f("2.5 million"), "two point five million")
        self.assertEqual(f("in 2014"), "in twenty fourteen")
        self.assertEqual(f("in 1905"), "in nineteen oh five")
        self.assertEqual(f("100"), "one hundred")
        self.assertEqual(f("21 days"), "twenty-one days")
        self.assertEqual(f("$3.50"), "three dollars and fifty cents")
        self.assertEqual(f("no digits here"), "no digits here")

    def test_langue_plausible(self):
        self.assertTrue(langues.langue_plausible(" ".join(EN_PHRASES), "en"))
        self.assertFalse(langues.langue_plausible("Une mairie cherche un peintre et doit publier son besoin dans les journaux", "en"))
        self.assertTrue(langues.langue_plausible("Une mairie cherche un peintre et doit publier son besoin dans les journaux", "fr"))

    def test_ecran_anglais(self):
        self.assertEqual(adaptation.localiser_ecran("12 000,5 €", "en"), "€12,000.5")
        self.assertEqual(adaptation.localiser_ecran("15 %", "en"), "15%")
        self.assertEqual(adaptation.localiser_ecran("12 000 €", "fr"), "12 000 €")


class Parite(Base):
    def test_adaptation_de_reference_a_la_meme_structure(self):
        ep = adaptation.adapter_episode(copy.deepcopy(SOURCE_EP), FauxMoteur(), "en", "Business Facts", CIBLE)
        self.assertEqual(parite.comparer_episode(SOURCE_EP, ep), [])
        self.assertEqual(ep["langue"], "en")
        self.assertEqual(ep["chaine"], "Business Facts")
        self.assertEqual(ep["scenes"][2]["params"]["valeur"], 12500)          # un chiffre ne change jamais
        self.assertEqual(ep["scenes"][2]["params"]["suffixe"], " €")          # symbole seul : recopié
        self.assertEqual(ep["scenes"][0]["params"]["accents"][0], "craftsmen")  # accents refaits depuis la phrase traduite
        self.assertEqual(ep["miniature"]["texte_haut"], "PUBLIC TENDERS FOR SMALL CRAFTSMEN")
        self.assertEqual(ep["miniature"]["style"], "createur")                # identifiant technique

    def test_un_chiffre_modifie_est_refuse(self):
        ep = adaptation.adapter_episode(copy.deepcopy(SOURCE_EP), FauxMoteur(), "en", "BF", CIBLE)
        ep["scenes"][2]["params"]["valeur"] = 14000  # « conversion » interdite
        self.assertTrue(any("12500" in e for e in parite.comparer_episode(SOURCE_EP, ep)))

    def test_scene_manquante_ou_type_change(self):
        ep = adaptation.adapter_episode(copy.deepcopy(SOURCE_EP), FauxMoteur(), "en", "BF", CIBLE)
        ep["scenes"][1]["type"] = "barres"
        ep2 = copy.deepcopy(ep)
        del ep2["scenes"][2]
        self.assertTrue(parite.comparer_episode(SOURCE_EP, ep))
        self.assertTrue(any("élément" in e for e in parite.comparer_episode(SOURCE_EP, ep2)))

    def test_faits_gardent_sources_et_termes(self):
        faits = adaptation.adapter_faits(copy.deepcopy(SOURCE_FAITS), FauxMoteur(), "en")
        self.assertEqual(parite.comparer_faits(SOURCE_FAITS, faits), [])
        self.assertEqual(faits[0]["sources"], SOURCE_FAITS[0]["sources"])
        faits[0]["sources"] = ["https://exemple.org/a", "https://autre.org/b"]
        self.assertTrue(parite.comparer_faits(SOURCE_FAITS, faits))

    def test_pas_de_copie_du_titre(self):
        pub = adaptation.adapter_publication(copy.deepcopy(SOURCE_PUB), FauxMoteur(), "en", "en")
        self.assertEqual(parite.comparer_publication(SOURCE_PUB, pub), [])
        pub["titre"] = SOURCE_PUB["titre"]
        self.assertTrue(parite.comparer_publication(SOURCE_PUB, pub))
        self.assertEqual(adaptation.adapter_publication(copy.deepcopy(SOURCE_PUB), FauxMoteur(), "en", "en")["langue"], "en")


class Valider(Base):
    def valider(self, ident=CIBLE):
        return valider.valider_brouillon(ident, "en", sans_reseau=True)

    def demande(self):
        return file_.creer_demande(self.en(), SRC)

    def test_episode_cible_valide_de_bout_en_bout(self):
        self.demande()
        self.brouillon(CIBLE)
        code, bilan = self.valider()
        self.assertEqual(code, 0, bilan)
        st = self.lire(f"episodes-b/{CIBLE}/status.json")
        self.assertEqual((st["etat"], st["chaine_id"]), ("ecrit", "en"))
        self.assertEqual(common.chaine_de(CIBLE), "en")
        t = self.lire(f"episodes-b/{CIBLE}/traduction.json")
        self.assertEqual((t["source"], t["moteur"], t["acceptee"]), (SRC, "claude", True))
        self.assertEqual(self.lire(f"episodes-b/{CIBLE}/episode.json")["langue"], "en")
        self.assertEqual(self.lire(f"episodes-b/{CIBLE}/publication.json")["langue"], "en")
        self.assertFalse((TMP / "episodes-b" / "_traductions" / CIBLE).exists(), "la demande est consommée")
        self.assertIn(CIBLE, common.list_episodes(chaine="en"))
        self.assertNotIn(CIBLE, common.list_episodes(chaine="fr"))

    def test_chiffres_dans_le_texte_parle_refuses(self):
        self.demande()
        ep, _, _ = self.brouillon(CIBLE)
        ep["phrases"][1] = "A town hall needs 2 painters or a gardener, and it must publish that need."
        self.brouillon(CIBLE, ep=ep)
        code, bilan = self.valider()
        self.assertEqual(code, 1)
        self.assertTrue(any("chiffres dans le texte parlé" in e for e in bilan["erreurs"]), bilan)

    def test_phrases_restees_en_francais_refusees(self):
        self.demande()
        ep, _, _ = self.brouillon(CIBLE)
        ep["phrases"] = list(SOURCE_EP["phrases"])
        self.brouillon(CIBLE, ep=ep)
        code, bilan = self.valider()
        self.assertEqual(code, 1)
        txt = " ".join(bilan["erreurs"])
        self.assertIn("ne ressemble pas", txt)
        self.assertIn("recopiées", txt)

    def test_chiffre_de_scene_modifie_refuse_par_valider(self):
        self.demande()
        ep, _, _ = self.brouillon(CIBLE)
        ep["scenes"][2]["params"]["valeur"] = 99
        self.brouillon(CIBLE, ep=ep)
        code, bilan = self.valider()
        self.assertEqual(code, 1)
        self.assertTrue(any("le chiffre doit rester" in e for e in bilan["erreurs"]), bilan)

    def test_titre_identique_refuse_puis_quarantaine_avec_raison(self):
        self.demande()
        _, _, pub = self.brouillon(CIBLE)
        pub["titre"] = SOURCE_PUB["titre"]
        for essai in (1, 2):
            self.brouillon(CIBLE, pub=pub)
            code, bilan = self.valider()
            self.assertEqual(code, 1, bilan)
        self.brouillon(CIBLE, pub=pub)
        code, bilan = self.valider()
        self.assertEqual(code, 2)
        st = self.lire(f"episodes-b/{CIBLE}/status.json")
        self.assertEqual(st["etat"], "quarantaine")
        self.assertIn("identique", st["raison"])
        self.assertFalse((TMP / "episodes-b" / "_traductions" / CIBLE).exists())

    def test_promesse_de_gain_et_avertissement_anglais_refuses(self):
        self.demande()
        ep, _, _ = self.brouillon(CIBLE)
        ep["phrases"][3] = "You watch the announcements and this is guaranteed to make you rich."
        self.brouillon(CIBLE, ep=ep)
        code, bilan = self.valider()
        self.assertEqual(code, 1)
        self.assertTrue(any("promesse de gain" in e for e in bilan["erreurs"]), bilan)
        ep["phrases"][3] = "You watch the announcements and this is not financial advice."
        self.brouillon(CIBLE, ep=ep)
        code, bilan = self.valider()
        self.assertTrue(any("avertissement" in e for e in bilan["erreurs"]), bilan)

    def test_factcheck_relance_dans_la_langue_cible(self):
        """Les faits de l'adaptation repassent par factcheck.verifier : le terme `check` doit se retrouver dans la page (cache local, pas de réseau)."""
        from autopilot.writer import factcheck
        self.demande()
        _, faits, _ = self.brouillon(CIBLE)
        appels = []
        vrai = factcheck.verifier

        def faux(fait, reseau=True):
            appels.append((fait["claim"], reseau))
            return fait["sources"][:1] if reseau else fait.get("verified", [])
        valider.verifier = faux
        try:
            code, bilan = valider.valider_brouillon(CIBLE, "en", sans_reseau=False)
        finally:
            valider.verifier = vrai
        self.assertEqual(code, 0, bilan)
        self.assertEqual(len(appels), 1)
        self.assertTrue(appels[0][0].startswith("A micro business"), appels)  # l'affirmation vérifiée est celle de la langue cible
        self.assertTrue(appels[0][1])

        # et une source qui ne contient pas le terme fait échouer l'adaptation
        self.demande_nouvelle = None

    def test_fait_non_verifie_refuse(self):
        self.demande()
        self.brouillon(CIBLE)
        valider.verifier = lambda fait, reseau=True: []
        try:
            code, bilan = valider.valider_brouillon(CIBLE, "en", sans_reseau=False)
        finally:
            from autopilot.writer import factcheck
            valider.verifier = factcheck.verifier
        self.assertEqual(code, 1)
        self.assertTrue(any("aucune source ne contient" in e for e in bilan["erreurs"]), bilan)

    def test_francais_inchange(self):
        """Un brouillon français passe toujours par les mêmes contrôles (aucun chiffre interdit, aucune parité)."""
        self.assertTrue(valider.a_un_nombre("Il y a trois euros"))
        self.assertFalse(valider.a_un_nombre("Il y a des euros"))
        self.assertTrue(valider.a_un_nombre("There are three euros", "en"))
        self.assertEqual(valider.controles_langue(["12 euros"], {"langue": "fr"}, "fr"), [])


class File(Base):
    def test_sources_eligibles(self):
        self.source("a-ecrit", etat="ecrit")
        self.source("b-quarantaine", etat="quarantaine", raison="x")
        self.source("c-publie", etat="publie")
        self.source("d-derive", etat="pret")
        self.ecrire("episodes-b/d-derive/origine.json", {"long": "x"})
        self.source("e-pret", etat="controle")
        self.assertEqual(sorted(file_.sources_eligibles(self.en())), sorted([SRC, "c-publie", "e-pret"]))

    def test_demandes_respectent_la_cible_de_stock(self):
        for i in range(8):
            self.source(f"s{i}", etat="pret")
        bilan = file_.alimenter(self.en())
        self.assertEqual(len(bilan["creees"]), 3)  # max_par_passage
        self.assertTrue(all(i.startswith("en-") for i in bilan["creees"]))
        dem = self.lire(f"episodes-b/_traductions/{bilan['creees'][0]}/demande.json")
        self.assertEqual((dem["chaine_cible"], dem["langue"], dem["format"]), ("en", "en", "short"))
        self.assertIn("episode", dem)
        # la cible est atteinte -> plus rien n'est demandé
        p = self.en()
        p["source"]["cible_jours_de_stock"] = 0.1
        self.assertEqual(file_.alimenter(p)["creees"], [])

    def test_stock_plein_ne_demande_rien(self):
        for i in range(12):
            self.ecrire(f"episodes-b/en-vieux{i}/episode.json", {"id": f"en-vieux{i}", "phrases": []})
            self.ecrire(f"episodes-b/en-vieux{i}/status.json", {"etat": "pret", "maj": common.now(), "raison": None, "chaine_id": "en"})
        self.assertGreaterEqual(file_.stock_cible(self.en())["jours_de_stock"], 4)
        self.assertEqual(file_.alimenter(self.en())["creees"], [])

    def test_une_source_n_est_jamais_demandee_deux_fois(self):
        self.assertEqual(file_.alimenter(self.en())["creees"], [CIBLE])
        self.assertEqual(file_.alimenter(self.en())["creees"], [])
        self.assertEqual(file_.sources_eligibles(self.en()), [])

    def test_chaine_non_preparee_ni_active_ignoree(self):
        self.profil("en", langue="en", voix={"dossier": "voix/en"}, source={"chaine": "fr", "mode": "traduction"}, preparation=False, active=False)
        self.assertEqual(file_.chaines_cibles(), [])
        self.assertEqual(traduire.passe(), {})

    def test_profil_invalide_ignore(self):
        self.profil("en", langue="en", preparation=True, source={"chaine": "fr", "mode": "traduction"})  # pas de voix.dossier
        self.assertEqual(file_.chaines_cibles(), [])


class Repli(Base):
    def test_repli_traduit_et_valide_un_short(self):
        file_.creer_demande(self.en(), SRC)
        b = traduire.repli(self.en(), forcer=True, traducteur=FauxMoteur(), sans_reseau=True)
        self.assertEqual(b["acceptes"], [CIBLE], b)
        t = self.lire(f"episodes-b/{CIBLE}/traduction.json")
        self.assertEqual((t["moteur"], t["a_relire"]), ("faux", True))
        self.assertEqual(common.get_status(CIBLE)["etat"], "ecrit")
        ep = self.lire(f"episodes-b/{CIBLE}/episode.json")
        self.assertEqual(ep["phrases"][0], DICO[SOURCE_EP["phrases"][0]])

    def test_claude_a_la_priorite(self):
        """Demande récente, Claude non bloqué : le repli n'y touche pas. Claude bloqué ou demande ancienne : il la prend."""
        file_.creer_demande(self.en(), SRC)
        self.assertEqual(traduire.a_traiter_par_repli(self.en()), [])
        (TMP / "autopilot" / "state" / "claude_blocked.json").write_text("{}", encoding="utf-8")
        self.assertEqual(traduire.a_traiter_par_repli(self.en()), [CIBLE])
        (TMP / "autopilot" / "state" / "claude_blocked.json").unlink()
        f = TMP / "episodes-b" / "_traductions" / CIBLE / "demande.json"
        dem = json.loads(f.read_text(encoding="utf-8"))
        dem["cree_le"] = (datetime.now() - timedelta(hours=40)).isoformat(timespec="seconds")
        f.write_text(json.dumps(dem), encoding="utf-8")
        self.assertEqual(traduire.a_traiter_par_repli(self.en()), [CIBLE])

    def test_un_brouillon_de_claude_n_est_pas_ecrase_par_le_repli(self):
        file_.creer_demande(self.en(), SRC)
        self.brouillon(CIBLE)
        self.assertEqual(traduire.a_traiter_par_repli(self.en(), forcer=True), [])

    def test_isolation_des_echecs(self):
        self.source("autre-source", etat="pret")
        autre = f"en-autre-source"
        for s in (SRC, "autre-source"):
            file_.creer_demande(self.en(), s)
        dico = {**DICO, "Même une micro-entreprise peut répondre à un marché public.": "Even a micro business can answer a public tender in France."}
        b = traduire.repli(self.en(), forcer=True, traducteur=FauxMoteur(dico, casser=[SOURCE_EP["phrases"][0]]), sans_reseau=True)
        # les deux sources ont le même texte : le moteur plante pour les deux -> aucune n'est acceptée, mais le passage va au bout sans exception
        self.assertEqual(len(b["echecs"]), 2)
        self.assertEqual(b["acceptes"], [])
        # le moteur est réparé : les demandes (non consommées) repartent
        b2 = traduire.repli(self.en(), forcer=True, traducteur=FauxMoteur(), sans_reseau=True)
        self.assertCountEqual(b2["acceptes"], [CIBLE, autre])

    def test_echecs_repetes_du_moteur_mettent_en_quarantaine_avec_raison(self):
        file_.creer_demande(self.en(), SRC)
        for _ in range(traduire.MAX_ECHECS_MOTEUR):
            traduire.repli(self.en(), forcer=True, traducteur=FauxMoteur(casser=[SOURCE_EP["phrases"][0]]), sans_reseau=True)
        st = common.get_status(CIBLE)
        self.assertEqual(st["etat"], "quarantaine")
        self.assertIn("traduction impossible", st["raison"])
        self.assertEqual(st["chaine_id"], "en")
        self.assertEqual(file_.alimenter(self.en())["creees"], [])  # jamais redemandée

    def test_moteur_absent_n_est_pas_une_erreur(self):
        file_.creer_demande(self.en(), SRC)
        b = traduire.repli(self.en(), forcer=True, sans_reseau=True)
        self.assertIn("indisponible", b)
        self.assertEqual(common.list_episodes(chaine="en"), [])

    def test_un_long_attend_claude(self):
        d = "episodes-b/long-test"
        self.ecrire(f"{d}/episode.json", {"id": "long-test", "phrases": ["x"], "scenes": []})
        self.ecrire(f"{d}/episode-long.json", {"id": "long-test", "chapitres": []})
        self.ecrire(f"{d}/faits.json", [])
        self.ecrire(f"{d}/publication.json", SOURCE_PUB)
        self.ecrire(f"{d}/status.json", {"etat": "pret", "maj": "2026-11-01T10:00:00", "raison": None, "chaine_id": "fr"})
        dem = file_.creer_demande(self.en(), "long-test")
        self.assertEqual(dem["format"], "long")
        b = traduire.repli(self.en(), forcer=True, traducteur=FauxMoteur(), sans_reseau=True)
        self.assertEqual(b["ignores"][0]["id"], "en-long-test")


class JamaisActive(Base):
    def test_aucune_passe_n_active_la_chaine(self):
        avant = (TMP / "autopilot" / "chaines" / "en.json").read_text(encoding="utf-8")
        traduire.passe(traducteur=FauxMoteur(), sans_reseau=True, forcer=True)
        traduire.etat()
        self.assertEqual((TMP / "autopilot" / "chaines" / "en.json").read_text(encoding="utf-8"), avant)
        self.assertFalse(chaines.est_active("en"))
        self.assertFalse(chaines.profil("en")["active"])
        self.assertIn("en", [p["id"] for p in chaines.preparees()])
        self.assertNotIn("en", [p["id"] for p in chaines.actives()])

    def test_la_passe_alimente_la_chaine_preparee(self):
        b = traduire.passe(traducteur=FauxMoteur(), sans_reseau=True, forcer=True)
        self.assertEqual(b["en"]["repli"]["acceptes"], [CIBLE], b)
        self.assertEqual(common.get_status(CIBLE)["etat"], "ecrit")
        etat = self.lire("autopilot/state/traduction.json")
        self.assertEqual(etat["chaines"]["en"]["adaptes"], 1)
        self.assertEqual(etat["chaines"]["en"]["voix"]["mode"], "integree")
        self.assertFalse(etat["chaines"]["en"]["active"])

    def test_dry_run_ne_cree_rien(self):
        b = traduire.passe(dry_run=True)
        self.assertEqual(b["en"]["sources_eligibles"], [SRC])
        self.assertEqual(file_.demandes_ouvertes(), [])


class Decalage(Base):
    def adapte(self, **statut_source):
        self.source(SRC, etat="publie", **statut_source)
        self.ecrire(f"episodes-b/{CIBLE}/traduction.json", {"source": SRC})
        self.ecrire(f"episodes-b/{CIBLE}/status.json", {"etat": "pret", "maj": common.now(), "raison": None, "chaine_id": "en"})

    def test_non_adaptation_toujours_publiable(self):
        from autopilot.traduction import decalage
        self.assertEqual(decalage.pret_a_sortir(SRC), (True, ""))

    def test_source_non_publiee_bloque(self):
        from autopilot.traduction import decalage
        self.source(SRC, etat="pret")
        self.ecrire(f"episodes-b/{CIBLE}/traduction.json", {"source": SRC})
        self.ecrire(f"episodes-b/{CIBLE}/status.json", {"etat": "pret", "maj": common.now(), "raison": None, "chaine_id": "en"})
        ok, raison = decalage.pret_a_sortir(CIBLE)
        self.assertFalse(ok)
        self.assertIn("pas encore publiée", raison)

    def test_decalage_de_48_heures(self):
        from autopilot.traduction import decalage
        publie = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        self.adapte(youtube={"video_id": "abc", "url": None, "visibilite": "public", "publie_a": publie.isoformat()})
        self.assertFalse(decalage.pret_a_sortir(CIBLE, publie + timedelta(hours=47))[0])
        self.assertTrue(decalage.pret_a_sortir(CIBLE, publie + timedelta(hours=49))[0])


class Orchestrateur(Base):
    """L'orchestrateur (run_daily) : la chaîne en préparation est fabriquée, jamais publiée ; la passe `traduire` est isolée et sans publication."""

    def setUp(self):
        super().setUp()
        import run_daily
        self.run_daily = run_daily
        self.ecrire("episodes-b/en-fabrique/episode.json", {"id": "en-fabrique", "phrases": []})
        self.ecrire("episodes-b/en-fabrique/status.json", {"etat": "ecrit", "maj": common.now(), "raison": None, "chaine_id": "en"})

    def test_fabrication_inclut_la_chaine_en_preparation_pas_la_publication(self):
        self.assertIn("en-fabrique", self.run_daily.candidats(("ecrit",), None, preparees=True))
        self.assertNotIn("en-fabrique", self.run_daily.candidats(("ecrit",), None))                 # défaut = chaînes ACTIVES (publication)
        self.assertNotIn("en-fabrique", self.run_daily.candidats(("pret", "programme"), None))

    def test_chaine_ni_active_ni_en_preparation_n_est_fabriquee(self):
        self.profil("en", langue="en", voix={"dossier": "voix/en"}, source={"chaine": "fr", "mode": "traduction"}, preparation=False)
        self.assertEqual(self.run_daily.candidats(("ecrit",), None, preparees=True), [])

    def test_commande_traduire_cree_les_demandes_sans_rien_publier(self):
        import argparse
        a = argparse.Namespace(chaine=None, max=None, sans_repli=True, forcer=False, dry_run=False)
        bilan = self.run_daily.cmd_traduire(a)
        self.assertEqual(bilan, {"chaines": 1, "erreurs": 0})
        self.assertEqual(file_.demandes_ouvertes("en"), [f"en-{SRC}"])
        self.assertFalse(chaines.est_active("en"))

    def test_stock_par_chaine_expose_la_preparation_et_la_voix(self):
        b = self.run_daily.stock_par_chaine()["en"]
        self.assertTrue(b["preparation"])
        self.assertFalse(b["active"])
        self.assertEqual((b["source"], b["voix"]["mode"], b["voix"]["locuteur"]), ("fr", "integree", "Ryan"))
        self.assertFalse(self.run_daily.stock_par_chaine()["fr"]["preparation"])


class Profils(Base):
    def test_chaine_non_francaise_en_preparation_exige_une_voix(self):
        self.profil("es", langue="es", preparation=True, source={"chaine": "fr", "mode": "traduction"})
        self.assertTrue(any("voix propre" in e for e in chaines.charger_profils()["es"]["erreurs"]))

    def test_options_de_source_validees(self):
        self.profil("es", langue="es", voix={"dossier": "voix/es"}, source={"chaine": "fr", "mode": "inconnu", "decalage_heures": -3})
        err = " ".join(chaines.charger_profils()["es"]["erreurs"])
        self.assertIn("source.mode", err)
        self.assertIn("decalage_heures", err)

    def test_voix_integree_clone_ou_manquante(self):
        p = self.en()
        self.assertEqual(chaines.voix_info(p)["mode"], "integree")
        env = chaines.env_briques(p)
        self.assertEqual((env["BDF_LANGUE"], env["BDF_LOCUTEUR"], env["BDF_VITESSE"]), ("en", "Ryan", "1.0"))
        self.assertNotIn("BDF_REF_WAV", env)
        (TMP / "autopilot" / "voix" / "en" / "ref.wav").write_bytes(b"RIFF")
        (TMP / "autopilot" / "voix" / "en" / "ref.txt").write_text("hello", encoding="utf-8")
        self.assertEqual(chaines.voix_info(p)["mode"], "clone")  # une voix de référence de l'utilisateur prend le dessus
        self.assertNotIn("BDF_LOCUTEUR", chaines.env_briques(p))
        (TMP / "autopilot" / "voix" / "en" / "voix.json").unlink()
        (TMP / "autopilot" / "voix" / "en" / "ref.wav").unlink()
        self.assertFalse(chaines.voix_info(p)["disponible"])


if __name__ == "__main__":
    unittest.main()
