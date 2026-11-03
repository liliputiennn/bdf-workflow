"""Orchestrateur quotidien du workflow YouTube Business (voir CONTRAT.md et README.md).

Usage :
  python autopilot/run_daily.py fabriquer [--id ID] [--max N] [--sans-voix] [--dry-run]
  python autopilot/run_daily.py finaliser [--id ID] [--dry-run]
  python autopilot/run_daily.py publier [--dry-run]
  python autopilot/run_daily.py etat [--json] [--alertes] [--taches]

Chaque sous-commande est idempotente et reprenable ; une erreur sur un épisode n'arrête jamais les autres.
Bibliothèque standard seulement.
"""
import argparse
import contextlib
import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

RYTHME_PAR_JOUR = 1            # vidéos publiées par jour
SEUIL_STOCK_JOURS = 3
SEUIL_DISQUE_GO = 3.0
MAX_TENTATIVES = 2
RENOTIF_H = 24
REDACTION_MAX_H = 36
MAX_LOGS = 20
TIMEOUT_FABRIQUE_MIN = 90
TIMEOUT_MINIATURE_MIN = 15
TIMEOUT_PUBLICATION_MIN = 30
BUDGET_FABRIQUE_MIN = 180
RUN_LOCK_TTL_S = 6 * 3600
ETATS_FABRIQUE = ("ecrit", "voix", "rendu")
log = logging.getLogger("bdf")


# ---------------------------------------------------------------- chemins (lus à l'appel : BDF_ROOT)
def autopilot_dir() -> Path:
    return common.ROOT / "autopilot"


def logs_dir() -> Path:
    return autopilot_dir() / "logs"


def python_exe() -> str:
    exe = Path(sys.executable)
    console = exe.with_name("python.exe")
    return str(console if console.exists() else exe)


# ---------------------------------------------------------------- journaux
def init_logs(cmd: str) -> Path:
    logs_dir().mkdir(parents=True, exist_ok=True)
    path = logs_dir() / f"run_daily-{datetime.now():%Y%m%d}-{cmd}.log"
    for h in list(log.handlers):
        log.removeHandler(h)
        with contextlib.suppress(Exception):
            h.close()
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S")
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if sys.stdout is not None:
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)
    rotation_logs()
    return path


def rotation_logs() -> None:
    fichiers = sorted(logs_dir().glob("run_daily-*.log"), key=lambda p: (p.stat().st_mtime, p.name))
    for p in fichiers[:-MAX_LOGS]:
        with contextlib.suppress(OSError):
            p.unlink()


# ---------------------------------------------------------------- disque
def disque_libre_go() -> float:
    fake = os.environ.get("BDF_DISQUE_LIBRE_GO")
    if fake:
        return float(fake)
    return shutil.disk_usage(common.ROOT.anchor or str(common.ROOT)).free / 1024 ** 3


