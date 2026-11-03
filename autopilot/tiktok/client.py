"""Client minimal de l'API TikTok « Content Posting » (envoi dans la boîte de réception, portée `video.upload`).

Bibliothèque standard seulement. Spécifications vérifiées dans la documentation de TikTok le 2026-11-03 :
  - jeton    POST https://open.tiktokapis.com/v2/oauth/token/  (formulaire ; le jeton d'accès dure 2 h, celui de renouvellement 180 jours et change à chaque renouvellement)
  - envoi    POST https://open.tiktokapis.com/v2/post/publish/inbox/video/init/  puis PUT des blocs sur `upload_url` (valable 1 h)
  - blocs    de 5 à 64 Mo, dans l'ordre ; le dernier peut aller jusqu'à 128 Mo ; 206 = bloc reçu, 201 = tout reçu
  - statut   POST https://open.tiktokapis.com/v2/post/publish/status/fetch/
Limite connue : 5 envois en attente au plus par 24 h et par utilisateur (erreur 403 `spam_risk_too_many_pending_share`).
Ce module ne lit ni n'affiche jamais le contenu des fichiers de `autopilot/secrets/`.
"""
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://open.tiktokapis.com"
ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent
SECRETS = RACINE / "autopilot" / "secrets"
FICHIER_CLIENT = SECRETS / "tiktok_client.json"
FICHIER_JETON = SECRETS / "tiktok_token.json"

MO = 1024 * 1024
BLOC_MIN, BLOC_MAX, BLOC_FINAL_MAX = 5 * MO, 64 * MO, 128 * MO
BLOC_DEFAUT = 32 * MO
MARGE_RENOUVELLEMENT_S = 300
ALERTE_RENOUVELLEMENT_JOURS = 14


class ErreurTikTok(Exception):
    pass


class ErreurAuth(ErreurTikTok):
    """Jeton absent, expiré ou refusé : l'utilisateur doit relancer `auth.py`."""


class ErreurReseau(ErreurTikTok):
    """Panne passagère (réseau, 5xx) : on réessaiera plus tard."""


class ErreurApi(ErreurTikTok):
    def __init__(self, code: str, message: str, http: int = 0):
        super().__init__(f"{code} : {message}")
        self.code, self.http = code, http


