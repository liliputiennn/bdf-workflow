"""Moteur « planificateur » : publie un Short sur TikTok EN PUBLIC par un service tiers dont l'application TikTok est déjà auditée.

Pourquoi : notre propre application TikTok n'est pas auditée, donc TikTok y force la visibilité « privée ». Un service déjà audité
(ici Upload-Post, API officielle de TikTok derrière) publie en public sans notification sur ton téléphone. Voir OPTIONS-PUBLICATION.md
(section « Voie automatique publique ») pour le comparatif, le prix et les limites.

Interface commune des moteurs (utilisée par envoi.py) :
    moteur.publier(video: Path, legende: str, reg: dict, afficher) -> identifiant de suivi (str)
    moteur.statut(identifiant) -> {"status": "PROCESSING_UPLOAD" | "PUBLISH_COMPLETE" | "SEND_TO_USER_INBOX" | "FAILED", "fail_reason": str}
(mêmes valeurs d'état que le moteur « boîte de réception », pour que le reste du programme n'ait rien à savoir du service.)

Clé d'accès : fichier autopilot/secrets/upload_post.json  {"api_key": "..."}  (créé par TOI ; ce programme ne le crée ni ne l'affiche).
Compte TikTok : connecté par toi dans le tableau de bord du service (profil nommé dans le champ `tiktok.planificateur.profil`).
Aucune publication n'a lieu hors d'un réglage explicite `"moteur": "planificateur"` dans le profil de la chaîne.
"""
import json
import sys
import uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import client as C  # noqa: E402

BASE = "https://api.upload-post.com/api"
FICHIER_CLE = "upload_post.json"
# Valeurs d'état du service (page « Upload Status ») -> états de notre file d'attente
ETATS_EN_COURS = ("pending", "queued", "processing", "in_progress", "retryable")
RAISONS_DEFINITIVES = ("tiktok_media_rejected",)


def chemin_cle(nom: str | None = None) -> Path:
    return C.SECRETS / (nom or FICHIER_CLE)


def lire_cle(chemin: Path) -> str:
    d = C.lire(chemin)
    cle = d.get("api_key") if isinstance(d, dict) else None
    if not (isinstance(cle, str) and cle.strip()):
        raise C.ErreurAuth(f"clé du planificateur absente : crée {chemin.name} avec {{\"api_key\": \"...\"}} (voir OPTIONS-PUBLICATION.md)")
    return cle.strip()


def corps_multipart(champs: list[tuple[str, str]], fichier: tuple[str, str, bytes, str]) -> tuple[bytes, str]:
    """(corps, type de contenu) d'un envoi multipart/form-data. fichier = (champ, nom, octets, type)."""
    frontiere = "----bdf" + uuid.uuid4().hex
    out = bytearray()
    for nom, val in champs:
        out += f'--{frontiere}\r\nContent-Disposition: form-data; name="{nom}"\r\n\r\n{val}\r\n'.encode("utf-8")
    champ, nom, octets, ctype = fichier
    out += f'--{frontiere}\r\nContent-Disposition: form-data; name="{champ}"; filename="{nom}"\r\nContent-Type: {ctype}\r\n\r\n'.encode("utf-8")
    out += octets + f"\r\n--{frontiere}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={frontiere}"