# ---------------------------------------------------------------- verrous (reprise après plantage)
def pid_vivant(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
        k32.CloseHandle(ctypes.c_void_p(h))
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def liberer_si_orphelin(path: Path) -> bool:
    """Supprime un verrou dont le processus propriétaire n'existe plus (en plus de la péremption par l'âge)."""
    try:
        pid = int(path.read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return False
    if pid == os.getpid() or pid_vivant(pid):
        return False
    with contextlib.suppress(OSError):
        path.unlink()
        log.warning("verrou orphelin repris : %s (processus %s disparu)", path.name, pid)
        return True
    return False


@contextlib.contextmanager
def verrou(path: Path, ttl_s: int = common.LOCK_TTL_S, wait_s: float = 0.0):
    liberer_si_orphelin(path)
    with common.file_lock(path, ttl_s=ttl_s, wait_s=wait_s):
        if path.name == ".lock" and path.parent.parent == common.EPISODES:
            # verrou d'un épisode : les briques appelées (miniature, publication...) ne le reprennent pas (voir common.episode_lock)
            cle, avant = "BDF_VERROU_EPISODES", os.environ.get("BDF_VERROU_EPISODES", "")
            os.environ[cle] = "|".join(x for x in (avant, path.parent.name) if x)
            try:
                yield
            finally:
                os.environ[cle] = avant
        else:
            yield


@contextlib.contextmanager
def eveil():
    """Demande à Windows de ne pas mettre en veille tant que le processus travaille (pas un réglage système)."""
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)  # CONTINUOUS | SYSTEM_REQUIRED
    try:
        yield
    finally:
        if sys.platform == "win32":
            with contextlib.suppress(Exception):
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


# ---------------------------------------------------------------- notifications
def alertes_fichier() -> Path:
    return common.STATE / "ALERTES.txt"


def _ecrire_alerte_fichier(titre: str, message: str) -> None:
    p = alertes_fichier()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        lignes = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
        lignes.append(f"{common.now()}  {titre} — {message}")
        p.write_text("\n".join(lignes[-300:]) + "\n", encoding="utf-8")
    except OSError:
        pass


_TOAST_PS = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$n = $x.GetElementsByTagName('text')
$n.Item(0).AppendChild($x.CreateTextNode($env:BDF_T)) | Out-Null
$n.Item(1).AppendChild($x.CreateTextNode($env:BDF_M)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($x)
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
"""


def _sans_fenetre() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def envoyer_notification(titre: str, message: str) -> str:
    """Journal d'alertes toujours écrit ; puis toast PowerShell, repli `msg`. Renvoie la méthode qui a servi."""
    _ecrire_alerte_fichier(titre, message)
    log.warning("ALERTE %s — %s", titre, message)
    if os.environ.get("BDF_NOTIF_DESACTIVEE") or sys.platform != "win32":
        return "fichier"
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _TOAST_PS],
            env={**os.environ, "BDF_T": titre, "BDF_M": message},
            capture_output=True, timeout=30, creationflags=_sans_fenetre(),
        )
        if r.returncode == 0:
            return "toast"
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        r = subprocess.run(["msg", "*", "/TIME:600", f"{titre} — {message}"], capture_output=True,
                           timeout=15, creationflags=_sans_fenetre())
        if r.returncode == 0:
            return "msg"
    except (OSError, subprocess.SubprocessError):
        pass
    return "fichier"


def _etat_alertes() -> dict:
    return common.read_json(common.STATE / "alertes.json", None) or {"envoyees": {}}


def notifier_si_nouveau(cle: str, titre: str, message: str, renotif_h: float | None = RENOTIF_H) -> bool:
    """Envoie l'alerte si `cle` n'a pas déjà été notifiée (ou depuis plus de `renotif_h` heures). None = une seule fois."""
    etat = _etat_alertes()
    vue = etat["envoyees"].get(cle)
    if vue:
        if renotif_h is None:
            return False
        if datetime.now() - datetime.fromisoformat(vue) < timedelta(hours=renotif_h):
            return False
    envoyer_notification(titre, message)
    etat["envoyees"][cle] = common.now()
    common.write_json(common.STATE / "alertes.json", etat)
    return True


def lever_cles(garder) -> None:
    """Oublie les alertes dont la condition a disparu (`garder(cle)` faux), pour re-notifier si elle revient."""
    etat = _etat_alertes()
    restantes = {k: v for k, v in etat["envoyees"].items() if garder(k)}
    if restantes != etat["envoyees"]:
        etat["envoyees"] = restantes
        common.write_json(common.STATE / "alertes.json", etat)


# ---------------------------------------------------------------- stock
def auth_youtube_presente() -> bool:
    """`youtube_auth.json` est écrit par le publieur : {"etat": "ok"} = tout va bien, autre chose = jeton à renouveler."""
    p = common.STATE / "youtube_auth.json"
    if not p.exists():
        return False
    contenu = common.read_json(p, None)
    return not (isinstance(contenu, dict) and contenu.get("etat") == "ok")


def redaction_en_retard() -> tuple[str | None, bool]:
    """`state/redaction.json` (écrit par writer/stock.py besoin) : (dernier_passage, plus de 36 h). Fichier absent : pas d'avis."""
    d = (common.read_json(common.STATE / "redaction.json", None) or {}).get("dernier_passage")
    if not d:
        return None, False
    try:
        return d, datetime.now() - datetime.fromisoformat(d) > timedelta(hours=REDACTION_MAX_H)
    except ValueError:
        return d, True


