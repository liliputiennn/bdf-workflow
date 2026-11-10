"""File d'attente TikTok : envoie les Shorts prêts sur TikTok (un compte par chaîne) et prépare un paquet de secours.

    python autopilot/tiktok/envoi.py                 # envoie les Shorts prêts (4 au plus par 24 h et par compte) et met à jour les statuts
    python autopilot/tiktok/envoi.py --dry-run       # montre ce qui serait envoyé, sans rien envoyer
    python autopilot/tiktok/envoi.py --paquet        # prépare seulement exports-tiktok/<id>/ (vidéo + légende) à déposer à la main

Quelles chaînes envoient quoi : le champ `tiktok` du profil de chaîne (autopilot/chaines/<id>.json) — absent = seulement la chaîne
par défaut ; `true`/`false` ; ou un objet {actif, mode, audit_confirme, jeton_fichier, hashtags, visibilite, max_par_24h, ia}.
Un jeton par compte : `python autopilot/tiktok/auth.py --chaine <id>` (voir CONNECTER-TIKTOK.md).

Deux moteurs (par chaîne, réglage `tiktok.moteur`) : « boite » (défaut, ci-dessous) ou « planificateur » (planificateur.py : un service
tiers déjà audité par TikTok publie EN PUBLIC ; clé dans autopilot/secrets/upload_post.json ; voir OPTIONS-PUBLICATION.md).

Deux modes (par chaîne) :
  - « boite » (défaut) : brouillon dans la boîte de réception TikTok (portée `video.upload`). TikTok notifie ; tu colles la légende et
    tu touches « Publier » (environ 30 secondes par vidéo). Rien n'est publié sans toi.
  - « direct » : publication directe (portée `video.publish`). Prise en compte SEULEMENT si le profil contient aussi
    `"audit_confirme": true` (ton réglage explicite, une fois l'application auditée par TikTok) ; sinon on reste sur « boite ».
    Avant l'audit, TikTok force la visibilité « privée » ; on ne compte donc jamais dessus.
Limite : 5 envois en attente par 24 h et par compte au plus ; on en envoie 4 (publication directe : 15 au plus par compte et par jour).
Un Short éligible : épisode 9:16 (pas un long), état pret/programme/publie, vidéo et rapport qualité « publiable », chaîne qui envoie.
Sans jeton pour une chaîne, le programme prépare quand même ses paquets et sort avec le code 3 (les autres chaînes sont traitées).
Codes retour : 0 = fait, 3 = connexion TikTok à refaire (`auth.py --chaine <id>`), 1 = erreur.
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
import planificateur as PL  # noqa: E402
import common  # noqa: E402

MAX_PAR_24H = 4
ETATS_ELIGIBLES = ("pret", "programme", "publie")
FICHIER_ETAT = common.STATE / "tiktok.json"
DOSSIER_PAQUETS = common.ROOT / "exports-tiktok"
LEGENDE_MAX = 2000
EN_COURS = ("PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "SEND_TO_USER_INBOX")


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


def chaine_de(ep: str) -> str:
    return common.chaine_de(ep)


def eligible(ep: str) -> bool:
    if est_long(ep) or common.get_status(ep).get("etat") not in ETATS_ELIGIBLES or not video(ep).exists():
        return False
    if not common.tiktok_pour(ep):
        return False  # le profil de cette chaîne n'envoie pas sur TikTok
    qa = common.read_json(common.EXPORTS / ep / "qa.json", None) or {}
    return bool(qa.get("publiable"))


MAX_HASHTAGS = 5  # TikTok recommande 3 à 5 mots-clés ; plus nuit à la lisibilité et ne rapporte rien


def hashtag(texte: str) -> str | None:
    """« gagner de l'argent avec l'IA » -> None (trop long) ; « services IA » -> #servicesia ; accents et ponctuation retirés."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(texte).lower()).encode("ascii", "ignore").decode()
    s = "".join(c for c in s if c.isalnum())
    return f"#{s}" if 3 <= len(s) <= 16 else None


def legende(ep: str) -> str:
    """Titre + hashtags de publication.json (+ hashtags du profil de la chaîne) ; la voix de synthèse est signalée
    (TikTok demande d'étiqueter les contenus générés par IA)."""
    pub = common.read_json(common.ep_dir(ep) / "publication.json", {}) or {}
    titre = str(pub.get("titre") or (common.read_json(common.ep_dir(ep) / "episode.json", {}) or {}).get("titre") or ep).strip()
    hashtags = []
    for t in (pub.get("tags") or []):  # 2 mots-clés du sujet au plus, courts, en minuscules, comme les gens les cherchent
        h = hashtag(t)
        if h and h not in hashtags and len(hashtags) < 2:
            hashtags.append(h)
    for h in common.tiktok_reglage(chaine_de(ep))["hashtags"]:
        if h.lower() not in [x.lower() for x in hashtags]:
            hashtags.append(h.lower())
    hashtags = hashtags[:MAX_HASHTAGS]
    texte = f"{titre}\n\n{' '.join(hashtags)}".strip()
    return texte[:LEGENDE_MAX]