def appel_http(methode: str, url: str, entetes: dict, corps: bytes | None, timeout: float = 60.0) -> tuple[int, dict, bytes]:
    """(code, en-têtes, corps). Remplaçable dans les tests."""
    req = urllib.request.Request(url, data=corps, headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() or b""
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        raise ErreurReseau(str(e)) from e


def _json(corps: bytes) -> dict:
    try:
        return json.loads(corps.decode("utf-8") or "{}")
    except ValueError:
        return {}


def lire(chemin: Path) -> dict | None:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ecrire_atomique(chemin: Path, obj: dict) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(chemin)


def charger_client(chemin: Path | None = None) -> dict:
    c = lire(chemin or FICHIER_CLIENT)
    if not c or not c.get("client_key") or not c.get("client_secret"):
        raise ErreurAuth("autopilot/secrets/tiktok_client.json absent ou incomplet (voir autopilot/tiktok/INSTALLATION.md)")
    return c


def _jeton_depuis_reponse(rep: dict, maintenant: float) -> dict:
    return {
        "access_token": rep["access_token"], "expire_a": int(maintenant + int(rep.get("expires_in", 7200))),
        "refresh_token": rep["refresh_token"], "refresh_expire_a": int(maintenant + int(rep.get("refresh_expires_in", 180 * 86400))),
        "open_id": rep.get("open_id", ""), "scope": rep.get("scope", ""),
    }


def echanger_code(client: dict, code: str, redirect_uri: str, verifier: str, appel=appel_http, maintenant=time.time) -> dict:
    corps = urllib.parse.urlencode({
        "client_key": client["client_key"], "client_secret": client["client_secret"], "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri, "code_verifier": verifier,
    }).encode()
    code_http, _, rep = appel("POST", f"{API}/v2/oauth/token/", {"Content-Type": "application/x-www-form-urlencoded"}, corps)
    d = _json(rep)
    if code_http != 200 or "access_token" not in d:
        raise ErreurAuth(f"échange du code refusé ({d.get('error', code_http)} : {d.get('error_description', '')})")
    return _jeton_depuis_reponse(d, maintenant())


def rafraichir(client: dict, jeton: dict, appel=appel_http, maintenant=time.time) -> dict:
    """Renouvelle le jeton d'accès. Le jeton de renouvellement change à chaque fois : on garde le nouveau."""
    if jeton.get("refresh_expire_a", 0) <= maintenant():
        raise ErreurAuth("jeton de renouvellement expiré (180 jours) : relance `python autopilot/tiktok/auth.py`")
    corps = urllib.parse.urlencode({
        "client_key": client["client_key"], "client_secret": client["client_secret"],
        "grant_type": "refresh_token", "refresh_token": jeton["refresh_token"],
    }).encode()
    code_http, _, rep = appel("POST", f"{API}/v2/oauth/token/", {"Content-Type": "application/x-www-form-urlencoded"}, corps)
    d = _json(rep)
    if code_http >= 500:
        raise ErreurReseau(f"TikTok indisponible ({code_http})")
    if code_http != 200 or "access_token" not in d:
        raise ErreurAuth(f"renouvellement refusé ({d.get('error', code_http)}) : relance `python autopilot/tiktok/auth.py`")
    return _jeton_depuis_reponse(d, maintenant())


def jeton_valide(client: dict, chemin: Path | None = None, appel=appel_http, maintenant=time.time) -> str:
    """Renvoie un jeton d'accès utilisable, en le renouvelant (et en le sauvegardant) si besoin."""
    chemin = chemin or FICHIER_JETON
    j = lire(chemin)
    if not j or not j.get("access_token"):
        raise ErreurAuth("aucun jeton TikTok : lance `python autopilot/tiktok/auth.py` (voir INSTALLATION.md)")
    if j["expire_a"] - maintenant() < MARGE_RENOUVELLEMENT_S:
        j = rafraichir(client, j, appel, maintenant)
        ecrire_atomique(chemin, j)
    return j["access_token"]


def jours_avant_expiration_renouvellement(chemin: Path | None = None, maintenant=time.time) -> float | None:
    j = lire(chemin or FICHIER_JETON)
    return None if not j else (j.get("refresh_expire_a", 0) - maintenant()) / 86400


def plan_blocs(taille: int) -> list[tuple[int, int]]:
    """[(premier_octet, dernier_octet)] selon les règles de TikTok : 5 à 64 Mo, dernier bloc jusqu'à 128 Mo, un seul bloc sous 64 Mo."""
    if taille <= 0:
        raise ErreurTikTok("fichier vide")
    if taille <= BLOC_MAX:
        return [(0, taille - 1)]
    n = taille // BLOC_DEFAUT
    blocs = [(k * BLOC_DEFAUT, (k + 1) * BLOC_DEFAUT - 1) for k in range(n - 1)]
    blocs.append(((n - 1) * BLOC_DEFAUT, taille - 1))
    if blocs[-1][1] - blocs[-1][0] + 1 > BLOC_FINAL_MAX:
        raise ErreurTikTok("fichier trop gros pour les règles de découpage de TikTok")
    return blocs


class TikTok:
    def __init__(self, jeton: str, appel=appel_http, pause=time.sleep):
        self.jeton, self.appel, self.pause = jeton, appel, pause

    def _api(self, chemin: str, corps: dict) -> dict:
        code, _, rep = self.appel("POST", API + chemin, {
            "Authorization": f"Bearer {self.jeton}", "Content-Type": "application/json; charset=UTF-8"}, json.dumps(corps).encode())
        d = _json(rep)
        err = d.get("error") or {}
        if code == 401 or err.get("code") in ("access_token_invalid", "scope_not_authorized"):
            raise ErreurAuth(f"jeton refusé par TikTok ({err.get('code') or code}) : relance `auth.py`")
        if code >= 500 or err.get("code") == "internal_error":
            raise ErreurReseau(f"TikTok indisponible ({code})")
        if code == 429:
            raise ErreurReseau("trop de requêtes (429), on réessaiera")
        if code >= 400 or (err.get("code") not in (None, "", "ok")):
            raise ErreurApi(str(err.get("code") or code), str(err.get("message") or ""), code)
        return d.get("data") or {}

    def initialiser(self, taille: int) -> tuple[str, str, list[tuple[int, int]]]:
        blocs = plan_blocs(taille)
        gros = BLOC_MAX if taille <= BLOC_MAX else BLOC_DEFAUT
        data = self._api("/v2/post/publish/inbox/video/init/", {"source_info": {
            "source": "FILE_UPLOAD", "video_size": taille, "chunk_size": taille if len(blocs) == 1 else gros, "total_chunk_count": len(blocs)}})
        if not data.get("publish_id") or not data.get("upload_url"):
            raise ErreurApi("reponse_incomplete", "publish_id ou upload_url manquant")
        return data["publish_id"], data["upload_url"], blocs

    def envoyer(self, chemin: Path, afficher=print) -> str:
        """Envoie la vidéo dans la boîte de réception TikTok de l'utilisateur ; renvoie le `publish_id`."""
        taille = chemin.stat().st_size
        publish_id, url, blocs = self.initialiser(taille)
        with chemin.open("rb") as f:
            for k, (a, b) in enumerate(blocs, 1):
                f.seek(a)
                morceau = f.read(b - a + 1)
                for essai in range(1, 4):
                    code, _, rep = self.appel("PUT", url, {
                        "Content-Type": "video/mp4", "Content-Length": str(len(morceau)),
                        "Content-Range": f"bytes {a}-{b}/{taille}"}, morceau, 300.0)
                    attendu = 201 if k == len(blocs) else 206
                    if code == attendu or (k == len(blocs) and code in (200, 201)):
                        break
                    if code in (403, 404):
                        raise ErreurApi("upload_refuse", f"adresse d'envoi refusée ({code})", code)
                    if code >= 500 and essai < 3:
                        self.pause(2 ** essai)
                        continue
                    raise ErreurApi("upload_refuse", f"bloc {k}/{len(blocs)} : code {code}", code)
                afficher(f"  bloc {k}/{len(blocs)} envoyé")
        return publish_id

    def statut(self, publish_id: str) -> dict:
        """{'status': 'PROCESSING_UPLOAD' | 'SEND_TO_USER_INBOX' | 'PUBLISH_COMPLETE' | 'FAILED', 'fail_reason'?}"""
        return self._api("/v2/post/publish/status/fetch/", {"publish_id": publish_id})