def calculer_stock() -> dict:
    par_etat = {e: 0 for e in common.ETATS}
    ids = {e: [] for e in common.ETATS}
    quarantaines = []
    for ep in common.list_episodes():
        st = common.get_status(ep)
        etat = st.get("etat", "ecrit")
        if etat not in par_etat:
            continue
        par_etat[etat] += 1
        ids[etat].append(ep)
        if etat == "quarantaine":
            quarantaines.append({"id": ep, "raison": st.get("raison"), "maj": st.get("maj")})
    publiable = par_etat["pret"] + par_etat["programme"]
    prep = sum(par_etat[e] for e in ("ecrit", "voix", "rendu", "controle"))
    jours = publiable / RYTHME_PAR_JOUR
    libre = disque_libre_go()
    passage, retard = redaction_en_retard()
    return {
        "maj": common.now(),
        "rythme_par_jour": RYTHME_PAR_JOUR,
        "par_etat": par_etat,
        "ids_par_etat": {e: v for e, v in ids.items() if v},
        "stock_publiable": publiable,
        "jours_de_stock": jours,
        "en_preparation": prep,
        "jours_avec_preparation": (publiable + prep) / RYTHME_PAR_JOUR,
        "date_rupture": (datetime.now().date() + timedelta(days=int(jours))).isoformat(),
        "stock_bas": jours < SEUIL_STOCK_JOURS,
        "quarantaines": quarantaines,
        "disque_libre_go": round(libre, 2),
        "disque_bas": libre < SEUIL_DISQUE_GO,
        "youtube_auth_a_renouveler": auth_youtube_presente(),
        "redaction_dernier_passage": passage,
        "redaction_en_retard": retard,
        "claude_bloque": (common.STATE / "claude_blocked.json").exists(),
    }


def rafraichir_stock(alerter: bool = True, ecrire: bool = True) -> dict:
    stock = calculer_stock()
    if ecrire:
        common.write_json(common.STATE / "stock.json", stock)
    if alerter:
        envoyer_alertes(stock)
    return stock


def envoyer_alertes(stock: dict) -> None:
    jours = stock["jours_de_stock"]
    if stock["stock_bas"]:
        notifier_si_nouveau("stock-bas", "Bureau des Faits : stock bas",
                            f"{jours:g} jour(s) de vidéos prêtes (seuil {SEUIL_STOCK_JOURS}). "
                            f"{stock['en_preparation']} en préparation.")
    nouvelles = []
    for q in stock["quarantaines"]:
        cle = f"quarantaine:{q['id']}:{q['maj']}"
        if cle not in _etat_alertes()["envoyees"]:
            nouvelles.append((cle, q))
    if nouvelles:
        resume = " ; ".join(f"{q['id']} ({(q['raison'] or '?')[:90]})" for _, q in nouvelles[:5])
        if len(nouvelles) > 5:
            resume += f" … (+{len(nouvelles) - 5})"
        envoyer_notification("Bureau des Faits : quarantaine", resume)
        etat = _etat_alertes()
        for cle, _ in nouvelles:
            etat["envoyees"][cle] = common.now()
        common.write_json(common.STATE / "alertes.json", etat)
    if stock["youtube_auth_a_renouveler"]:
        notifier_si_nouveau("youtube-auth", "Bureau des Faits : YouTube",
                            "Jeton YouTube à renouveler (voir autopilot/state/youtube_auth.json).")
    if stock["disque_bas"]:
        notifier_si_nouveau("disque-bas", "Bureau des Faits : disque presque plein",
                            f"{stock['disque_libre_go']:.1f} Go libres (seuil {SEUIL_DISQUE_GO:g} Go) : rendu suspendu.")
    if stock["redaction_en_retard"]:
        notifier_si_nouveau("redaction-retard", "Bureau des Faits : rédacteur silencieux",
                            f"Dernier passage du rédacteur : {stock['redaction_dernier_passage']} (plus de {REDACTION_MAX_H} h).")
    quarantaine_cles = {f"quarantaine:{q['id']}:{q['maj']}" for q in stock["quarantaines"]}
    lever_cles(lambda k: (k in quarantaine_cles) if k.startswith("quarantaine:") else (
        (stock["stock_bas"] if k == "stock-bas" else
         stock["youtube_auth_a_renouveler"] if k == "youtube-auth" else
         stock["disque_bas"] if k == "disque-bas" else
         stock["redaction_en_retard"] if k == "redaction-retard" else True)))