class UploadPost:
    def __init__(self, cle: str, profil: str, appel=C.appel_http):
        self.cle, self.profil, self.appel = cle, profil, appel

    def _entetes(self, extra: dict | None = None) -> dict:
        return {"Authorization": f"Apikey {self.cle}", "Accept": "application/json", **(extra or {})}

    def _reponse(self, code: int, corps: bytes) -> dict:
        try:
            d = json.loads(corps.decode("utf-8") or "{}")
        except ValueError:
            d = {}
        d = d if isinstance(d, dict) else {}
        if code == 401:
            raise C.ErreurAuth("clé du planificateur refusée ou expirée : remets une clé valide dans upload_post.json")
        if code == 403:
            raise C.ErreurApi("plan", "TikTok demande un abonnement payant chez le planificateur (offre gratuite refusée)", code)
        if code == 429:
            raise C.ErreurApi("limite", str(d.get("message") or d.get("error") or "limite atteinte (quota mensuel ou 15 par 24 h)")[:200], code)
        if code >= 500:
            raise C.ErreurReseau(f"le planificateur répond {code}")
        if code >= 400:
            raise C.ErreurApi("refus", str(d.get("message") or d.get("error") or code)[:200], code)
        return d

    def publier(self, video: Path, legende: str, reg: dict, afficher=print) -> str:
        """Envoie la vidéo + la légende ; renvoie l'identifiant de suivi. Publication directe publique (réglage `visibilite` de la chaîne)."""
        champs = [("user", self.profil), ("platform[]", "tiktok"), ("title", legende), ("tiktok_title", legende),
                  ("privacy_level", reg["visibilite"]), ("post_mode", "DIRECT_POST"), ("async_upload", "true")]
        corps, ctype = corps_multipart(champs, ("video", video.name, video.read_bytes(), "video/mp4"))
        afficher(f"  envoi au planificateur ({len(corps) // 1024} Ko)")
        code, _, brut = self.appel("POST", f"{BASE}/upload", self._entetes({"Content-Type": ctype}), corps, 300.0)
        d = self._reponse(code, brut)
        rid = d.get("request_id") or d.get("job_id")
        if not rid:
            raise C.ErreurApi("reponse", "pas d'identifiant de suivi dans la réponse du planificateur", code)
        return str(rid)

    def statut(self, identifiant: str) -> dict:
        code, _, brut = self.appel("GET", f"{BASE}/uploadposts/status?request_id={identifiant}", self._entetes(), None, 30.0)
        if code == 404:
            return {"status": "FAILED", "fail_reason": "not_found"}
        return traduire_statut(self._reponse(code, brut))


def traduire_statut(d: dict) -> dict:
    """Réponse « Upload Status » -> état de notre file d'attente."""
    st = d.get("status")
    res = [r for r in (d.get("results") or []) if isinstance(r, dict) and r.get("platform") == "tiktok"]
    if st == "completed":
        if any(r.get("fallback_to_inbox") for r in res):
            return {"status": "SEND_TO_USER_INBOX"}  # plafond de TikTok atteint : brouillon dans ta boîte, à publier à la main
        return {"status": "PUBLISH_COMPLETE"}
    if st == "failed":
        msg = " ".join(str(r.get("message") or "") for r in res) or str(d.get("message") or "")
        raison = "video_rejected" if any(x in msg for x in RAISONS_DEFINITIVES) else "internal"
        return {"status": "FAILED", "fail_reason": raison}
    return {"status": "PROCESSING_UPLOAD"}


BASE_ZERNIO = "https://zernio.com/api/v1"


