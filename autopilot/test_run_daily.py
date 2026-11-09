"""Tests de l'orchestrateur, dans un dossier temporaire (BDF_ROOT). Aucune voix réelle, aucun GPU, aucune vraie notification.

Lancer :  cd autopilot && python -m unittest -v
"""
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REAL_AUTOPILOT = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="bdf-test-"))
os.environ["BDF_ROOT"] = str(TMP)
os.environ["BDF_NOTIF_DESACTIVEE"] = "1"
os.environ["BDF_PAUSE_S"] = "0"
os.environ["BDF_DISQUE_LIBRE_GO"] = "50"
sys.path.insert(0, str(REAL_AUTOPILOT))

import chaines  # noqa: E402
import common  # noqa: E402
import run_daily  # noqa: E402

assert common.ROOT == TMP.resolve(), "BDF_ROOT n'est pas pris en compte"

FAKE_MAKE_SHORT = '''
import sys, time
sys.path.insert(0, r"%(real)s")
import common
ep = sys.argv[1]
with open(common.ROOT / "appels.log", "a", encoding="utf-8") as f:
    f.write("make_short " + ep + " " + " ".join(sys.argv[2:]) + "\\n")
mp = common.ep_dir(ep) / "mode.txt"
mode = mp.read_text().strip() if mp.exists() else "ok"
def sortie(publiable=True, problemes=()):
    (common.EXPORTS / ep).mkdir(parents=True, exist_ok=True)
    (common.EXPORTS / ep / (ep + ".mp4")).write_bytes(b"x")
    common.write_json(common.EXPORTS / ep / "qa.json", {"publiable": publiable, "problemes": list(problemes), "alertes": []})
if mode == "ok":
    sortie(); common.set_status(ep, "controle")
elif mode == "ok-sans-statut":
    sortie()
elif mode == "crash":
    print("boum : GPU hors memoire"); sys.exit(1)
elif mode == "crash-une-fois":
    flag = common.ep_dir(ep) / "deja.flag"
    if not flag.exists():
        flag.write_text("1"); print("premier echec"); sys.exit(1)
    sortie(); common.set_status(ep, "controle")
elif mode == "quarantaine":
    common.set_status(ep, "quarantaine", "volume hors limites"); sys.exit(2)
elif mode == "quarantaine-muette":
    sortie(False, ["duree 75 s > 60 s"]); sys.exit(2)
elif mode == "dort":
    time.sleep(60)
'''


FAKE_MAKE_LONG = '''
import sys
sys.path.insert(0, r"%(real)s")
import common
ep = sys.argv[1]
with open(common.ROOT / "appels.log", "a", encoding="utf-8") as f:
    f.write("make_long " + ep + " " + " ".join(sys.argv[2:]) + "\\n")
mp = common.ep_dir(ep) / "mode.txt"
mode = mp.read_text().strip() if mp.exists() else "ok"
if mode == "reprise":
    sys.exit(3)
if mode == "crash":
    print("boum"); sys.exit(1)
if mode == "quarantaine":
    common.set_status(ep, "quarantaine", "duree 3 min hors de 5 a 15"); sys.exit(2)
(common.EXPORTS / ep).mkdir(parents=True, exist_ok=True)
(common.EXPORTS / ep / (ep + ".mp4")).write_bytes(b"x")
common.write_json(common.EXPORTS / ep / "qa.json", {"publiable": True, "problemes": [], "alertes": []})
common.set_status(ep, "controle")
'''


FAKE_TIKTOK = '''
import sys, json
sys.path.insert(0, r"%(real)s")
import common
with open(common.ROOT / "appels.log", "a", encoding="utf-8") as f:
    f.write("tiktok " + " ".join(sys.argv[1:]) + "\\n")
mode = (common.ROOT / "tiktok_mode.txt").read_text().strip() if (common.ROOT / "tiktok_mode.txt").exists() else "ok"
if mode == "auth":
    print(json.dumps({"auth": "jeton absent", "paquets": ["x"], "envoyes": []})); sys.exit(3)
print(json.dumps({"envoyes": ["a", "b"]}))
'''

FAKE_MINIATURE = '''
import sys
sys.path.insert(0, r"%(real)s")
import common
ep = sys.argv[1]
with open(common.ROOT / "appels.log", "a", encoding="utf-8") as f:
    f.write("miniature " + ep + "\\n")
(common.ep_dir(ep) / "miniature.png").write_bytes(b"png")
common.set_status(ep, "pret")
'''

FAKE_PUBLISH = '''
import sys
sys.path.insert(0, r"%(real)s")
import common
with open(common.ROOT / "appels.log", "a", encoding="utf-8") as f:
    f.write("publish " + " ".join(sys.argv[1:]) + "\\n")
'''