# ---------------------------------------------------------------- appel des briques
def lancer(cmd: list, timeout_s: float, env_extra: dict | None = None) -> tuple[int, str]:
    """Lance une brique, renvoie (code, sortie). Délai dépassé : arbre de processus tué, code 124."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "BDF_LOCK_PARENT": "1", **(env_extra or {})}
    log.info("$ %s", " ".join(map(str, cmd)))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", cwd=str(common.ROOT), env=env, creationflags=_sans_fenetre())
    try:
        sortie, _ = p.communicate(timeout=timeout_s)
        return p.returncode, sortie or ""
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=_sans_fenetre())
        else:
            p.kill()
        try:
            sortie, _ = p.communicate(timeout=30)
        except Exception:
            sortie = ""
        return 124, (sortie or "") + f"\n[délai de {timeout_s / 60:g} min dépassé : processus arrêté]"


def _queue(texte: str, n: int) -> str:
    return "\n".join(texte.strip().splitlines()[-n:])


def _ecrire_tentatives(ep: str, n: int) -> None:
    st = common.get_status(ep)
    st["tentatives"] = n
    st["maj"] = common.now()
    common.write_json(common.ep_dir(ep) / "status.json", st)


def _raison_qa(ep: str) -> str:
    qa = common.read_json(common.EXPORTS / ep / "qa.json", None) or {}
    morceaux = list(qa.get("problemes") or []) + list(qa.get("alertes") or [])
    return ("contrôle qualité : " + " ; ".join(morceaux))[:500] if morceaux else "code retour 2 sans raison dans qa.json"


def _ecrire_trace(ep: str, nom: str, rc: int, sortie: str) -> Path:
    p = common.ep_dir(ep) / f"trace-{nom}.log"
    with contextlib.suppress(OSError):
        p.write_text(f"{common.now()} code {rc}\n{_queue(sortie, 200)[-20000:]}\n", encoding="utf-8")
    return p


def pause_entre_essais() -> None:
    time.sleep(float(os.environ.get("BDF_PAUSE_S", "30")))


def appeler_brique(ep: str, nom: str, cmd: list, timeout_s: float, apres_succes) -> str:
    """Appelle une brique avec 2 tentatives. Renvoie 'ok' ou 'quarantaine'.
    Code 2 : la brique a posé la quarantaine (sinon on la pose). Autre échec : trace + nouvel essai, puis quarantaine."""
    faites = common.get_status(ep).get("tentatives", 0) or 0
    rc, sortie = 1, ""
    while faites < MAX_TENTATIVES:
        faites += 1
        rc, sortie = lancer(cmd, timeout_s)
        log.info("[%s] %s : code %s\n%s", ep, nom, rc, _queue(sortie, 15))
        if common.get_status(ep)["etat"] == "quarantaine":
            return "quarantaine"
        if rc == 0:
            apres_succes(ep)
            return "ok" if common.get_status(ep)["etat"] != "quarantaine" else "quarantaine"
        if rc == 2:
            common.set_status(ep, "quarantaine", _raison_qa(ep))
            return "quarantaine"
        _ecrire_trace(ep, nom, rc, sortie)
        _ecrire_tentatives(ep, faites)
        log.warning("[%s] %s : échec inattendu (code %s), essai %s/%s", ep, nom, rc, faites, MAX_TENTATIVES)
        if faites < MAX_TENTATIVES:
            pause_entre_essais()
    derniere = next((l.strip() for l in reversed(sortie.splitlines()) if l.strip()), "aucune sortie")
    common.set_status(ep, "quarantaine",
                      f"{nom} : échec inattendu après {faites} essais (code {rc}) : {derniere[:200]} — trace : trace-{nom}.log")
    return "quarantaine"


def _apres_fabrique(ep: str) -> None:
    """La fabrique doit avoir posé `controle` ; sinon on constate le résultat à sa place."""
    st = common.get_status(ep)
    if st["etat"] in ("controle", "pret", "programme", "publie", "quarantaine"):
        pass
    else:
        mp4 = common.EXPORTS / ep / f"{ep}.mp4"
        qa = common.read_json(common.EXPORTS / ep / "qa.json", None) or {}
        if mp4.exists() and qa.get("publiable"):
            common.set_status(ep, "controle")
            log.info("[%s] statut passé à « controle » par l'orchestrateur (la fabrique ne l'avait pas fait)", ep)
        else:
            common.set_status(ep, "quarantaine", "fabrique terminée (code 0) sans vidéo ou rapport qualité exploitable")
    if common.get_status(ep).get("tentatives"):
        _ecrire_tentatives(ep, 0)


def _apres_miniature(ep: str) -> None:
    st = common.get_status(ep)
    if st["etat"] == "controle":
        if (common.ep_dir(ep) / "miniature.png").exists():
            common.set_status(ep, "pret")
            log.info("[%s] statut passé à « pret » par l'orchestrateur (miniature présente)", ep)
        else:
            common.set_status(ep, "quarantaine", "miniature : code 0 mais aucun miniature.png produit")
    if common.get_status(ep).get("tentatives"):
        _ecrire_tentatives(ep, 0)


# ---------------------------------------------------------------- sous-commandes
def candidats(etats, seul: str | None) -> list:
    out = [ep for ep in common.list_episodes() if common.get_status(ep).get("etat") in etats]
    return [ep for ep in out if seul in (None, ep)]


def est_long(ep: str) -> bool:
    """Un long (16:9, chapitres) a un `episode-long.json` ; son `episode.json` n'est qu'une vue à plat pour la miniature et la publication."""
    return (common.ep_dir(ep) / "episode-long.json").exists()


def fabriquer_long(ep: str, a) -> str:
    """Fabrique un long avec `make_long.py` : voix par reprises (verrou GPU pris par la brique), rendu 16:9, découpage en Shorts.
    Code 3 = « à reprendre » (voix inachevée, GPU occupé) : ce n'est pas un échec, le prochain passage continue."""
    brique = autopilot_dir() / "make_long.py"
    if not brique.exists():
        log.error("[%s] make_long.py introuvable", ep)
        return "ignores"
    cmd = [python_exe(), str(brique), ep, "--budget-min", str(a.budget_long_min)] + (["--sans-voix"] if a.sans_voix else [])
    rc, sortie = lancer(cmd, (a.budget_long_min + 150) * 60)
    log.info("[%s] long : code %s\n%s", ep, rc, _queue(sortie, 15))
    if common.get_status(ep)["etat"] == "quarantaine":
        return "quarantaine"
    if rc == 0:
        _apres_fabrique(ep)
        return "ok" if common.get_status(ep)["etat"] != "quarantaine" else "quarantaine"
    if rc == 2:
        common.set_status(ep, "quarantaine", _raison_qa(ep))
        return "quarantaine"
    if rc == 3:
        log.info("[%s] long : à reprendre au prochain passage (voix inachevée ou GPU occupé)", ep)
        return "ignores"
    faites = (common.get_status(ep).get("tentatives", 0) or 0) + 1
    _ecrire_trace(ep, "long", rc, sortie)
    _ecrire_tentatives(ep, faites)
    if faites >= MAX_TENTATIVES:
        derniere = next((l.strip() for l in reversed(sortie.splitlines()) if l.strip()), "aucune sortie")
        common.set_status(ep, "quarantaine", f"long : échec inattendu après {faites} essais (code {rc}) : {derniere[:200]}")
        return "quarantaine"
    log.warning("[%s] long : échec inattendu (code %s), essai %s/%s au prochain passage", ep, rc, faites, MAX_TENTATIVES)
    return "erreurs"