class Zernio:
    """Zernio (ex-Late) : offre gratuite = 2 comptes sociaux, publications illimitées, API complète (zernio.com/pricing).
    Les connexions TikTok récentes passent par l'application « Business » du service : vidéos publiées en public seulement.
    La vidéo est déposée chez le service (URL signée), puis un post `publishNow` est créé."""

    def __init__(self, cle: str, compte: str, consentement: bool, appel=C.appel_http):
        self.cle, self.compte, self.consentement, self.appel = cle, compte, consentement, appel

    def _json(self, methode, url, corps_json=None, timeout=60.0):
        ent = {"Authorization": f"Bearer {self.cle}", "Accept": "application/json"}
        corps = None
        if corps_json is not None:
            corps, ent["Content-Type"] = json.dumps(corps_json).encode("utf-8"), "application/json"
        code, _, brut = self.appel(methode, url, ent, corps, timeout)
        return code, brut

    def _reponse(self, code: int, brut: bytes) -> dict:
        try:
            d = json.loads(brut.decode("utf-8") or "{}")
        except ValueError:
            d = {}
        d = d if isinstance(d, dict) else {}
        msg = str(d.get("message") or d.get("error") or code)[:200]
        if code in (401, 403):
            raise C.ErreurAuth("clé du planificateur refusée : remets une clé valide dans zernio.json")
        if code == 429:
            raise C.ErreurApi("limite", msg, code)
        if code >= 500:
            raise C.ErreurReseau(f"le planificateur répond {code}")
        if code >= 400:
            raise C.ErreurApi("refus", msg, code)
        return d

    def publier(self, video: Path, legende: str, reg: dict, afficher=print) -> str:
        if not self.compte:
            raise C.ErreurAuth("identifiant de compte absent : mets `planificateur.compte` (accountId Zernio) dans le profil de la chaîne")
        if not self.consentement:
            raise C.ErreurAuth("TikTok exige ta confirmation à chaque publication : écris toi-même `planificateur.consentement: true` "
                               "(tu as relu le contenu et acceptes la politique d'usage de la musique de TikTok)")
        octets = video.read_bytes()
        d = self._reponse(*self._json("POST", f"{BASE_ZERNIO}/media/presign", {"filename": video.name, "contentType": "video/mp4", "size": len(octets)}))
        if not (d.get("uploadUrl") and d.get("publicUrl")):
            raise C.ErreurApi("reponse", "pas d'adresse de dépôt dans la réponse", 200)
        afficher(f"  dépôt de la vidéo chez le planificateur ({len(octets) // 1024} Ko)")
        code, _, brut = self.appel("PUT", d["uploadUrl"], {"Content-Type": "video/mp4"}, octets, 300.0)
        if code >= 500:
            raise C.ErreurReseau(f"dépôt refusé ({code})")
        if code >= 400:
            raise C.ErreurApi("depot", f"dépôt refusé ({code})", code)
        corps = {"content": legende, "mediaItems": [{"url": d["publicUrl"], "type": "video"}], "publishNow": True,
                 "platforms": [{"platform": "tiktok", "accountId": self.compte}],
                 "tiktokSettings": {"privacy_level": reg["visibilite"], "allow_comment": False, "allow_duet": False, "allow_stitch": False,
                                    "content_preview_confirmed": True, "express_consent_given": True}}
        r = self._reponse(*self._json("POST", f"{BASE_ZERNIO}/posts", corps))
        pid = (r.get("post") or {}).get("_id")
        if not pid:
            raise C.ErreurApi("reponse", "pas d'identifiant de post dans la réponse", 200)
        return str(pid)

    def statut(self, identifiant: str) -> dict:
        code, brut = self._json("GET", f"{BASE_ZERNIO}/posts/{identifiant}")
        if code == 404:
            return {"status": "FAILED", "fail_reason": "not_found"}
        return traduire_statut_zernio(self._reponse(code, brut))


def traduire_statut_zernio(d: dict) -> dict:
    post = d.get("post") if isinstance(d.get("post"), dict) else d
    st = post.get("status")
    plats = [p for p in (post.get("platforms") or []) if isinstance(p, dict) and p.get("platform") == "tiktok"]
    if st == "published" or (plats and all(p.get("status") == "published" for p in plats)):
        return {"status": "PUBLISH_COMPLETE"}
    if st == "failed" or any(p.get("status") == "failed" for p in plats):
        return {"status": "FAILED", "fail_reason": "internal"}
    return {"status": "PROCESSING_UPLOAD"}


def charger(reg: dict, appel=C.appel_http):
    p = reg["planificateur"]
    cle = lire_cle(chemin_cle(p["cle_fichier"]))
    if p["service"] == "zernio":
        return Zernio(cle, p["compte"], p["consentement"], appel)
    return UploadPost(cle, p["profil"], appel)
