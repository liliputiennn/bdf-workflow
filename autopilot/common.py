"""Briques communes du workflow (voir CONTRAT.md) : statuts atomiques, verrous, verrou GPU.

Bibliothèque standard seulement, utilisable depuis Python 3.11 à 3.14.
"""
import contextlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

# BDF_ROOT redirige tout (épisodes, exports, état) vers un autre dossier : sert aux tests, sans effet en production.
ROOT = Path(os.environ["BDF_ROOT"]).resolve() if os.environ.get("BDF_ROOT") else Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes-b"
EXPORTS = ROOT / "exports-b"
STATE = ROOT / "autopilot" / "state"
ETATS = ["ecrit", "voix", "rendu", "controle", "pret", "programme", "publie", "quarantaine"]
LOCK_TTL_S = 3 * 3600


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, data) -> None:
    """Écriture atomique : fichier temporaire puis renommage."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def ep_dir(ep_id: str) -> Path:
    return EPISODES / ep_id


def get_status(ep_id: str) -> dict:
    return read_json(ep_dir(ep_id) / "status.json", None) or {
        "etat": "ecrit", "maj": now(), "raison": None, "tentatives": 0,
        "youtube": {"video_id": None, "url": None, "visibilite": None, "publie_a": None},
    }


def set_status(ep_id: str, etat: str, raison: str | None = None, **extra) -> dict:
    """Fait avancer un épisode. `quarantaine` exige une raison."""
    if etat not in ETATS:
        raise ValueError(f"état inconnu : {etat}")
    if etat == "quarantaine" and not raison:
        raise ValueError("une quarantaine exige une raison")
    st = get_status(ep_id)
    st.update({"etat": etat, "maj": now(), "raison": raison, **extra})
    write_json(ep_dir(ep_id) / "status.json", st)
    if etat == "publie":
        try:
            liberer_disque(ep_id)
        except Exception:  # libérer du disque ne doit jamais faire échouer une publication
            pass
    return st


# ---------------------------------------------------------------- libération du disque après publication
GROS_FICHIERS = (".mp4", ".mov", ".webm", ".wav")
DOSSIERS_VOIX = ("cache",)  # cache de voix de l'épisode, regénérable


def tiktok_pour(ep_id: str) -> bool:
    """Le compte TikTok (un seul) reçoit-il les Shorts de cette chaîne ? Par défaut : seulement ceux de la chaîne par défaut (champ `tiktok` du profil)."""
    ch = chaine_de(ep_id)
    voulu = (read_json(ROOT / "autopilot" / "chaines" / f"{ch}.json", {}) or {}).get("tiktok")
    return ch == CHAINE_DEFAUT if voulu is None else bool(voulu)


def _tiktok_actif() -> bool:
    return (ROOT / "autopilot" / "secrets" / "tiktok_token.json").exists()


def _tiktok_envoye(ep_id: str) -> bool:
    v = ((read_json(STATE / "tiktok.json", {}) or {}).get("envoyes") or {}).get(ep_id) or {}
    return v.get("statut") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE") and not v.get("a_reessayer")


def peut_liberer(ep_id: str) -> bool:
    """Vrai si la vidéo est publiée partout où elle doit l'être et si plus rien ne doit la relire.

    - YouTube : état `publie` et identifiant de vidéo connu ;
    - Short : si TikTok est configuré (jeton présent), le Short doit y avoir été envoyé ;
    - long : tous ses Shorts doivent avoir déjà leur propre voix (découpage fait)."""
    st = get_status(ep_id)
    if st.get("etat") != "publie" or not (st.get("youtube") or {}).get("video_id"):
        return False
    est_long = (ep_dir(ep_id) / "episode-long.json").exists()
    if not est_long and _tiktok_actif() and tiktok_pour(ep_id) and not _tiktok_envoye(ep_id):
        return False
    if est_long:
        for s in (read_json(EXPORTS / ep_id / "qa.json", {}) or {}).get("shorts", []):
            if not (ep_dir(s) / "voice.wav").exists() and not (ep_dir(s) / "nettoyage.json").exists():
                return False
    return True


def liberer_disque(ep_id: str, dry_run: bool = False) -> list[str]:
    """Supprime les gros fichiers regénérables (vidéo rendue, voix, cache de voix) d'un épisode publié.

    Garde tout le reste : textes, faits, publication, statut, rapport qualité, miniatures. Renvoie les chemins supprimés."""
    import shutil
    if not peut_liberer(ep_id) or (ep_dir(ep_id) / "nettoyage.json").exists() and not dry_run:
        return []
    cibles = []
    for base in (EXPORTS / ep_id, ep_dir(ep_id)):
        if base.is_dir():
            cibles += [p for p in base.iterdir() if p.is_file() and p.suffix.lower() in GROS_FICHIERS]
    cibles += [ep_dir(ep_id) / d for d in DOSSIERS_VOIX if (ep_dir(ep_id) / d).is_dir()]
    sup = []
    for p in cibles:
        if not (str(p.resolve()).startswith(str(EPISODES.resolve())) or str(p.resolve()).startswith(str(EXPORTS.resolve()))):
            continue  # sécurité : jamais en dehors des dossiers d'épisodes
        sup.append(str(p))
        if not dry_run:
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    if sup and not dry_run:
        write_json(ep_dir(ep_id) / "nettoyage.json", {"maj": now(), "supprimes": [Path(s).name for s in sup]})
    return sup


def liberer_tout_publie(dry_run: bool = False) -> dict:
    """Passe sur tous les épisodes publiés dont le nettoyage n'a pas encore été fait (rattrape l'envoi TikTok tardif)."""
    out = {}
    for ep in list_episodes("publie"):
        sup = liberer_disque(ep, dry_run)
        if sup:
            out[ep] = len(sup)
    return out


CHAINE_DEFAUT = "fr"  # chaîne des épisodes sans `chaine_id` dans leur status.json (voir chaines.py)


def chaine_de(ep_id: str) -> str:
    """Chaîne à laquelle appartient un épisode (`chaine_id` du status.json ; à défaut la chaîne historique)."""
    return str((read_json(ep_dir(ep_id) / "status.json", {}) or {}).get("chaine_id") or CHAINE_DEFAUT)


def list_episodes(etat: str | None = None, chaine: str | None = None) -> list[str]:
    """Identifiants d'épisodes (triés), éventuellement filtrés par état et par chaîne. Ignore les dossiers `_*`."""
    out = []
    for d in sorted(EPISODES.glob("*")):
        if d.is_dir() and not d.name.startswith("_") and (d / "episode.json").exists():
            if etat is None or get_status(d.name)["etat"] == etat:
                if chaine is None or chaine_de(d.name) == chaine:
                    out.append(d.name)
    return out