def cmd_fabriquer(a) -> dict:
    brique = autopilot_dir() / "make_short.py"
    bilan = {"ok": 0, "quarantaine": 0, "ignores": 0, "erreurs": 0}
    todo = candidats(ETATS_FABRIQUE, a.id)
    if not todo:
        log.info("fabriquer : aucun épisode à fabriquer")
        return bilan
    libre = disque_libre_go()
    if libre < SEUIL_DISQUE_GO:
        log.error("fabriquer : disque presque plein (%.1f Go libres < %g) : rendu sauté pour %s épisode(s)",
                  libre, SEUIL_DISQUE_GO, len(todo))
        bilan["ignores"] = len(todo)
        return bilan
    if not brique.exists():
        log.error("fabriquer : %s introuvable", brique)
        bilan["ignores"] = len(todo)
        return bilan
    debut = time.time()
    traites = 0
    for ep in todo:
        if a.max is not None and traites >= a.max:
            log.info("fabriquer : limite de %s épisode(s) atteinte", a.max)
            break
        if time.time() - debut > a.budget_min * 60:
            log.info("fabriquer : budget de temps épuisé (%s min), reprise au prochain passage", a.budget_min)
            break
        if a.dry_run:
            log.info("[dry-run] fabriquerait %s (état %s)", ep, common.get_status(ep)["etat"])
            continue
        if est_long(ep):  # la brique du long prend elle-même le verrou GPU, par reprises
            try:
                with verrou(common.ep_dir(ep) / ".lock", wait_s=0):
                    traites += 1
                    bilan[fabriquer_long(ep, a)] += 1
            except TimeoutError:
                log.info("[%s] verrou d'épisode occupé : ignoré pour ce passage", ep)
                bilan["ignores"] += 1
            except Exception:
                log.error("[%s] erreur inattendue de l'orchestrateur :\n%s", ep, traceback.format_exc())
                bilan["erreurs"] += 1
            continue
        cmd = [python_exe(), str(brique), ep] + (["--sans-voix"] if a.sans_voix else [])
        try:
            with verrou(common.STATE / "gpu.lock", wait_s=a.attente_gpu):
                try:
                    with verrou(common.ep_dir(ep) / ".lock", wait_s=0):
                        traites += 1
                        res = appeler_brique(ep, "fabrique", cmd, a.timeout_min * 60, _apres_fabrique)
                        bilan[res] += 1
                except TimeoutError:
                    log.info("[%s] verrou d'épisode occupé : ignoré pour ce passage", ep)
                    bilan["ignores"] += 1
        except TimeoutError:
            restants = todo[todo.index(ep):]
            log.warning("GPU occupé (gpu.lock) : %s épisode(s) reportés au prochain passage", len(restants))
            bilan["ignores"] += len(restants)
            break
        except Exception:
            log.error("[%s] erreur inattendue de l'orchestrateur :\n%s", ep, traceback.format_exc())
            bilan["erreurs"] += 1
    return bilan


