"""OAuth « application de bureau » pour YouTube : navigateur + redirection 127.0.0.1 + PKCE.

Lit `autopilot/secrets/client_secret.json` (déposé par le propriétaire), écrit `autopilot/secrets/token.json`.
Ce module ne crée ni client, ni compte, ni jeton de lui-même : le propriétaire se connecte dans son navigateur.

    python autopilot/publish/auth.py             # connexion (une seule fois)
    python autopilot/publish/auth.py --statut    # état du jeton, sans rien afficher de secret
"""
import base64
import hashlib
import json
import secrets as aleatoire
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
from erreurs import ErreurAuth, ErreurReseau  # noqa: E402

PORTEE = "https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl"  # force-ssl : poster le commentaire du cadeau
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
MARGE_EXPIRATION_S = 120


def dossier_secrets() -> Path:
    return common.ROOT / "autopilot" / "secrets"


def chemin_client() -> Path:
    return dossier_secrets() / "client_secret.json"


def chemin_jeton() -> Path:
    return dossier_secrets() / "token.json"


def chemin_etat_auth() -> Path:
    return common.STATE / "youtube_auth.json"


def charger_client() -> dict:
    """Retourne {client_id, client_secret, auth_uri, token_uri} depuis le fichier téléchargé chez Google."""
    brut = common.read_json(chemin_client())
    if not brut:
        raise ErreurAuth(f"fichier client OAuth absent ou illisible : {chemin_client()} (voir INSTALLATION.md)")
    bloc = brut.get("installed") or brut.get("web")
    if not bloc or "client_id" not in bloc:
        raise ErreurAuth("client_secret.json invalide : il faut un identifiant de type « Application de bureau »")
    return {
        "client_id": bloc["client_id"],
        "client_secret": bloc.get("client_secret", ""),
        "auth_uri": bloc.get("auth_uri", AUTH_URI),
        "token_uri": bloc.get("token_uri", TOKEN_URI),
    }


def noter_etat_auth(etat: str, raison: str | None = None) -> None:
    """`autopilot/state/youtube_auth.json` : l'orchestrateur s'y fie pour savoir si la publication est possible."""
    common.write_json(chemin_etat_auth(), {"etat": etat, "raison": raison, "maj": common.now()})


def _poster(url: str, champs: dict, timeout: float = 30.0) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(champs).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}
        finally:
            e.close()
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise ErreurReseau(f"serveur d'authentification injoignable : {e}") from e


class Jeton:
    """Jeton d'accès avec rafraîchissement automatique à partir du jeton de rafraîchissement."""

    def __init__(self, horloge=time.time):
        self.horloge = horloge
        self._client = None

    def _charger(self) -> dict:
        jeton = common.read_json(chemin_jeton())
        if not jeton or not jeton.get("refresh_token"):
            raise ErreurAuth("aucun jeton : lancer `python autopilot/publish/auth.py` (voir INSTALLATION.md)")
        return jeton

    def acces(self, force: bool = False) -> str:
        jeton = self._charger()
        if not force and jeton.get("access_token") and jeton.get("expiry", 0) - self.horloge() > MARGE_EXPIRATION_S:
            return jeton["access_token"]
        return self.rafraichir(jeton)

    def rafraichir(self, jeton: dict | None = None) -> str:
        jeton = jeton or self._charger()
        client = self._client = self._client or charger_client()
        code, rep = _poster(client["token_uri"], {
            "client_id": client["client_id"], "client_secret": client["client_secret"],
            "refresh_token": jeton["refresh_token"], "grant_type": "refresh_token"})
        if code == 200 and rep.get("access_token"):
            jeton.update(access_token=rep["access_token"], expiry=self.horloge() + int(rep.get("expires_in", 3600)),
                         maj=common.now())
            if rep.get("refresh_token"):
                jeton["refresh_token"] = rep["refresh_token"]
            common.write_json(chemin_jeton(), jeton)
            if (common.read_json(chemin_etat_auth(), {}) or {}).get("etat") == "a_refaire":
                noter_etat_auth("ok")  # un rafraîchissement réussi lève l'alerte
            return jeton["access_token"]
        if code in (400, 401) or rep.get("error") in ("invalid_grant", "invalid_client", "unauthorized_client"):
            raise ErreurAuth(f"jeton refusé ({rep.get('error', code)}) : refaire la connexion avec auth.py")
        raise ErreurReseau(f"rafraîchissement du jeton impossible (HTTP {code})")


