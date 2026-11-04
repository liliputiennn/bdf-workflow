"""Client YouTube Data API v3 (bibliothèque standard) : envoi résumable, miniature, relecture, mise à jour.

Protocole d'envoi : https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol
Les échecs passagers (réseau coupé, 5xx, 429) sont retentés avec attente exponentielle ; une session d'envoi
interrompue est reprise là où YouTube l'a laissée (et mémorisée dans `episodes-b/<id>/youtube_upload.json`).
"""
import json
import random
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.client
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
from erreurs import ErreurAuth, ErreurContenu, ErreurQuota, ErreurReseau, Transitoire  # noqa: E402

RAISONS_QUOTA = {"quotaExceeded", "dailyLimitExceeded", "uploadLimitExceeded", "youtube.quota"}
RAISONS_PASSAGERES = {"rateLimitExceeded", "userRateLimitExceeded", "backendError", "internalError", "serviceUnavailable"}
RAISONS_AUTH = {"authError", "insufficientPermissions", "youtubeSignupRequired", "accountClosed", "accountSuspended",
                "channelClosed", "channelSuspended", "forbidden", "unauthorized", "required"}
CODES_PASSAGERS = {408, 429, 500, 502, 503, 504}


class _SansRedirection(urllib.request.HTTPRedirectHandler):
    """Un 308 « Resume Incomplete » n'est pas une redirection."""

    def redirect_request(self, *a, **k):
        return None


_OPENER = urllib.request.build_opener(_SansRedirection)


def appel_http(methode: str, url: str, entetes: dict, corps: bytes | None, timeout: float) -> tuple[int, dict, bytes]:
    """Un appel HTTP. Ne lève jamais sur un code d'état ; lève Transitoire si le réseau lâche."""
    req = urllib.request.Request(url, data=corps, method=methode, headers=entetes)
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read() or b""
        finally:
            e.close()
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as e:
        raise Transitoire(f"réseau : {e}") from e


def raison_erreur(corps: bytes) -> tuple[str, str]:
    try:
        err = json.loads(corps)["error"]
        if isinstance(err, str):
            return err, ""
        return (err.get("errors") or [{}])[0].get("reason", ""), err.get("message", "")
    except (ValueError, KeyError, TypeError, IndexError):
        return "", corps[:200].decode("utf-8", "replace")


def classer(code: int, corps: bytes) -> Exception:
    """Transforme une réponse d'erreur en exception du bon type."""
    raison, message = raison_erreur(corps)
    detail = f"HTTP {code} {raison} {message}".strip()
    if raison in RAISONS_QUOTA:
        return ErreurQuota(detail)
    if code in CODES_PASSAGERS or raison in RAISONS_PASSAGERES:
        return Transitoire(detail)
    if code == 401 or raison in RAISONS_AUTH:
        return ErreurAuth(detail)
    return ErreurContenu(detail)