def verifier_png(p: Path) -> str | None:
    """Renvoie None si la miniature manuelle est valide (PNG 1280x720, ≤ 2 Mo), sinon le défaut."""
    try:
        if p.stat().st_size > 2 * 1024 * 1024:
            return "plus de 2 Mo"
        with p.open("rb") as f:
            tete = f.read(24)
    except OSError as e:
        return str(e)
    if tete[:8] != b"\x89PNG\r\n\x1a\n":
        return "pas un PNG"
    l, h = int.from_bytes(tete[16:20], "big"), int.from_bytes(tete[20:24], "big")
    return None if (l, h) == (1280, 720) else f"dimensions {l}x{h} au lieu de 1280x720"


def cmd_finaliser(a) -> dict:
    brique = autopilot_dir() / "miniature.py"
    manuelles = common.ROOT / "miniatures-manuelles"
    bilan = {"ok": 0, "quarantaine": 0, "ignores": 0, "erreurs": 0}
    for ep in candidats(("controle",), a.id):
        if a.dry_run:
            log.info("[dry-run] finaliserait %s", ep)
            continue
        try:
            with verrou(common.ep_dir(ep) / ".lock", wait_s=0):
                manuelle = manuelles / f"{ep}.png"
                if manuelle.exists():
                    defaut = verifier_png(manuelle)
                    if defaut is None:
                        tmp = common.ep_dir(ep) / "miniature.png.tmp"
                        shutil.copyfile(manuelle, tmp)
                        os.replace(tmp, common.ep_dir(ep) / "miniature.png")
                        common.set_status(ep, "pret")
                        log.info("[%s] miniature manuelle utilisée -> pret", ep)
                        bilan["ok"] += 1
                        continue
                    log.warning("[%s] miniature manuelle refusée (%s) : repli sur la miniature automatique", ep, defaut)
                if brique.exists():
                    cmd = [python_exe(), str(brique), ep]
                    res = appeler_brique(ep, "miniature", cmd, TIMEOUT_MINIATURE_MIN * 60, _apres_miniature)
                    bilan[res] += 1
                else:
                    log.info("[%s] en attente : ni miniature manuelle ni miniature.py", ep)
                    bilan["ignores"] += 1
        except TimeoutError:
            log.info("[%s] verrou d'épisode occupé : ignoré pour ce passage", ep)
            bilan["ignores"] += 1
        except Exception:
            log.error("[%s] erreur inattendue de l'orchestrateur :\n%s", ep, traceback.format_exc())
            bilan["erreurs"] += 1
    return bilan