def _verifier_pkce() -> tuple[str, str]:
    verif = base64.urlsafe_b64encode(aleatoire.token_bytes(48)).rstrip(b"=").decode()
    defi = base64.urlsafe_b64encode(hashlib.sha256(verif.encode()).digest()).rstrip(b"=").decode()
    return verif, defi


PAGE_OK = "<html><meta charset=utf-8><body style='font-family:sans-serif'><h2>Connexion réussie</h2><p>Tu peux fermer cet onglet et retourner au terminal.</p></body></html>"
PAGE_KO = "<html><meta charset=utf-8><body style='font-family:sans-serif'><h2>Connexion refusée</h2><p>Retourne au terminal pour voir le détail.</p></body></html>"


def autoriser(ouvrir_navigateur: bool = True, attente_s: int = 300, afficher=print) -> dict:
    """Flux complet. Retourne le jeton écrit. Le propriétaire clique « Autoriser » dans son navigateur."""
    client = charger_client()
    verif, defi = _verifier_pkce()
    etat = aleatoire.token_urlsafe(24)
    recu: dict = {}

    class Reception(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if "code" in q or "error" in q:
                recu.update(q)
            corps = (PAGE_OK if "code" in q else PAGE_KO).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, *a):
            pass

    serveur = HTTPServer(("127.0.0.1", 0), Reception)
    redirection = f"http://127.0.0.1:{serveur.server_address[1]}"
    url = client["auth_uri"] + "?" + urllib.parse.urlencode({
        "client_id": client["client_id"], "redirect_uri": redirection, "response_type": "code",
        "scope": PORTEE, "code_challenge": defi, "code_challenge_method": "S256", "state": etat,
        "access_type": "offline", "prompt": "consent"})
    afficher("Ouvre ce lien dans ton navigateur et autorise l'accès à ta chaîne YouTube :\n" + url)
    if ouvrir_navigateur:
        webbrowser.open(url)
    fin = time.time() + attente_s
    serveur.timeout = 1
    while not recu and time.time() < fin:
        serveur.handle_request()
    serveur.server_close()
    if not recu:
        raise ErreurAuth("délai dépassé : aucune réponse du navigateur")
    if recu.get("error"):
        raise ErreurAuth(f"autorisation refusée : {recu['error']}")
    if recu.get("state") != etat:
        raise ErreurAuth("réponse inattendue (paramètre state différent) : connexion abandonnée")
    code, rep = _poster(client["token_uri"], {
        "client_id": client["client_id"], "client_secret": client["client_secret"], "code": recu["code"],
        "code_verifier": verif, "grant_type": "authorization_code", "redirect_uri": redirection})
    if code != 200 or not rep.get("refresh_token"):
        raise ErreurAuth(f"échange du code refusé ({rep.get('error', code)}) : {rep.get('error_description', '')}")
    jeton = {"access_token": rep["access_token"], "refresh_token": rep["refresh_token"],
             "expiry": time.time() + int(rep.get("expires_in", 3600)), "scope": rep.get("scope", PORTEE),
             "token_type": rep.get("token_type", "Bearer"), "maj": common.now()}
    common.write_json(chemin_jeton(), jeton)
    noter_etat_auth("ok")
    return jeton


def statut() -> dict:
    jeton = common.read_json(chemin_jeton())
    return {"client_secret": chemin_client().exists(),
            "jeton": bool(jeton and jeton.get("refresh_token")),
            "acces_valide_encore_s": int(jeton.get("expiry", 0) - time.time()) if jeton else None,
            "etat_auth": common.read_json(chemin_etat_auth())}


if __name__ == "__main__":
    try:
        if "--statut" in sys.argv:
            print(json.dumps(statut(), ensure_ascii=False, indent=1))
        else:
            autoriser(ouvrir_navigateur="--sans-navigateur" not in sys.argv)
            print("Jeton enregistré dans autopilot/secrets/token.json. C'est terminé.")
    except (ErreurAuth, ErreurReseau) as e:
        print(f"ÉCHEC : {e}", file=sys.stderr)
        sys.exit(3)
