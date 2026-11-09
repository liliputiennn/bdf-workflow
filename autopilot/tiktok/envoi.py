"""File d'attente TikTok : envoie les Shorts prêts dans la boîte de réception TikTok, et prépare un paquet de secours.

    python autopilot/tiktok/envoi.py                 # envoie les Shorts prêts (4 au plus par 24 h) et met à jour les statuts
    python autopilot/tiktok/envoi.py --dry-run       # montre ce qui serait envoyé, sans rien envoyer
    python autopilot/tiktok/envoi.py --paquet        # prépare seulement exports-tiktok/<id>/ (vidéo + légende) à déposer à la main

Ce que TikTok permet (documentation vérifiée le 2026-11-03) : tant que ton application n'est pas auditée, la publication directe
reste privée ; on utilise donc l'envoi dans la boîte de réception (portée `video.upload`). TikTok t'y envoie une notification :
tu ouvres l'application, tu colles la légende et tu touches « Publier » (environ 30 secondes par vidéo). Rien n'est publié sans toi.
Limite : 5 envois en attente par 24 h au plus ; on en envoie 4.
Un Short éligible : épisode 9:16 (pas un long), état pret/programme/publie, vidéo et rapport qualité « publiable ».
Sans jeton, le programme prépare quand même les paquets et sort avec le code 3.
Codes retour : 0 = fait, 3 = connexion TikTok à refaire (`auth.py`), 1 = erreur.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent))
import client as C  # noqa: E402
import common  # noqa: E402

MAX_PAR_24H = 4
ETATS_ELIGIBLES = ("pret", "programme", "publie")
FICHIER_ETAT = common.STATE / "tiktok.json"
DOSSIER_PAQUETS = common.ROOT / "exports-tiktok"
LEGENDE_MAX = 2000
EN_COURS = ("PROCESSING_UPLOAD", "SEND_TO_USER_INBOX")


def lire_etat() -> dict:
    d = common.read_json(FICHIER_ETAT, {}) or {}
    d.setdefault("envoyes", {})
    return d


def ecrire_etat(d: dict) -> None:
    d["maj"] = common.now()
    common.write_json(FICHIER_ETAT, d)


def est_long(ep: str) -> bool:
    return (common.ep_dir(ep) / "episode-long.json").exists()


def video(ep: str) -> Path:
    return common.EXPORTS / ep / f"{ep}.mp4"


def eligible(ep: str) -> bool:
    if est_long(ep) or common.get_status(ep).get("etat") not in ETATS_ELIGIBLES or not video(ep).exists():
        return False
    if not common.tiktok_pour(ep):
        return False  # le compte TikTok n'est pas celui de cette chaîne
    qa = common.read_json(common.EXPORTS / ep / "qa.json", None) or {}
    return bool(qa.get("publiable"))


def legende(ep: str) -> str:
    """Titre + hashtags tirés de publication.json ; la voix de synthèse est signalée (TikTok demande d'étiqueter les contenus générés par IA)."""
    pub = common.read_json(common.ep_dir(ep) / "publication.json", {}) or {}
    titre = str(pub.get("titre") or (common.read_json(common.ep_dir(ep) / "episode.json", {}) or {}).get("titre") or ep).strip()
    tags = [t for t in (pub.get("tags") or []) if isinstance(t, str) and t.strip()][:4]
    hashtags = ["#" + "".join(c for c in t.title() if c.isalnum()) for t in tags]
    if "#business" not in [h.lower() for h in hashtags]:
        hashtags.append("#business")
    texte = f"{titre}\n\n{' '.join(hashtags)}".strip()
    return texte[:LEGENDE_MAX]


def candidats(deja: dict) -> list[str]:
    ids = [ep for ep in common.list_episodes() if eligible(ep) and (ep not in deja or deja[ep].get("a_reessayer"))]
    return sorted(ids, key=lambda e: common.get_status(e).get("maj", ""))


def preparer_paquet(ep: str) -> Path:
    d = DOSSIER_PAQUETS / ep
    d.mkdir(parents=True, exist_ok=True)
    if not (d / f"{ep}.mp4").exists():
        shutil.copy2(video(ep), d / f"{ep}.mp4")
    (d / "legende.txt").write_text(legende(ep) + "\n\nÀ cocher dans TikTok : « Contenu généré par IA ».\n", encoding="utf-8")
    return d


def envois_24h(etat: dict, maintenant=time.time) -> int:
    n = 0
    for v in etat["envoyes"].values():
        t = v.get("envoye_ts")
        if isinstance(t, (int, float)) and maintenant() - t < 86400:
            n += 1
    return n


def mettre_a_jour_statuts(tt, etat: dict) -> int:
    """Demande à TikTok où en sont les envois en cours ; un échec temporaire (`internal`) sera réessayé."""
    changes = 0
    for ep, v in etat["envoyes"].items():
        if v.get("statut") not in EN_COURS:
            continue
        try:
            s = tt.statut(v["publish_id"])
        except C.ErreurApi as e:
            v["erreur"] = str(e)[:200]
            continue
        nouveau = s.get("status") or v["statut"]
        if nouveau != v["statut"]:
            changes += 1
            v["statut"] = nouveau
            if nouveau == "FAILED":
                v["raison"] = s.get("fail_reason", "")
                if v["raison"] in ("internal", "video_pull_failed"):
                    v["a_reessayer"] = True
    return changes


def envoyer_file(tt, max_n: int, seul: str | None, dry_run: bool, afficher=print, maintenant=time.time) -> dict:
    etat = lire_etat()
    bilan = {"envoyes": [], "ignores": 0, "statuts_changes": 0, "dans_24h": 0}
    if not dry_run:
        bilan["statuts_changes"] = mettre_a_jour_statuts(tt, etat)
    place = max(0, min(max_n, MAX_PAR_24H - envois_24h(etat, maintenant)))
    todo = [e for e in candidats(etat["envoyes"]) if seul in (None, e)]
    for ep in todo:
        if place <= 0:
            bilan["ignores"] += 1
            continue
        if dry_run:
            afficher(f"[dry-run] enverrait {ep}")
            bilan["envoyes"].append(ep)
            place -= 1
            continue
        try:
            with common.episode_lock(ep):
                afficher(f"envoi de {ep}")
                pid = tt.envoyer(video(ep), afficher)
        except TimeoutError:
            bilan["ignores"] += 1
            continue
        etat["envoyes"][ep] = {"publish_id": pid, "envoye_a": common.now(), "envoye_ts": maintenant(),
                               "statut": "PROCESSING_UPLOAD", "legende": legende(ep)}
        ecrire_etat(etat)  # on sauvegarde après chaque envoi : une panne ne le fait pas refaire
        bilan["envoyes"].append(ep)
        place -= 1
    if not dry_run:
        ecrire_etat(etat)
    bilan["dans_24h"] = envois_24h(etat, maintenant)
    return bilan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--paquet", action="store_true", help="prépare seulement les paquets à déposer à la main")
    ap.add_argument("--max", type=int, default=MAX_PAR_24H)
    ap.add_argument("--id")
    a = ap.parse_args(argv)
    etat = lire_etat()
    todo = [e for e in candidats(etat["envoyes"]) if a.id in (None, e)]
    sortie = {"candidats": todo}
    auth_ok = True
    tt = None
    if not a.paquet:
        try:
            cl = C.charger_client()
            tt = C.TikTok(C.jeton_valide(cl))
        except C.ErreurAuth as e:
            auth_ok = False
            sortie["auth"] = str(e)
    if tt is not None:
        try:
            sortie.update(envoyer_file(tt, a.max, a.id, a.dry_run))
        except C.ErreurAuth as e:
            auth_ok = False
            sortie["auth"] = str(e)
        except C.ErreurReseau as e:
            sortie["reseau"] = str(e)
        except C.ErreurApi as e:
            sortie["erreur"] = str(e)
    if not auth_ok or a.paquet:
        if not a.dry_run:
            sortie["paquets"] = [str(preparer_paquet(ep)) for ep in todo]
    if sortie.get("jours_avant_renouvellement") is None:
        j = C.jours_avant_expiration_renouvellement()
        if j is not None:
            sortie["jours_avant_renouvellement"] = round(j, 1)
    print(json.dumps(sortie, ensure_ascii=False, indent=1))
    if not auth_ok:
        return 3
    return 1 if ("erreur" in sortie) else 0


if __name__ == "__main__":
    sys.exit(main())