def cmd_publier(a) -> dict:
    brique = autopilot_dir() / "publish" / "publish.py"
    bilan = {"appel": False, "code": None}
    if not brique.exists():
        log.info("publier : %s absent, rien à faire", brique)
        return bilan
    a_publier = candidats(("pret", "programme"), None)
    if not a_publier:
        log.info("publier : aucun épisode pret/programme")
        return bilan
    if a.dry_run:
        log.info("[dry-run] publierait : %s", ", ".join(a_publier))
        return bilan
    rc, sortie = lancer([python_exe(), str(brique), "--en-attente"], TIMEOUT_PUBLICATION_MIN * 60)
    log.log(logging.INFO if rc == 0 else logging.WARNING, "publish.py : code %s\n%s", rc, _queue(sortie, 25))
    bilan.update(appel=True, code=rc)
    return bilan


def cmd_tiktok(a) -> dict:
    """Envoie les Shorts prêts dans la boîte de réception TikTok (tiktok/envoi.py) et prévient quand il y a quelque chose à publier.
    Code 3 de la brique = connexion TikTok à refaire : on le dit une fois, les paquets de secours sont préparés quand même."""
    brique = autopilot_dir() / "tiktok" / "envoi.py"
    bilan = {"appel": False, "code": None, "envoyes": 0}
    if not brique.exists():
        log.error("tiktok : %s introuvable", brique)
        return bilan
    cmd = [python_exe(), str(brique)] + (["--dry-run"] if a.dry_run else [])
    rc, sortie = lancer(cmd, 30 * 60)
    log.log(logging.INFO if rc == 0 else logging.WARNING, "tiktok/envoi.py : code %s\n%s", rc, _queue(sortie, 25))
    bilan.update(appel=True, code=rc)
    if a.dry_run:
        return bilan
    try:
        res = json.loads(sortie[sortie.index("{"):sortie.rindex("}") + 1])
    except ValueError:
        res = {}
    n = len(res.get("envoyes") or [])
    bilan["envoyes"] = n
    if n:
        envoyer_notification("Bureau des Faits : TikTok",
                             f"{n} vidéo(s) t'attendent dans ta boîte de réception TikTok : ouvre l'application, colle la légende, touche Publier.")
    if rc == 3:
        notifier_si_nouveau("tiktok-auth", "Bureau des Faits : TikTok",
                            "Connexion TikTok à refaire (python autopilot/tiktok/auth.py). Les paquets à déposer à la main sont dans exports-tiktok.")
    return bilan


def rendu_etat(s: dict) -> str:
    L = [f"BUREAU DES FAITS — état du stock ({s['maj']})", ""]
    L.append("Épisodes par état :")
    for e in common.ETATS:
        n = s["par_etat"][e]
        ids = s["ids_par_etat"].get(e, [])
        L.append(f"  {e:<11}{n:>3}  {', '.join(ids[:6])}{' …' if len(ids) > 6 else ''}")
    L.append("")
    marque = "  ⚠ SOUS LE SEUIL" if s["stock_bas"] else ""
    L.append(f"Stock publiable : {s['stock_publiable']} vidéo(s) = {s['jours_de_stock']:g} jour(s) à {s['rythme_par_jour']}/jour{marque}")
    L.append(f"En préparation  : {s['en_preparation']} (soit {s['jours_avec_preparation']:g} jour(s) si tout passe)")
    L.append(f"Rupture prévue  : {s['date_rupture']} (sans nouvelle vidéo)")
    L.append(f"Disque          : {s['disque_libre_go']:.1f} Go libres{'  ⚠ SOUS LE SEUIL, rendu suspendu' if s['disque_bas'] else ''}")
    L.append(f"Jeton YouTube   : {'À RENOUVELER (state/youtube_auth.json)' if s['youtube_auth_a_renouveler'] else 'rien à signaler'}")
    L.append(f"Rédacteur       : dernier passage {s['redaction_dernier_passage'] or 'inconnu'}{'  ⚠ PLUS DE 36 h' if s['redaction_en_retard'] else ''}")
    if s["claude_bloque"]:
        L.append("Rédacteur Claude: bloqué (state/claude_blocked.json)")
    L.append("")
    if s["quarantaines"]:
        L.append("Quarantaines :")
        for q in s["quarantaines"]:
            L.append(f"  - {q['id']} ({q['maj']}) : {q['raison']}")
    else:
        L.append("Quarantaines : aucune")
    return "\n".join(L)