def candidats(deja: dict) -> list[str]:
    ids = [ep for ep in common.list_episodes() if eligible(ep) and (ep not in deja or deja[ep].get("a_reessayer"))]
    return sorted(ids, key=lambda e: common.get_status(e).get("maj", ""))


def _paris(ts: float):
    from datetime import datetime, timedelta, timezone
    try:
        from zoneinfo import ZoneInfo
        return datetime.fromtimestamp(ts, ZoneInfo("Europe/Paris"))
    except Exception:  # pas de base de fuseaux : heure d'hiver de Paris
        return datetime.fromtimestamp(ts, timezone(timedelta(hours=1)))


def prochain_creneau(etat: dict, creneaux: list[str], chaine: str, maintenant=time.time, horizon_h: int = 48) -> str | None:
    """Premier créneau libre (heure de Paris, ISO sans fuseau) au moins 20 min dans le futur, pas déjà pris par la chaîne ; None si
    rien dans l'horizon. Un envoi par créneau : jamais plusieurs vidéos en même temps."""
    from datetime import timedelta
    pris = {v.get("programme_pour") for v in etat["envoyes"].values() if (v.get("chaine") or common.CHAINE_DEFAUT) == chaine}
    t0 = _paris(maintenant() + 20 * 60)
    for j in range(0, horizon_h // 24 + 2):
        jour = (t0 + timedelta(days=j)).date()
        for c in creneaux:
            h, m = map(int, c.split(":"))
            cand = t0.replace(year=jour.year, month=jour.month, day=jour.day, hour=h, minute=m, second=0, microsecond=0)
            iso = cand.strftime("%Y-%m-%dT%H:%M:%S")
            if cand >= t0 and iso not in pris and (cand - t0).total_seconds() <= horizon_h * 3600:
                return iso
    return None


def preparer_paquet(ep: str) -> Path:
    d = DOSSIER_PAQUETS / ep
    d.mkdir(parents=True, exist_ok=True)
    if not (d / f"{ep}.mp4").exists():
        shutil.copy2(video(ep), d / f"{ep}.mp4")
    (d / "legende.txt").write_text(legende(ep) + "\n\nÀ cocher dans TikTok : « Contenu généré par IA ».\n", encoding="utf-8")
    return d


def envois_24h(etat: dict, maintenant=time.time, chaine: str | None = None) -> int:
    """Envois des dernières 24 h. La limite de TikTok est par compte, donc par chaîne ; sans `chaine` : tous."""
    n = 0
    for v in etat["envoyes"].values():
        if chaine is not None and (v.get("chaine") or common.CHAINE_DEFAUT) != chaine:
            continue
        t = v.get("envoye_ts")
        if isinstance(t, (int, float)) and maintenant() - t < 86400:
            n += 1
    return n


def _client_de(tt, chaine: str):
    """`tt` : un client unique (valable pour toutes les chaînes) ou un dict {chaîne: client}."""
    return tt.get(chaine) if isinstance(tt, dict) else tt


def mettre_a_jour_statuts(tt, etat: dict) -> int:
    """Demande à TikTok où en sont les envois en cours ; un échec temporaire (`internal`) sera réessayé."""
    changes = 0
    for ep, v in etat["envoyes"].items():
        if v.get("statut") not in EN_COURS:
            continue
        client = _client_de(tt, v.get("chaine") or common.CHAINE_DEFAUT)
        if client is None:
            continue
        try:
            s = client.statut(v["publish_id"])
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
    """Envoie les Shorts prêts, chaîne par chaîne (un compte, donc une limite de 24 h, par chaîne).

    `tt` : un client TikTok ou un dict {chaîne: client}. Une chaîne sans client est mise de côté (`sans_client`)."""
    etat = lire_etat()
    bilan = {"envoyes": [], "ignores": 0, "statuts_changes": 0, "dans_24h": 0, "sans_client": []}
    if not dry_run:
        bilan["statuts_changes"] = mettre_a_jour_statuts(tt, etat)
    todo = [e for e in candidats(etat["envoyes"]) if seul in (None, e)]
    places: dict[str, int] = {}
    for ep in todo:
        ch = chaine_de(ep)
        reg = common.tiktok_reglage(ch)
        client = _client_de(tt, ch)
        if client is None:
            if ch not in bilan["sans_client"]:
                bilan["sans_client"].append(ch)
            continue
        if ch not in places:
            places[ch] = max(0, min(max_n, reg["max_par_24h"] - envois_24h(etat, maintenant, ch)))
        if places[ch] <= 0:
            bilan["ignores"] += 1
            continue
        mode = reg["mode"]
        if dry_run:
            afficher(f"[dry-run] enverrait {ep} ({ch}, {mode})")
            bilan["envoyes"].append(ep)
            places[ch] -= 1
            continue
        try:
            with common.episode_lock(ep):
                afficher(f"envoi de {ep} ({ch}, {mode})")
                if mode == "planificateur":
                    quand = prochain_creneau(etat, reg["creneaux"], ch, maintenant)
                    if quand is None:
                        bilan["ignores"] += 1
                        continue
                    pid = client.publier(video(ep), legende(ep), reg, afficher, quand=quand)
                elif mode == "direct":
                    info = client.post_info_direct(legende(ep), reg["visibilite"], reg["ia"])
                    pid = client.envoyer(video(ep), afficher, post_info=info)
                else:
                    pid = client.envoyer(video(ep), afficher)
        except TimeoutError:
            bilan["ignores"] += 1
            continue
        etat["envoyes"][ep] = {"publish_id": pid, "envoye_a": common.now(), "envoye_ts": maintenant(), "chaine": ch, "mode": mode,
                               "statut": "PROCESSING_UPLOAD", "legende": legende(ep), "programme_pour": quand if mode == "planificateur" else None}
        ecrire_etat(etat)  # on sauvegarde après chaque envoi : une panne ne le fait pas refaire
        bilan["envoyes"].append(ep)
        places[ch] -= 1
    if not dry_run:
        ecrire_etat(etat)
    bilan["dans_24h"] = envois_24h(etat, maintenant)
    return bilan


def clients_pour(chaines, charger_client=None, jeton_valide=None, appel=None) -> tuple[dict, dict, dict]:
    """({chaîne: client}, {chaîne: raison du refus}, {chaîne: panne réseau}) : un jeton par compte ; une chaîne sans jeton
    valide (ou en panne) n'empêche pas les autres."""
    charger_client, jeton_valide, appel = charger_client or C.charger_client, jeton_valide or C.jeton_valide, appel or C.appel_http
    clients, refus, pannes = {}, {}, {}
    for ch in chaines:
        reg = common.tiktok_reglage(ch)
        if reg["moteur"] == "planificateur":  # service tiers déjà audité : une clé d'accès, pas de jeton TikTok chez nous
            try:
                clients[ch] = PL.charger(reg, appel)
            except C.ErreurAuth as e:
                refus[ch] = str(e)
            continue
        try:
            cl = charger_client()
            jeton = jeton_valide(cl, C.chemin_jeton(common.tiktok_reglage(ch)["jeton_fichier"]), appel)
            clients[ch] = C.TikTok(jeton, appel)
        except C.ErreurAuth as e:
            refus[ch] = str(e)
        except C.ErreurReseau as e:
            pannes[ch] = str(e)
    return clients, refus, pannes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--paquet", action="store_true", help="prépare seulement les paquets à déposer à la main")
    ap.add_argument("--max", type=int, default=None, help="plafond par passage (défaut : seulement la limite de 24 h de la chaîne)")
    ap.add_argument("--id")
    a = ap.parse_args(argv)
    etat = lire_etat()
    todo = [e for e in candidats(etat["envoyes"]) if a.id in (None, e)]
    sortie = {"candidats": todo}
    en_cours = {v.get("chaine") or common.CHAINE_DEFAUT for v in etat["envoyes"].values() if v.get("statut") in EN_COURS}
    chaines = sorted({chaine_de(e) for e in todo} | en_cours)
    clients, refus, pannes = ({}, {}, {}) if a.paquet else clients_pour(chaines)
    a_reconnecter = sorted(refus)
    if refus:
        sortie["auth"] = "; ".join(f"{ch} : {m}" for ch, m in refus.items())
        sortie["chaines_a_reconnecter"] = a_reconnecter
    if pannes:
        sortie["reseau"] = "; ".join(f"{ch} : {m}" for ch, m in pannes.items())
    if clients:
        try:
            sortie.update(envoyer_file(clients, a.max if a.max is not None else 1000, a.id, a.dry_run))
        except C.ErreurAuth as e:
            sortie["auth"] = str(e)
            a_reconnecter = sorted(set(a_reconnecter) | set(clients))
            sortie["chaines_a_reconnecter"] = a_reconnecter
        except C.ErreurReseau as e:
            sortie["reseau"] = str(e)
        except C.ErreurApi as e:
            sortie["erreur"] = str(e)
    if (a.paquet or a_reconnecter) and not a.dry_run:
        sortie["paquets"] = [str(preparer_paquet(ep)) for ep in todo if a.paquet or chaine_de(ep) in a_reconnecter]
    if sortie.get("jours_avant_renouvellement") is None:
        j = C.jours_avant_expiration_renouvellement(C.chemin_jeton(common.tiktok_reglage(common.CHAINE_DEFAUT)["jeton_fichier"]))
        if j is not None:
            sortie["jours_avant_renouvellement"] = round(j, 1)
    print(json.dumps(sortie, ensure_ascii=False, indent=1))
    if a_reconnecter:
        return 3
    return 1 if ("erreur" in sortie) else 0


if __name__ == "__main__":
    sys.exit(main())