@contextlib.contextmanager
def file_lock(path: Path, ttl_s: int = LOCK_TTL_S, wait_s: float = 0.0):
    """Verrou par création exclusive. Un verrou plus vieux que `ttl_s` est considéré comme périmé et repris."""
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + wait_s
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {now()}".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > ttl_s:
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.time() >= deadline:
                raise TimeoutError(f"verrou occupé : {path.name}")
            time.sleep(2)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


@contextlib.contextmanager
def episode_lock(ep_id: str, **kw):
    """Verrou par épisode, transmis aux sous-processus : si le processus parent (l'orchestrateur) tient déjà le verrou
    de cet épisode, la brique qu'il appelle (miniature, publication...) ne le reprend pas et ne se bloque donc pas elle-même."""
    cle = "BDF_VERROU_EPISODES"
    tenus = [x for x in os.environ.get(cle, "").split("|") if x]
    if ep_id in tenus:
        yield
        return
    with file_lock(ep_dir(ep_id) / ".lock", **kw):
        os.environ[cle] = "|".join(tenus + [ep_id])
        try:
            yield
        finally:
            os.environ[cle] = "|".join(tenus)


def gpu_lock(**kw):
    """Un seul travail de voix à la fois sur la RTX 3050 (4 Go)."""
    return file_lock(STATE / "gpu.lock", **kw)
