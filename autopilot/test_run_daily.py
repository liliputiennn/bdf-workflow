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


if __name__ == "__main__":
    unittest.main()