class YouTube:
    def __init__(self, jeton, cfg: dict, quota, dormir=time.sleep):
        self.jeton, self.cfg, self.quota, self.dormir = jeton, cfg, quota, dormir
        self.api = cfg["urls"]["api"]
        self.upload = cfg["urls"]["upload"]
        self.res = cfg["reseau"]

    # --- bas niveau -------------------------------------------------------------------------------------

    def _attente(self, essai: int) -> float:
        base = min(self.res["attente_max_s"], self.res["attente_initiale_s"] * 2 ** (essai - 1))
        return base * random.uniform(0.75, 1.25)

    def _appel(self, methode: str, url: str, entetes: dict | None = None, corps: bytes | None = None) -> tuple[int, dict, bytes]:
        """Appel authentifié ; renouvelle le jeton une fois sur 401."""
        for rafraichi in (False, True):
            h = dict(entetes or {})
            h["Authorization"] = "Bearer " + self.jeton.acces(force=rafraichi)
            code, rep_h, rep = appel_http(methode, url, h, corps, self.res["timeout_s"])
            if code != 401:
                return code, rep_h, rep
        raise ErreurAuth("YouTube refuse le jeton même après rafraîchissement : refaire la connexion (auth.py)")

    def _avec_reprises(self, fonction):
        """Exécute `fonction()` ; retente les échecs passagers avec attente exponentielle."""
        for essai in range(1, self.res["tentatives_max"] + 1):
            try:
                return fonction()
            except Transitoire as e:
                if essai == self.res["tentatives_max"]:
                    raise ErreurReseau(f"abandon après {essai} tentatives : {e}") from e
                self.dormir(self._attente(essai))

    def _json(self, methode: str, url: str, corps: dict | None = None, operation: str = "", unites: int = 0) -> dict:
        self.quota.verifier(unites=unites)
        donnees = json.dumps(corps).encode() if corps is not None else None
        entetes = {"Content-Type": "application/json; charset=UTF-8"} if donnees else {}

        def une_fois():
            code, _, rep = self._appel(methode, url, entetes, donnees)
            if code >= 400:
                raise classer(code, rep)
            return json.loads(rep or b"{}")

        try:
            res = self._avec_reprises(une_fois)
        except ErreurQuota as e:
            self.quota.declarer_epuise(str(e))
            e.prochain_essai = self.quota.prochain_essai()
            raise
        self.quota.depenser(operation, unites=unites)
        return res

    # --- envoi résumable --------------------------------------------------------------------------------

    def _ouvrir_session(self, taille: int, metadonnees: dict) -> str:
        url = f"{self.upload}/videos?" + urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status"})
        entetes = {"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(taille),
                   "X-Upload-Content-Type": "video/mp4"}

        def une_fois():
            code, h, rep = self._appel("POST", url, entetes, json.dumps(metadonnees).encode())
            if code != 200 or not h.get("location"):
                raise classer(code if code >= 400 else 502, rep)
            return h["location"]

        try:
            return self._avec_reprises(une_fois)
        except ErreurQuota as e:
            self.quota.declarer_epuise(str(e))
            e.prochain_essai = self.quota.prochain_essai()
            raise

    def envoyer_video(self, chemin: Path, metadonnees: dict, memo: Path, afficher=print) -> dict:
        """Envoie la vidéo (reprise comprise). Retourne la ressource `video` renvoyée par YouTube."""
        taille = chemin.stat().st_size
        signature = {"taille": taille, "mtime": int(chemin.stat().st_mtime)}
        sauve = common.read_json(memo, {}) or {}
        session = sauve.get("session") if sauve.get("signature") == signature else None
        decalage = None if session else 0
        chunk = self.cfg["chunk_octets"]
        echecs = 0

        while True:
            try:
                if not session:
                    unites, envois = self.quota.cout_envoi()
                    self.quota.verifier(unites=unites, envois=envois)
                    session = self._ouvrir_session(taille, metadonnees)
                    self.quota.depenser("videos.insert", unites=unites, envois=envois)
                    common.write_json(memo, {"session": session, "signature": signature, "ouverte": common.now()})
                    decalage = 0
                if decalage is None:
                    code, h, rep = self._appel("PUT", session, {"Content-Range": f"bytes */{taille}", "Content-Length": "0"}, b"")
                    if code in (200, 201):
                        return json.loads(rep)
                    if code == 308:
                        decalage = int(h["range"].split("-")[1]) + 1 if h.get("range") else 0
                    elif code in (404, 410):
                        session, decalage = None, 0
                        raise Transitoire("session d'envoi expirée, nouvelle session")
                    else:
                        raise classer(code, rep)
                with open(chemin, "rb") as f:
                    f.seek(decalage)
                    morceau = f.read(chunk if taille - decalage > chunk else taille - decalage)
                fin = decalage + len(morceau) - 1
                afficher(f"  envoi {decalage + len(morceau)}/{taille} octets")
                code, h, rep = self._appel("PUT", session, {"Content-Range": f"bytes {decalage}-{fin}/{taille}",
                                                           "Content-Type": "video/mp4"}, morceau)
                if code in (200, 201):
                    return json.loads(rep)
                if code == 308:
                    decalage = int(h["range"].split("-")[1]) + 1 if h.get("range") else 0
                    echecs = 0
                    continue
                if code in (404, 410):
                    session, decalage = None, 0
                    raise Transitoire("session d'envoi expirée, nouvelle session")
                raise classer(code, rep)
            except Transitoire as e:
                echecs += 1
                if echecs >= self.res["tentatives_max"]:
                    raise ErreurReseau(f"envoi interrompu après {echecs} tentatives : {e} (session conservée pour la reprise)") from e
                self.dormir(self._attente(echecs))
                if session:
                    decalage = None  # on demande à YouTube ce qu'il a reçu

    # --- le reste de l'API -------------------------------------------------------------------------------

    def definir_miniature(self, video_id: str, image: Path) -> None:
        self.quota.verifier(unites=self.cfg["quota"]["cout_miniature"])
        mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        url = f"{self.upload}/thumbnails/set?" + urllib.parse.urlencode({"videoId": video_id, "uploadType": "media"})
        donnees = image.read_bytes()

        def une_fois():
            code, _, rep = self._appel("POST", url, {"Content-Type": mime}, donnees)
            if code >= 400:
                raise classer(code, rep)

        try:
            self._avec_reprises(une_fois)
        except ErreurQuota as e:
            self.quota.declarer_epuise(str(e))
            e.prochain_essai = self.quota.prochain_essai()
            raise
        self.quota.depenser("thumbnails.set", unites=self.cfg["quota"]["cout_miniature"])

    def poster_commentaire(self, video_id: str, texte: str) -> str:
        """`commentThreads.insert` : poste un commentaire de la chaîne sous la vidéo. Renvoie son identifiant.
        L'API ne permet pas de l'épingler : le propriétaire clique « Épingler » dans YouTube Studio."""
        corps = {"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": texte}}}}
        res = self._json("POST", f"{self.api}/commentThreads?part=snippet", corps, operation="commentThreads.insert",
                         unites=self.cfg["quota"].get("cout_commentaire", 50))
        return str(res.get("id", ""))

    def lire_videos(self, ids: list[str], parts: str = "status") -> list[dict]:
        """`videos.list` (1 unité par appel, 50 identifiants au plus)."""
        sortie: list[dict] = []
        for i in range(0, len(ids), 50):
            url = f"{self.api}/videos?" + urllib.parse.urlencode({"part": parts, "id": ",".join(ids[i:i + 50]), "maxResults": 50})
            sortie += self._json("GET", url, operation="videos.list", unites=self.cfg["quota"]["cout_lecture"]).get("items", [])
        return sortie

    def lister_envois_chaine(self) -> list[str]:
        """Identifiants de toutes les vidéos envoyées sur la chaîne (liste de lecture « uploads »)."""
        q = self.cfg["quota"]["cout_lecture"]
        chaine = self._json("GET", f"{self.api}/channels?" + urllib.parse.urlencode({"part": "contentDetails", "mine": "true"}),
                            operation="channels.list", unites=q)
        if not chaine.get("items"):
            raise ErreurAuth("aucune chaîne YouTube trouvée pour ce compte")
        liste = chaine["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        ids, page = [], None
        while True:
            params = {"part": "contentDetails", "playlistId": liste, "maxResults": 50}
            if page:
                params["pageToken"] = page
            rep = self._json("GET", f"{self.api}/playlistItems?" + urllib.parse.urlencode(params),
                             operation="playlistItems.list", unites=q)
            ids += [i["contentDetails"]["videoId"] for i in rep.get("items", [])]
            page = rep.get("nextPageToken")
            if not page:
                return ids

    def mettre_a_jour_statut(self, video_id: str, statut: dict) -> dict:
        """`videos.update` sur la partie `status` : il faut renvoyer le statut complet, pas seulement un champ."""
        url = f"{self.api}/videos?" + urllib.parse.urlencode({"part": "status"})
        return self._json("PUT", url, {"id": video_id, "status": statut}, operation="videos.update",
                          unites=self.cfg["quota"]["cout_mise_a_jour"])


def construire_ressource(pub: dict, cfg: dict, publie_a_iso: str) -> dict:
    """Corps JSON de `videos.insert` (parts snippet + status) à partir de publication.json."""
    return {
        "snippet": {
            "title": pub["titre"], "description": pub["description"], "tags": pub.get("tags", []),
            "categoryId": str(pub.get("categorie_id") or cfg["categorie_id"]),
            "defaultLanguage": pub.get("langue") or cfg["langue"],
            "defaultAudioLanguage": pub.get("langue") or cfg["langue"],
        },
        "status": {
            "privacyStatus": "private", "publishAt": publie_a_iso,
            "selfDeclaredMadeForKids": False, "embeddable": True, "publicStatsViewable": True,
            "containsSyntheticMedia": bool(cfg.get("badge_ia_youtube", False)) and bool(pub.get("contenu_ia", False)),
        },
    }
