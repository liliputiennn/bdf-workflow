"""OAuth « application de bureau » pour YouTube : navigateur + redirection 127.0.0.1 + PKCE.

Lit `autopilot/secrets/client_secret.json` (déposé par le propriétaire), écrit `autopilot/secrets/token.json`
(`token-<chaîne>.json` pour une autre chaîne : un jeton par chaîne YouTube, un seul client OAuth pour tout le projet).
Ce module ne crée ni client, ni compte, ni jeton de lui-même : le propriétaire se connecte dans son navigateur.

    python autopilot/publish/auth.py                       # connexion de la chaîne par défaut (une seule fois)
    python autopilot/publish/auth.py --chaine en           # connexion d'une autre chaîne (voir connecter_chaine.py, qui vérifie en plus la chaîne)
    python autopilot/publish/auth.py --statut [--chaine X] # état du jeton, sans rien afficher de secret
    python autopilot/publish/auth.py --ecrire-etat         # écrit state/jetons.json : pour chaque chaîne, jeton présent ou non (aucun secret)
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

import chaines  # noqa: E402
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


def nom_fichier_jeton(chaine: str | None = None) -> str:
    """Nom du fichier de jeton d'une chaîne (champ `jeton_fichier` de son profil ; token.json pour la chaîne par défaut)."""
    if not chaine or chaine == chaines.CHAINE_DEFAUT:
        p = chaines.profil(chaines.CHAINE_DEFAUT)
        return (p or {}).get("jeton_fichier") or "token.json"
    p = chaines.profil(chaine)
    if p is None:
        raise ErreurAuth(f"chaîne inconnue : {chaine} (profils dans autopilot/chaines/)")
    if not chaines.FICHIER_JETON_VALIDE.match(p["jeton_fichier"]) or p["jeton_fichier"] in ("client_secret.json", "tiktok_token.json", "tiktok_client.json"):
        raise ErreurAuth(f"profil {chaine} : jeton_fichier invalide")
    return p["jeton_fichier"]


def chemin_jeton(chaine: str | None = None) -> Path:
    return dossier_secrets() / nom_fichier_jeton(chaine)


def chemin_etat_auth(chaine: str | None = None) -> Path:
    return common.STATE / chaines.fichier_etat_auth(chaine or chaines.CHAINE_DEFAUT)


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


def noter_etat_auth(etat: str, raison: str | None = None, chaine: str | None = None) -> None:
    """`autopilot/state/youtube_auth.json` (`youtube_auth-<chaîne>.json` pour les autres) : l'orchestrateur s'y fie pour savoir si la publication est possible."""
    common.write_json(chemin_etat_auth(chaine), {"etat": etat, "raison": raison, "maj": common.now()})


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

    def __init__(self, horloge=time.time, chaine: str | None = None):
        self.horloge = horloge
        self.chaine = chaine or chaines.CHAINE_DEFAUT
        self._client = None

    def _charger(self) -> dict:
        jeton = common.read_json(chemin_jeton(self.chaine))
        if not jeton or not jeton.get("refresh_token"):
            option = "" if self.chaine == chaines.CHAINE_DEFAUT else f" --chaine {self.chaine}"
            raise ErreurAuth(f"aucun jeton pour la chaîne « {self.chaine} » : lancer `python autopilot/publish/auth.py{option}` (voir INSTALLATION.md et CONNECTER-UNE-CHAINE.md)")
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
            common.write_json(chemin_jeton(self.chaine), jeton)
            if (common.read_json(chemin_etat_auth(self.chaine), {}) or {}).get("etat") == "a_refaire":
                noter_etat_auth("ok", chaine=self.chaine)  # un rafraîchissement réussi lève l'alerte
            return jeton["access_token"]
        if code in (400, 401) or rep.get("error") in ("invalid_grant", "invalid_client", "unauthorized_client"):
            option = "" if self.chaine == chaines.CHAINE_DEFAUT else f" --chaine {self.chaine}"
            raise ErreurAuth(f"jeton refusé ({rep.get('error', code)}) : refaire la connexion avec auth.py{option}")
        raise ErreurReseau(f"rafraîchissement du jeton impossible (HTTP {code})")


def _verifier_pkce() -> tuple[str, str]:
    verif = base64.urlsafe_b64encode(aleatoire.token_bytes(48)).rstrip(b"=").decode()
    defi = base64.urlsafe_b64encode(hashlib.sha256(verif.encode()).digest()).rstrip(b"=").decode()
    return verif, defi


PAGE_OK = "<html><meta charset=utf-8><body style='font-family:sans-serif'><h2>Connexion réussie</h2><p>Tu peux fermer cet onglet et retourner au terminal.</p></body></html>"
PAGE_KO = "<html><meta charset=utf-8><body style='font-family:sans-serif'><h2>Connexion refusée</h2><p>Retourne au terminal pour voir le détail.</p></body></html>"


def autoriser(ouvrir_navigateur: bool = True, attente_s: int = 300, afficher=print, chaine: str | None = None) -> dict:
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
    common.write_json(chemin_jeton(chaine), jeton)
    noter_etat_auth("ok", chaine=chaine)
    return jeton


def statut(chaine: str | None = None) -> dict:
    jeton = common.read_json(chemin_jeton(chaine))
    return {"chaine": chaine or chaines.CHAINE_DEFAUT, "client_secret": chemin_client().exists(),
            "jeton": bool(jeton and jeton.get("refresh_token")),
            "acces_valide_encore_s": int(jeton.get("expiry", 0) - time.time()) if jeton else None,
            "etat_auth": common.read_json(chemin_etat_auth(chaine))}


def ecrire_etat_jetons() -> dict:
    """`autopilot/state/jetons.json` : pour chaque chaîne, un jeton est-il enregistré ? Seulement des booléens (aucun contenu de jeton) ;
    c'est ce que lisent l'orchestrateur et la web app, qui n'ont pas le droit d'ouvrir autopilot/secrets/."""
    client = chemin_client().exists()
    etat = {}
    for ident in chaines.charger_profils():
        try:
            jeton = common.read_json(chemin_jeton(ident))
        except ErreurAuth:
            jeton = None
        etat[ident] = {"connecte": bool(jeton and jeton.get("refresh_token")), "client": client, "maj": common.now()}
    common.write_json(common.STATE / "jetons.json", etat)
    return etat


if __name__ == "__main__":
    try:
        chaine_cli = sys.argv[sys.argv.index("--chaine") + 1] if "--chaine" in sys.argv else None
        if "--ecrire-etat" in sys.argv:
            ecrire_etat_jetons()
        elif "--statut" in sys.argv:
            print(json.dumps(statut(chaine_cli), ensure_ascii=False, indent=1))
        else:
            autoriser(ouvrir_navigateur="--sans-navigateur" not in sys.argv, chaine=chaine_cli)
            print(f"Jeton enregistré dans autopilot/secrets/{nom_fichier_jeton(chaine_cli)}. C'est terminé.")
    except (ErreurAuth, ErreurReseau) as e:
        print(f"ÉCHEC : {e}", file=sys.stderr)
        sys.exit(3)