def png(path: Path, w: int, h: int, extra: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", w, h) + b"\x08\x06\0\0\0" + b"0" * extra)


def faux_episode(ep: str, etat: str = "ecrit", mode: str | None = None, raison: str | None = None) -> None:
    d = common.ep_dir(ep)
    d.mkdir(parents=True, exist_ok=True)
    (d / "episode.json").write_text("{}", encoding="utf-8")
    if mode:
        (d / "mode.txt").write_text(mode)
    if etat != "ecrit" or raison:
        common.set_status(ep, etat, raison)


def appels() -> list:
    p = common.ROOT / "appels.log"
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def lancer(*argv) -> int:
    with redirect_stdout(io.StringIO()):
        return run_daily.main(list(argv))


class Base(unittest.TestCase):
    def setUp(self):
        for h in list(run_daily.log.handlers):
            run_daily.log.removeHandler(h)
            h.close()
        for d in ("episodes-b", "exports-b", "autopilot", "miniatures-manuelles", "appels.log"):
            p = TMP / d
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        os.environ["BDF_DISQUE_LIBRE_GO"] = "50"  # les tests ne dépendent pas du vrai disque
        (TMP / "autopilot").mkdir(exist_ok=True)
        (TMP / "autopilot" / "make_short.py").write_text(FAKE_MAKE_SHORT % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        (TMP / "autopilot" / "make_long.py").write_text(FAKE_MAKE_LONG % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        (TMP / "autopilot" / "tiktok").mkdir(exist_ok=True)
        (TMP / "autopilot" / "tiktok" / "envoi.py").write_text(FAKE_TIKTOK % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        mode_tt = TMP / "tiktok_mode.txt"
        if mode_tt.exists():
            mode_tt.unlink()
        self.notifs = []
        patcher = mock.patch.object(run_daily, "envoyer_notification",
                                    side_effect=lambda t, m: self.notifs.append((t, m)) or "fichier")
        patcher.start()
        self.addCleanup(patcher.stop)

    def etat(self, ep):
        return common.get_status(ep)["etat"]


class Fabriquer(Base):
    def test_fabrication_normale_et_stock_json(self):
        faux_episode("a")
        self.assertEqual(lancer("fabriquer"), 0)
        self.assertEqual(self.etat("a"), "controle")
        stock = common.read_json(common.STATE / "stock.json")
        self.assertEqual(stock["par_etat"]["controle"], 1)
        self.assertFalse((common.ep_dir("a") / ".lock").exists())
        self.assertFalse((common.STATE / "gpu.lock").exists())

    def test_idempotent(self):
        faux_episode("a")
        lancer("fabriquer")
        lancer("fabriquer")
        self.assertEqual(len(appels()), 1)

    def test_sans_voix_transmis(self):
        faux_episode("a")
        lancer("fabriquer", "--sans-voix")
        self.assertIn("--sans-voix", appels()[0])

    def test_statut_pose_par_orchestrateur_si_la_brique_ne_le_fait_pas(self):
        faux_episode("a", mode="ok-sans-statut")
        lancer("fabriquer")
        self.assertEqual(self.etat("a"), "controle")

    def test_dry_run_ne_touche_a_rien(self):
        faux_episode("a")
        lancer("fabriquer", "--dry-run")
        self.assertEqual(appels(), [])
        self.assertEqual(self.etat("a"), "ecrit")
        self.assertFalse((common.STATE / "stock.json").exists())

    def test_reprise_apres_plantage(self):
        """Épisode resté en « voix », verrous laissés par un processus mort : tout est repris."""
        faux_episode("a", etat="voix")
        mort = 2 ** 31 - 2
        for p in (common.ep_dir("a") / ".lock", common.STATE / "gpu.lock", common.STATE / "run_fabriquer.lock"):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"{mort} {common.now()}")
        self.assertEqual(lancer("fabriquer"), 0)
        self.assertEqual(self.etat("a"), "controle")
        self.assertEqual(len(appels()), 1)

    def test_verrou_perime_par_age(self):
        faux_episode("a")
        lock = common.ep_dir("a") / ".lock"
        lock.write_text(f"{os.getpid()} vieux")  # pid vivant mais verrou vieux de 4 h
        vieux = time.time() - 4 * 3600
        os.utime(lock, (vieux, vieux))
        lancer("fabriquer")
        self.assertEqual(self.etat("a"), "controle")

    def test_instance_deja_en_cours(self):
        faux_episode("a")
        run = common.STATE / "run_fabriquer.lock"
        run.parent.mkdir(parents=True, exist_ok=True)
        run.write_text(f"{os.getpid()} {common.now()}")
        self.assertEqual(lancer("fabriquer"), 0)
        self.assertEqual(appels(), [])
        self.assertEqual(self.etat("a"), "ecrit")

    def test_gpu_occupe(self):
        faux_episode("a")
        faux_episode("b")
        gpu = common.STATE / "gpu.lock"
        gpu.parent.mkdir(parents=True, exist_ok=True)
        gpu.write_text(f"{os.getpid()} {common.now()}")  # processus vivant : verrou légitime
        self.assertEqual(lancer("fabriquer", "--attente-gpu", "0"), 0)
        self.assertEqual(appels(), [])
        self.assertEqual((self.etat("a"), self.etat("b")), ("ecrit", "ecrit"))
        self.assertTrue(gpu.exists(), "le verrou d'un autre ne doit pas être supprimé")

    def test_quarantaine_posee_par_la_brique(self):
        faux_episode("a", mode="quarantaine")
        lancer("fabriquer")
        st = common.get_status("a")
        self.assertEqual((st["etat"], st["raison"]), ("quarantaine", "volume hors limites"))
        self.assertEqual(len(appels()), 1, "pas de nouvel essai après une quarantaine")
        self.assertTrue(any("quarantaine" in t.lower() for t, _ in self.notifs))

    def test_code_2_sans_statut_pose_la_quarantaine_avec_la_raison_du_qa(self):
        faux_episode("a", mode="quarantaine-muette")
        lancer("fabriquer")
        st = common.get_status("a")
        self.assertEqual(st["etat"], "quarantaine")
        self.assertIn("duree 75 s", st["raison"])

    def test_echec_inattendu_deux_essais_puis_quarantaine_avec_trace(self):
        faux_episode("a", mode="crash")
        lancer("fabriquer")
        st = common.get_status("a")
        self.assertEqual(st["etat"], "quarantaine")
        self.assertIn("2 essais", st["raison"])
        self.assertIn("GPU hors memoire", st["raison"])
        self.assertEqual(len(appels()), 2)
        trace = common.ep_dir("a") / "trace-fabrique.log"
        self.assertIn("GPU hors memoire", trace.read_text(encoding="utf-8"))

    def test_echec_puis_succes_au_deuxieme_essai(self):
        faux_episode("a", mode="crash-une-fois")
        lancer("fabriquer")
        self.assertEqual(self.etat("a"), "controle")
        self.assertEqual(len(appels()), 2)
        self.assertEqual(common.get_status("a")["tentatives"], 0)

    def test_un_echec_n_arrete_pas_les_autres(self):
        faux_episode("a", mode="crash")
        faux_episode("b")
        lancer("fabriquer")
        self.assertEqual((self.etat("a"), self.etat("b")), ("quarantaine", "controle"))

    def test_delai_depasse_compte_comme_un_echec(self):
        faux_episode("a", mode="dort")
        t0 = time.time()
        lancer("fabriquer", "--timeout-min", "0.03")
        self.assertLess(time.time() - t0, 30)
        self.assertEqual(self.etat("a"), "quarantaine")
        self.assertIn("code 124", common.get_status("a")["raison"])

    def test_max_et_id(self):
        for e in ("a", "b", "c"):
            faux_episode(e)
        lancer("fabriquer", "--max", "1")
        self.assertEqual([self.etat(e) for e in "abc"], ["controle", "ecrit", "ecrit"])
        lancer("fabriquer", "--id", "c")
        self.assertEqual([self.etat(e) for e in "abc"], ["controle", "ecrit", "controle"])

    def test_disque_presque_plein_saute_le_rendu(self):
        faux_episode("a")
        os.environ["BDF_DISQUE_LIBRE_GO"] = "2.1"
        lancer("fabriquer")
        self.assertEqual(appels(), [])
        self.assertEqual(self.etat("a"), "ecrit")
        stock = common.read_json(common.STATE / "stock.json")
        self.assertTrue(stock["disque_bas"])
        self.assertTrue(any("disque" in t.lower() for t, _ in self.notifs))

    def test_disque_juste_au_dessus_du_seuil(self):
        faux_episode("a")
        os.environ["BDF_DISQUE_LIBRE_GO"] = "3.5"
        lancer("fabriquer")
        self.assertEqual(self.etat("a"), "controle")


class FabriquerLong(Base):
    def long(self, ep, mode=None):
        faux_episode(ep, mode=mode)
        (common.ep_dir(ep) / "episode-long.json").write_text("{}", encoding="utf-8")

    def test_un_long_passe_par_make_long_et_jamais_par_make_short(self):
        self.long("l")
        faux_episode("c")
        lancer("fabriquer")
        a = appels()
        self.assertTrue(any(x.startswith("make_long l --budget-min 90") for x in a), a)
        self.assertFalse(any(x.startswith("make_short l") for x in a), a)
        self.assertTrue(any(x.startswith("make_short c") for x in a), a)
        self.assertEqual(self.etat("l"), "controle")

    def court_derive(self, long_id, n, voix=True):
        sid = f"{long_id}-s{n}"
        faux_episode(sid)
        common.write_json(common.ep_dir(sid) / "origine.json", {"long": long_id})
        if voix:
            (common.ep_dir(sid) / "voice.wav").write_bytes(b"w")
        return sid

    def test_les_shorts_d_un_long_sont_rendus_dans_le_meme_passage(self):
        """Régression : sur le cloud leur voice.wav n'est pas enregistré, un Short laissé au passage suivant partait en quarantaine."""
        self.long("l")
        s1, s2 = self.court_derive("l", 1), self.court_derive("l", 2)
        lancer("fabriquer", "--max", "1")  # même avec --max 1 : les Shorts du long ne comptent pas
        a = appels()
        for s in (s1, s2):
            self.assertEqual(a.count(f"make_short {s} --voix-prete"), 1, a)
            self.assertEqual(self.etat(s), "controle")

    def test_un_short_derive_sans_voix_est_laisse_de_cote(self):
        self.long("l")
        sans = self.court_derive("l", 1, voix=False)
        autre = self.court_derive("autre", 1)  # Short d'un autre long : pas touché par celui-ci
        lancer("fabriquer", "--id", "l")
        a = appels()
        self.assertFalse(any(x.startswith(f"make_short {sans}") for x in a), a)
        self.assertFalse(any(x.startswith(f"make_short {autre}") for x in a), a)
        self.assertEqual(self.etat(sans), "ecrit")

    def test_un_short_n_est_pas_rendu_deux_fois(self):
        self.long("l")
        s1 = self.court_derive("l", 1)
        lancer("fabriquer")
        self.assertEqual(sum(x.startswith(f"make_short {s1} ") for x in appels()), 1, appels())

    def test_code_3_est_une_reprise_pas_un_echec(self):
        self.long("l", mode="reprise")
        for _ in range(4):
            lancer("fabriquer")
        self.assertEqual(self.etat("l"), "ecrit")
        self.assertFalse(common.get_status("l").get("tentatives"))
        self.assertEqual(len([x for x in appels() if x.startswith("make_long l")]), 4)

    def test_deux_plantages_mettent_le_long_en_quarantaine(self):
        self.long("l", mode="crash")
        lancer("fabriquer")
        self.assertEqual(self.etat("l"), "ecrit")
        lancer("fabriquer")
        self.assertEqual(self.etat("l"), "quarantaine")

    def test_quarantaine_posee_par_la_brique(self):
        self.long("l", mode="quarantaine")
        lancer("fabriquer")
        self.assertEqual(self.etat("l"), "quarantaine")

    def test_budget_de_voix_transmis(self):
        self.long("l")
        lancer("fabriquer", "--budget-long-min", "45")
        self.assertTrue(any("make_long l --budget-min 45" in x for x in appels()), appels())


class TikTok(Base):
    def test_notifie_quand_des_videos_attendent_dans_la_boite(self):
        self.assertEqual(lancer("tiktok"), 0)
        self.assertEqual(appels(), ["tiktok "])
        self.assertTrue(any("2 vidéo(s)" in m for _, m in self.notifs), self.notifs)

    def test_connexion_a_refaire_alerte_une_fois(self):
        (TMP / "tiktok_mode.txt").write_text("auth")
        lancer("tiktok")
        lancer("tiktok")
        n = [m for t, m in self.notifs if "Connexion TikTok" in m]
        self.assertEqual(len(n), 1, self.notifs)

    def test_dry_run_transmis_sans_notification(self):
        lancer("tiktok", "--dry-run")
        self.assertEqual(appels(), ["tiktok --dry-run"])
        self.assertEqual(self.notifs, [])


class Finaliser(Base):
    def test_miniature_manuelle_valide(self):
        faux_episode("a", etat="controle")
        png(TMP / "miniatures-manuelles" / "a.png", 1280, 720)
        lancer("finaliser")
        self.assertEqual(self.etat("a"), "pret")
        self.assertTrue((common.ep_dir("a") / "miniature.png").exists())

    def test_miniature_manuelle_invalide_est_refusee(self):
        faux_episode("a", etat="controle")
        png(TMP / "miniatures-manuelles" / "a.png", 1920, 1080)
        lancer("finaliser")
        self.assertEqual(self.etat("a"), "controle")

    def test_miniature_manuelle_trop_lourde(self):
        faux_episode("a", etat="controle")
        png(TMP / "miniatures-manuelles" / "a.png", 1280, 720, extra=2 * 1024 * 1024)
        lancer("finaliser")
        self.assertEqual(self.etat("a"), "controle")

    def test_sans_miniature_ni_module_reste_en_controle(self):
        faux_episode("a", etat="controle")
        lancer("finaliser")
        self.assertEqual(self.etat("a"), "controle")

    def test_module_miniature(self):
        (TMP / "autopilot" / "miniature.py").write_text(FAKE_MINIATURE % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        faux_episode("a", etat="controle")
        lancer("finaliser")
        self.assertEqual(self.etat("a"), "pret")
        self.assertEqual(appels(), ["miniature a"])

    def test_la_manuelle_a_priorite_sur_le_module(self):
        (TMP / "autopilot" / "miniature.py").write_text(FAKE_MINIATURE % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        faux_episode("a", etat="controle")
        png(TMP / "miniatures-manuelles" / "a.png", 1280, 720)
        lancer("finaliser")
        self.assertEqual(self.etat("a"), "pret")
        self.assertEqual(appels(), [])


class Publier(Base):
    def test_module_absent(self):
        faux_episode("a", etat="pret")
        self.assertEqual(lancer("publier"), 0)
        self.assertEqual(appels(), [])

    def test_appel_en_attente(self):
        (TMP / "autopilot" / "publish").mkdir()
        (TMP / "autopilot" / "publish" / "publish.py").write_text(FAKE_PUBLISH % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        faux_episode("a", etat="pret")
        lancer("publier")
        self.assertEqual(appels(), ["publish --en-attente"])

    def test_rien_a_publier(self):
        (TMP / "autopilot" / "publish").mkdir()
        (TMP / "autopilot" / "publish" / "publish.py").write_text(FAKE_PUBLISH % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        faux_episode("a", etat="controle")
        lancer("publier")
        self.assertEqual(appels(), [])


class StockEtAlertes(Base):
    """Scénarios d'alerte écrits pour une vidéo par jour : on fixe le rythme à 1 pour qu'ils restent lisibles (le vrai rythme est testé dans StockCadence)."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(run_daily, "RYTHME_PAR_JOUR", 1)
        p.start()
        self.addCleanup(p.stop)

    def test_calcul_du_stock(self):
        for ep, etat in [("p1", "pret"), ("p2", "pret"), ("g1", "programme"), ("e1", "ecrit"),
                         ("c1", "controle"), ("pub", "publie")]:
            faux_episode(ep, etat=etat)
        faux_episode("q1", etat="quarantaine", raison="source introuvable")
        s = run_daily.calculer_stock()
        self.assertEqual(s["stock_publiable"], 3)
        self.assertEqual(s["jours_de_stock"], 3)
        self.assertFalse(s["stock_bas"])
        self.assertEqual(s["en_preparation"], 2)
        self.assertEqual(s["jours_avec_preparation"], 5)
        self.assertEqual(s["par_etat"]["publie"], 1)
        self.assertEqual(s["quarantaines"][0]["raison"], "source introuvable")

    def test_stock_sous_trois_jours_alerte_une_seule_fois(self):
        faux_episode("p1", etat="pret")
        faux_episode("p2", etat="pret")
        lancer("publier")
        lancer("publier")
        self.assertEqual([t for t, _ in self.notifs].count("La Débrouille : stock bas"), 1)
        faux_episode("p3", etat="pret")
        lancer("publier")  # stock rétabli : l'alerte est réarmée
        faux_episode("p3", etat="publie")
        lancer("publier")
        self.assertEqual([t for t, _ in self.notifs].count("La Débrouille : stock bas"), 2)

    def test_pas_d_alerte_de_stock_si_trois_jours(self):
        for i in range(3):
            faux_episode(f"p{i}", etat="pret")
        lancer("publier")
        self.assertEqual(self.notifs, [])

    def test_quarantaine_notifiee_une_fois_par_episode(self):
        for i in range(3):
            faux_episode(f"p{i}", etat="pret")
        faux_episode("q", etat="quarantaine", raison="trop long")
        lancer("publier")
        lancer("publier")
        self.assertEqual(len(self.notifs), 1)
        self.assertIn("q (trop long)", self.notifs[0][1])

    def test_jeton_youtube(self):
        for i in range(3):
            faux_episode(f"p{i}", etat="pret")
        common.write_json(common.STATE / "youtube_auth.json", {"etat": "ok", "raison": None})
        lancer("publier")
        self.assertEqual(self.notifs, [])
        common.write_json(common.STATE / "youtube_auth.json", {"etat": "a_refaire", "raison": "jeton expiré"})
        lancer("publier")
        self.assertEqual([t for t, _ in self.notifs], ["La Débrouille : YouTube"])
        self.assertTrue(common.read_json(common.STATE / "stock.json")["youtube_auth_a_renouveler"])
        lancer("publier")
        self.assertEqual(len(self.notifs), 1, "pas de nouvelle alerte avant 24 h")

    def test_redaction_silencieuse(self):
        from datetime import datetime, timedelta
        for i in range(3):
            faux_episode(f"p{i}", etat="pret")
        lancer("publier")  # pas de redaction.json : aucun avis
        self.assertEqual(self.notifs, [])
        common.write_json(common.STATE / "redaction.json", {"dernier_passage": (datetime.now() - timedelta(hours=10)).isoformat()})
        lancer("publier")
        self.assertEqual(self.notifs, [])
        common.write_json(common.STATE / "redaction.json", {"dernier_passage": (datetime.now() - timedelta(hours=40)).isoformat()})
        lancer("publier")
        lancer("publier")
        self.assertEqual([t for t, _ in self.notifs], ["La Débrouille : rédacteur silencieux"])

    def test_etat_n_envoie_rien_sans_option(self):
        faux_episode("q", etat="quarantaine", raison="x")
        lancer("etat")
        self.assertEqual(self.notifs, [])
        lancer("etat", "--alertes")
        self.assertTrue(self.notifs)

    def test_etat_tableau_et_json(self):
        faux_episode("p1", etat="pret")
        faux_episode("q", etat="quarantaine", raison="source introuvable")
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_daily.main(["etat"])
        sortie = buf.getvalue()
        for attendu in ("Stock publiable : 1 vidéo(s) = 1 jour(s)", "SOUS LE SEUIL", "q (", "source introuvable", "Disque"):
            self.assertIn(attendu, sortie)
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_daily.main(["etat", "--json"])
        self.assertEqual(json.loads(buf.getvalue())["stock_publiable"], 1)

    def test_etat_sans_aucun_episode(self):
        self.assertEqual(lancer("etat"), 0)


class Divers(Base):
    def test_rotation_des_journaux(self):
        logs = TMP / "autopilot" / "logs"
        logs.mkdir(parents=True)
        for i in range(30):
            p = logs / f"run_daily-2020{i:04d}-etat.log"
            p.write_text("x")
            os.utime(p, (1000 + i, 1000 + i))
        lancer("etat")
        restants = list(logs.glob("run_daily-*.log"))
        self.assertLessEqual(len(restants), 20)
        self.assertTrue(any(datetime_str in p.name for p in restants for datetime_str in ("-etat.log",)))

    def test_journal_horodate(self):
        lancer("etat")
        contenu = next((TMP / "autopilot" / "logs").glob("run_daily-*-etat.log")).read_text(encoding="utf-8")
        self.assertRegex(contenu, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")

    def test_repli_si_le_toast_echoue(self):
        mock.patch.stopall()
        with mock.patch.dict(os.environ, {"BDF_NOTIF_DESACTIVEE": ""}), \
                mock.patch.object(run_daily.subprocess, "run", side_effect=OSError("pas de powershell")):
            methode = run_daily.envoyer_notification("Titre", "Message")
        self.assertEqual(methode, "fichier")
        self.assertIn("Titre — Message", (common.STATE / "ALERTES.txt").read_text(encoding="utf-8"))

    def test_png_valide(self):
        p = TMP / "x.png"
        png(p, 1280, 720)
        self.assertIsNone(run_daily.verifier_png(p))
        p.write_bytes(b"pas un png du tout, vraiment pas du tout")
        self.assertEqual(run_daily.verifier_png(p), "pas un PNG")

    def test_pid_vivant(self):
        self.assertTrue(run_daily.pid_vivant(os.getpid()))
        self.assertFalse(run_daily.pid_vivant(2 ** 31 - 2))


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class StockCadence(Base):
    """Cadence du 8 novembre 2026 : 8 Shorts par jour + 3 longs par semaine."""

    def test_rythme_par_defaut(self):
        self.assertEqual(run_daily.SHORTS_PAR_JOUR, 8)
        self.assertEqual(run_daily.LONGS_PAR_SEMAINE, 3)
        self.assertAlmostEqual(run_daily.RYTHME_PAR_JOUR, 8 + 3 / 7)

    def test_un_jour_de_stock_vaut_huit_shorts_et_demi(self):
        for i in range(17):
            faux_episode(f"p{i}", etat="pret")
        s = run_daily.calculer_stock()
        self.assertEqual(s["stock_publiable"], 17)
        self.assertAlmostEqual(s["jours_de_stock"], round(17 / run_daily.RYTHME_PAR_JOUR, 2))
        self.assertTrue(s["stock_bas"])  # moins de 3 jours = moins de 26 vidéos
        self.assertEqual(s["shorts_par_jour"], 8)

    def test_stock_confortable(self):
        for i in range(30):
            faux_episode(f"p{i}", etat="pret")
        s = run_daily.calculer_stock()
        self.assertFalse(s["stock_bas"])
        self.assertGreater(s["jours_de_stock"], 3)

    def test_le_tableau_dit_la_cadence(self):
        faux_episode("p1", etat="pret")
        texte = run_daily.rendu_etat(run_daily.calculer_stock())
        self.assertIn("8 Shorts + 3 longs par semaine", texte)


FAKE_BRIQUE_CHAINE = '''
import os, sys
sys.path.insert(0, r"%(real)s")
import common
ep = sys.argv[1]
with open(common.ROOT / "appels.log", "a", encoding="utf-8") as f:
    f.write("make_en " + ep + " chaine=" + os.environ.get("BDF_CHAINE", "?") + " langue=" + os.environ.get("BDF_LANGUE", "?")
            + " ref=" + os.path.basename(os.path.dirname(os.environ.get("BDF_REF_WAV", "?"))) + "\\n")
(common.EXPORTS / ep).mkdir(parents=True, exist_ok=True)
(common.EXPORTS / ep / (ep + ".mp4")).write_bytes(b"x")
common.write_json(common.EXPORTS / ep / "qa.json", {"publiable": True, "problemes": [], "alertes": []})
common.set_status(ep, "controle")
'''


class MultiChaines(Base):
    """Plusieurs chaînes : rattachement des épisodes, activation, environnement par chaîne, isolation des échecs, stock par chaîne."""

    def setUp(self):
        super().setUp()
        self.profils()  # fr et en actives, sommeil inactive

    def profils(self, actives=("fr", "en"), **extra):
        d = TMP / "autopilot" / "chaines"
        d.mkdir(parents=True, exist_ok=True)
        base = {"fr": {}, "en": {"langue": "en", "voix": {"dossier": "voix/en"}, "frequence": {"shorts_par_jour": 2, "longs_par_semaine": 0}},
                "sommeil": {"format": "sommeil", "frequence": {"shorts_par_jour": 1, "longs_par_semaine": 0}}}
        for ident, plus in {**base, **extra}.items():
            p = {"id": ident, "nom": f"Chaîne {ident.upper()}", "langue": "fr", "format": "business", "active": ident in actives,
                 "jeton_fichier": "token.json" if ident == "fr" else f"token-{ident}.json", **plus}
            (d / f"{ident}.json").write_text(json.dumps(p), encoding="utf-8")
        (TMP / "autopilot" / "voix" / "en").mkdir(parents=True, exist_ok=True)
        (TMP / "autopilot" / "voix" / "en" / "ref.wav").write_bytes(b"RIFF")

    def ep(self, ep_id, chaine, etat="ecrit", mode=None):
        faux_episode(ep_id, etat=etat, mode=mode)
        common.set_status(ep_id, etat, chaine_id=chaine)

    # ---- rattachement et migration
    def test_un_episode_sans_chaine_appartient_a_la_chaine_par_defaut(self):
        shutil.rmtree(TMP / "autopilot" / "chaines")
        faux_episode("ancien", etat="pret")
        self.assertEqual(common.chaine_de("ancien"), "fr")
        self.assertEqual(list(chaines.charger_profils()), ["fr"])  # sans dossier de profils : la chaîne historique seule, active
        self.assertTrue(chaines.est_active("fr"))
        self.assertEqual(run_daily.calculer_stock()["par_chaine"]["fr"]["stock_publiable"], 1)

    def test_migration_non_destructive_et_idempotente(self):
        faux_episode("a", etat="pret")
        faux_episode("b", etat="ecrit")
        common.set_status("a", "pret", youtube={"video_id": None, "url": None, "visibilite": None, "publie_a": None}, tentatives=1)
        avant = {e: common.read_json(common.ep_dir(e) / "status.json") for e in ("a", "b") if (common.ep_dir(e) / "status.json").exists()}
        essai = chaines.migrer(dry_run=True)
        self.assertEqual(essai["rattaches"], ["a"])  # b n'a pas de status.json : on n'en crée pas
        self.assertEqual({e: common.read_json(common.ep_dir(e) / "status.json") for e in avant}, avant)  # dry-run : rien de changé
        res = chaines.migrer()
        self.assertEqual(res["rattaches"], ["a"])
        apres = common.read_json(common.ep_dir("a") / "status.json")
        self.assertEqual(apres["chaine_id"], "fr")
        self.assertEqual({k: v for k, v in apres.items() if k != "chaine_id"}, avant["a"])  # tout le reste est intact
        self.assertEqual(chaines.migrer(), {"rattaches": [], "deja_rattaches": 1, "dry_run": False})
        self.assertFalse((common.ep_dir("b") / "status.json").exists())

    def test_set_status_conserve_la_chaine(self):
        self.ep("x", "en", "ecrit")
        common.set_status("x", "voix")
        common.set_status("x", "controle")
        self.assertEqual(common.chaine_de("x"), "en")
        self.assertEqual(common.list_episodes(chaine="en"), ["x"])
        self.assertEqual(common.list_episodes(chaine="fr"), [])

    # ---- activation
    def test_une_chaine_inactive_est_ignoree_par_toutes_les_commandes(self):
        self.profils(actives=("fr",))
        (TMP / "autopilot" / "miniature.py").write_text(FAKE_MINIATURE % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        self.ep("en-1", "en", "ecrit")
        self.ep("en-2", "en", "controle")
        self.ep("fr-1", "fr", "ecrit")
        lancer("fabriquer")
        lancer("finaliser")
        self.assertEqual((self.etat("en-1"), self.etat("en-2")), ("ecrit", "controle"))
        self.assertEqual(self.etat("fr-1"), "pret")
        self.assertEqual(appels(), ["make_short fr-1 ", "miniature fr-1"])  # rien n'est fabriqué ni miniaturé pour la chaîne inactive

    def test_publier_n_appelle_pas_le_publieur_pour_une_chaine_inactive(self):
        self.profils(actives=("fr",))
        (TMP / "autopilot" / "publish").mkdir()
        (TMP / "autopilot" / "publish" / "publish.py").write_text(FAKE_PUBLISH % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        self.ep("en-3", "en", "pret")
        lancer("publier")
        self.assertEqual(appels(), [])

    def test_profil_invalide_jamais_active(self):
        self.profils(en={"langue": "en", "voix": {"dossier": None}})  # chaîne active en anglais sans voix propre : refusée
        self.ep("en-1", "en", "ecrit")
        p = chaines.charger_profils()["en"]
        self.assertFalse(p["valide"])
        self.assertTrue(any("sans voix propre" in e for e in p["erreurs"]))
        lancer("fabriquer")
        self.assertEqual(self.etat("en-1"), "ecrit")
        self.assertIn("en", run_daily.calculer_stock()["par_chaine"])
        self.assertFalse(run_daily.calculer_stock()["par_chaine"]["en"]["active"])

    def test_validation_des_profils(self):
        ok = chaines.normaliser({"id": "histoire", "langue": "fr", "format": "histoire"})
        self.assertEqual(chaines.valider_profil(ok, {"fr", "histoire"}), [])
        mauvais = [
            ({"id": "Mauvais Id"}, "identifiant invalide"),
            ({"id": "a", "format": "inconnu"}, "format"),
            ({"id": "a", "jeton_fichier": "../token.json"}, "jeton_fichier"),
            ({"id": "a", "jeton_fichier": "client_secret.json"}, "jeton_fichier"),
            ({"id": "a", "source": {"chaine": "a"}}, "source"),
            ({"id": "a", "publication": {"quota": {"plafond_envois": 999}}}, "non surchargeable"),
            ({"id": "a", "voix": {"dossier": "../../secrets"}}, "voix.dossier"),
            ({"id": "a", "briques": {"fabrique": "/etc/passwd"}}, "briques.fabrique"),
        ]
        for brut, attendu in mauvais:
            erreurs = chaines.valider_profil(chaines.normaliser(brut), {"a", "fr"})
            self.assertTrue(any(attendu in e for e in erreurs), (brut, erreurs))

    # ---- environnement et briques par chaîne
    def test_chaque_chaine_recoit_sa_voix_sa_langue_et_sa_brique(self):
        self.profils(en={"langue": "en", "voix": {"dossier": "voix/en"}, "briques": {"fabrique": "make_en.py"}})
        (TMP / "autopilot" / "make_en.py").write_text(FAKE_BRIQUE_CHAINE % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        self.ep("fr-1", "fr", "ecrit")
        self.ep("en-1", "en", "ecrit")
        lancer("fabriquer")
        self.assertEqual(sorted(appels()), ["make_en en-1 chaine=en langue=en ref=en", "make_short fr-1 "])
        self.assertEqual((self.etat("fr-1"), self.etat("en-1")), ("controle", "controle"))

    def test_une_brique_hors_de_autopilot_est_refusee(self):
        p = chaines.normaliser({"id": "x", "briques": {"fabrique": "../../evil.py"}})
        defaut = TMP / "autopilot" / "make_short.py"
        self.assertEqual(chaines.brique(p, "fabrique", defaut), defaut)

    # ---- isolation
    def test_une_chaine_en_echec_ne_bloque_pas_les_autres(self):
        self.ep("en-1", "en", "ecrit", mode="crash")
        self.ep("en-2", "en", "ecrit", mode="quarantaine")
        self.ep("fr-1", "fr", "ecrit")
        self.assertEqual(lancer("fabriquer"), 0)
        self.assertEqual((self.etat("en-1"), self.etat("en-2")), ("quarantaine", "quarantaine"))
        self.assertEqual(self.etat("fr-1"), "controle")
        # les quarantaines de chaque chaîne sont comptées chez elle
        pc = common.read_json(common.STATE / "stock.json")["par_chaine"]
        self.assertEqual((pc["en"]["par_etat"]["quarantaine"], pc["fr"]["par_etat"]["quarantaine"]), (2, 0))

    def test_tour_de_role_entre_chaines_avec_max(self):
        for i in (1, 2, 3):
            self.ep(f"a{i}", "fr", "ecrit")
            self.ep(f"b{i}", "en", "ecrit")
        lancer("fabriquer", "--max", "2")
        self.assertEqual(sorted(e.split()[1] for e in appels()), ["a1", "b1"])  # sans tour de rôle : a1 et a2, et la chaîne en attendrait
        lancer("fabriquer", "--max", "2", "--chaine", "en")
        self.assertEqual(sorted(e.split()[1] for e in appels()), ["a1", "b1", "b2", "b3"])
        self.assertEqual([self.etat(f"a{i}") for i in (1, 2, 3)], ["controle", "ecrit", "ecrit"])

    def test_option_chaine_limite_le_traitement(self):
        self.ep("a1", "fr", "ecrit")
        self.ep("b1", "en", "ecrit")
        lancer("fabriquer", "--chaine", "en")
        self.assertEqual((self.etat("a1"), self.etat("b1")), ("ecrit", "controle"))

    def test_le_publieur_est_appele_une_fois_pour_toutes_les_chaines(self):
        (TMP / "autopilot" / "publish").mkdir()
        (TMP / "autopilot" / "publish" / "publish.py").write_text(FAKE_PUBLISH % {"real": REAL_AUTOPILOT}, encoding="utf-8")
        self.ep("a1", "fr", "pret")
        self.ep("b1", "en", "pret")
        lancer("publier")
        self.assertEqual(appels(), ["publish --en-attente"])

    # ---- stock et alertes par chaîne
    def test_stock_par_chaine_et_global_des_chaines_actives(self):
        self.profils(actives=("fr", "en"))
        for i in range(30):
            self.ep(f"f{i}", "fr", "pret")
        for i in range(4):
            self.ep(f"e{i}", "en", "pret")
        for i in range(5):
            self.ep(f"s{i}", "sommeil", "pret")  # chaîne inactive : ne compte pas dans le global
        s = run_daily.calculer_stock()
        pc = s["par_chaine"]
        self.assertEqual((pc["fr"]["stock_publiable"], pc["en"]["stock_publiable"], pc["sommeil"]["stock_publiable"]), (30, 4, 5))
        self.assertEqual(s["stock_publiable"], 34)
        self.assertEqual(sorted(s["chaines_actives"]), ["en", "fr"])
        self.assertEqual(pc["en"]["jours_de_stock"], 2.0)  # 4 vidéos à 2 par jour
        self.assertEqual(s["jours_de_stock"], 2.0)         # la chaîne la plus juste donne le ton
        self.assertTrue(s["stock_bas"] and pc["en"]["stock_bas"] and not pc["fr"]["stock_bas"])
        self.assertFalse(pc["sommeil"]["active"])
        self.assertFalse(pc["sommeil"]["stock_bas"])  # pas d'alerte pour une chaîne inactive

    def test_alerte_de_stock_bas_nomme_la_chaine_et_n_est_envoyee_qu_une_fois(self):
        for i in range(40):
            self.ep(f"f{i}", "fr", "pret")
        self.ep("e0", "en", "pret")
        lancer("etat", "--alertes")
        lancer("etat", "--alertes")
        titres = [t for t, _ in self.notifs]
        self.assertEqual(titres.count("Chaîne EN : stock bas"), 1)
        self.assertNotIn("Chaîne FR : stock bas", titres)
        cles = common.read_json(common.STATE / "alertes.json")["envoyees"]
        self.assertIn("stock-bas:en", cles)
        self.assertNotIn("stock-bas", cles)  # la clé de la chaîne par défaut reste « stock-bas »

    def test_jeton_manquant_d_une_chaine_active_alerte_une_fois(self):
        for i in range(40):
            self.ep(f"f{i}", "fr", "pret")
            self.ep(f"e{i}", "en", "pret")
        common.write_json(common.STATE / "jetons.json", {"fr": {"connecte": True}, "en": {"connecte": False}})
        lancer("etat", "--alertes")
        lancer("etat", "--alertes")
        s = common.read_json(common.STATE / "stock.json")
        self.assertTrue(s["par_chaine"]["en"]["auth_a_renouveler"])
        self.assertFalse(s["par_chaine"]["fr"]["auth_a_renouveler"])
        self.assertTrue(s["youtube_auth_a_renouveler"])
        self.assertEqual([t for t, _ in self.notifs].count("Chaîne EN : YouTube"), 1)
        self.assertIn("CONNECTER-UNE-CHAINE", next(m for t, m in self.notifs if t == "Chaîne EN : YouTube"))

    def test_etat_auth_propre_a_chaque_chaine(self):
        for i in range(40):
            self.ep(f"f{i}", "fr", "pret")
            self.ep(f"e{i}", "en", "pret")
        common.write_json(common.STATE / "youtube_auth-en.json", {"etat": "a_refaire", "raison": "jeton expiré"})
        s = run_daily.calculer_stock()
        self.assertTrue(s["par_chaine"]["en"]["auth_a_renouveler"])
        self.assertFalse(s["par_chaine"]["fr"]["auth_a_renouveler"])

    def test_tableau_etat_liste_les_chaines(self):
        self.ep("a", "fr", "pret")
        texte = run_daily.rendu_etat(run_daily.calculer_stock())
        self.assertIn("Chaînes :", texte)
        self.assertIn("en", texte)
        self.assertIn("inactive", texte)

    def test_les_quarantaines_de_chaines_inactives_n_alertent_pas(self):
        self.profils(actives=("fr",))
        faux_episode("e0", etat="quarantaine", raison="raison")
        common.set_status("e0", "quarantaine", "raison", chaine_id="en")
        self.assertEqual(run_daily.calculer_stock()["quarantaines"], [])

    def test_tiktok_seulement_pour_la_chaine_par_defaut(self):
        self.ep("a", "fr", "pret")
        self.ep("b", "en", "pret")
        self.assertTrue(common.tiktok_pour("a"))
        self.assertFalse(common.tiktok_pour("b"))

    def test_frequence(self):
        fr = chaines.profil("fr")
        self.assertEqual(chaines.frequence(fr, 8, 3), (8, 3))
        p = chaines.normaliser({"id": "q", "publication": {"heures_shorts": ["10:00", "18:00"], "shorts_par_creneau": 2, "jours_longs": [1, 4]}})
        self.assertEqual(chaines.frequence(p, 8, 3), (4, 2))
        self.assertEqual(chaines.frequence(chaines.normaliser({"id": "z", "frequence": {"shorts_par_jour": 0, "longs_par_semaine": 4}}), 8, 3), (0, 4))


if __name__ == "__main__":
    unittest.main()