def etat_taches() -> str:
    try:
        r = subprocess.run(["schtasks", "/query", "/fo", "csv", "/nh"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30, creationflags=_sans_fenetre())
    except (OSError, subprocess.SubprocessError) as e:
        return f"schtasks indisponible : {e}"
    lignes = [l.replace('"', "").split(",") for l in r.stdout.splitlines() if "BDF-" in l]
    if not lignes:
        return "Tâches planifiées : aucune tâche BDF-* installée"
    return "Tâches planifiées :\n" + "\n".join(f"  {c[0].lstrip(chr(92))}  prochaine : {c[1] if len(c) > 1 else '?'}  état : {c[2] if len(c) > 2 else '?'}"
                                              for c in lignes)


def cmd_etat(a) -> dict:
    stock = rafraichir_stock(alerter=a.alertes)
    log.info("etat : stock publiable %s, en préparation %s, quarantaines %s, disque %.1f Go",
             stock["stock_publiable"], stock["en_preparation"], len(stock["quarantaines"]), stock["disque_libre_go"])
    if a.json:
        print(json.dumps(stock, ensure_ascii=False, indent=1))
    else:
        print(rendu_etat(stock))
        if a.taches:
            print()
            print(etat_taches())
    return stock


# ---------------------------------------------------------------- CLI
def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Orchestrateur quotidien du workflow Business")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fabriquer", help="ecrit -> controle (voix + rendu), un épisode à la fois sous gpu.lock")
    f.add_argument("--id")
    f.add_argument("--max", type=int)
    f.add_argument("--sans-voix", action="store_true")
    f.add_argument("--attente-gpu", type=float, default=120, help="secondes d'attente du verrou GPU")
    f.add_argument("--budget-min", type=float, default=BUDGET_FABRIQUE_MIN)
    f.add_argument("--timeout-min", type=float, default=TIMEOUT_FABRIQUE_MIN)
    f.add_argument("--budget-long-min", type=float, default=90.0, help="durée maximale d'une reprise de voix pour un long (format 16:9)")
    f.add_argument("--dry-run", action="store_true")
    n = sub.add_parser("finaliser", help="controle -> pret (miniature)")
    n.add_argument("--id")
    n.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("publier", help="appelle publish.py --en-attente")
    p.add_argument("--dry-run", action="store_true")
    t = sub.add_parser("tiktok", help="envoie les Shorts prêts dans la boîte de réception TikTok (tiktok/envoi.py)")
    t.add_argument("--dry-run", action="store_true")
    e = sub.add_parser("etat", help="tableau du stock")
    e.add_argument("--json", action="store_true")
    e.add_argument("--alertes", action="store_true", help="envoie aussi les notifications")
    e.add_argument("--taches", action="store_true", help="affiche les tâches planifiées BDF-*")
    return ap


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    init_logs(a.cmd)
    if a.cmd == "etat":
        for h in list(log.handlers):  # le tableau (ou le JSON) est seul sur la console, le journal garde la trace
            if not isinstance(h, logging.FileHandler):
                log.removeHandler(h)
        try:
            cmd_etat(a)
            return 0
        except Exception:
            log.error("etat : %s", traceback.format_exc())
            return 1
    fonction = {"fabriquer": cmd_fabriquer, "finaliser": cmd_finaliser, "publier": cmd_publier, "tiktok": cmd_tiktok}[a.cmd]
    try:
        with verrou(common.STATE / f"run_{a.cmd}.lock", ttl_s=RUN_LOCK_TTL_S, wait_s=0), eveil():
            log.info("=== %s (dry-run=%s) ===", a.cmd, getattr(a, "dry_run", False))
            try:
                bilan = fonction(a)
                log.info("bilan %s : %s", a.cmd, bilan)
            except Exception:
                log.error("%s : erreur inattendue :\n%s", a.cmd, traceback.format_exc())
            if not a.dry_run:
                try:  # une vidéo publiée partout n'a plus besoin de ses gros fichiers : on libère le disque
                    liberes = common.liberer_tout_publie()
                    if liberes:
                        log.info("disque libéré après publication : %s", liberes)
                except Exception:
                    log.error("libération du disque : %s", traceback.format_exc())
                rafraichir_stock()
        return 0
    except TimeoutError:
        log.info("%s : une autre instance est déjà en cours, rien à faire", a.cmd)
        return 0
    except Exception:
        log.error("%s : plantage de l'orchestrateur :\n%s", a.cmd, traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
