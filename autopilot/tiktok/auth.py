"""Connexion TikTok (une seule fois) : navigateur + redirection 127.0.0.1 + PKCE.

Lit `autopilot/secrets/tiktok_client.json` (clé et secret de ton application TikTok, déposés par toi) et écrit
`autopilot/secrets/tiktok_token.json`. Ce programme ne crée aucun compte et ne connaît aucun mot de passe : tu te connectes
dans ton navigateur et tu autorises l'accès (portée `video.upload` : envoyer des vidéos dans ta boîte de réception TikTok).

    python autopilot/tiktok/auth.py             # connexion
    python autopilot/tiktok/auth.py --statut    # état du jeton, sans rien afficher de secret
"""
import argparse
import hashlib
import http.server
import json
import secrets as aleatoire
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import client as C  # noqa: E402

AUTORISATION = "https://www.tiktok.com/v2/auth/authorize/"
PORTEE = "video.upload"


def defi_pkce() -> tuple[str, str]:
    """(verifier, challenge) : TikTok attend le SHA-256 du verifier écrit en hexadécimal."""
    verifier = aleatoire.token_urlsafe(72)[:96]
    return verifier, hashlib.sha256(verifier.encode()).hexdigest()


def url_autorisation(client_key: str, redirect_uri: str, etat: str, challenge: str) -> str:
    return AUTORISATION + "?" + urllib.parse.urlencode({
        "client_key": client_key, "scope": PORTEE, "response_type": "code", "redirect_uri": redirect_uri,
        "state": etat, "code_challenge": challenge, "code_challenge_method": "S256"})


def attendre_code(etat: str, port: int = 0, delai_s: float = 300.0) -> tuple[str, int, dict]:
    """Serveur local éphémère : renvoie (code, port, erreur). Le chemin est /callback/ (à enregistrer chez TikTok)."""
    recu: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            if urllib.parse.urlsplit(self.path).path != "/callback/":
                self.send_response(404); self.end_headers(); return
            recu.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ok = "code" in q and q.get("state") == etat
            self.wfile.write(("<h2>Connexion réussie, tu peux fermer cet onglet.</h2>" if ok else "<h2>Connexion refusée ou invalide.</h2>").encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    srv.timeout = 1.0
    threading.Thread(target=lambda: None).start()
    fin = time.time() + delai_s
    while time.time() < fin and not recu:
        srv.handle_request()
    srv.server_close()
    return recu.get("code", ""), srv.server_address[1], recu


def connexion(port: int = 0, ouvrir=webbrowser.open, afficher=print) -> int:
    client = C.charger_client()
    verifier, challenge = defi_pkce()
    etat = aleatoire.token_urlsafe(24)
    # le port doit exister avant d'ouvrir le navigateur : on réserve le serveur d'abord
    srv_port = port
    if not srv_port:
        import socket
        s = socket.socket(); s.bind(("127.0.0.1", 0)); srv_port = s.getsockname()[1]; s.close()
    redirect = f"http://127.0.0.1:{srv_port}/callback/"
    url = url_autorisation(client["client_key"], redirect, etat, challenge)
    afficher("Ouverture du navigateur pour autoriser l'accès (portée : envoyer des vidéos dans ta boîte de réception TikTok).")
    afficher("Si rien ne s'ouvre, copie ce lien dans ton navigateur :\n" + url)
    ouvrir(url)
    code, _, recu = attendre_code(etat, srv_port)
    if not code or recu.get("state") != etat:
        afficher("Connexion non terminée : " + (recu.get("error_description") or recu.get("error") or "aucune réponse reçue à temps"))
        return 1
    jeton = C.echanger_code(client, urllib.parse.unquote(code), redirect, verifier)
    C.ecrire_atomique(C.FICHIER_JETON, jeton)
    afficher("Jeton enregistré dans autopilot/secrets/tiktok_token.json. C'est terminé.")
    return 0


def statut() -> dict:
    client = C.lire(C.FICHIER_CLIENT)
    j = C.lire(C.FICHIER_JETON)
    now = time.time()
    return {
        "client": bool(client and client.get("client_key") and client.get("client_secret")),
        "jeton": bool(j and j.get("access_token")),
        "acces_valide_encore_s": int(j["expire_a"] - now) if j else None,
        "renouvellement_dans_jours": round((j["refresh_expire_a"] - now) / 86400, 1) if j else None,
        "portee": (j or {}).get("scope"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--statut", action="store_true")
    ap.add_argument("--port", type=int, default=0, help="port local fixe (à enregistrer chez TikTok) ; 0 = au hasard (exige le port joker *)")
    a = ap.parse_args(argv)
    if a.statut:
        print(json.dumps(statut(), ensure_ascii=False, indent=1))
        return 0
    try:
        return connexion(a.port)
    except C.ErreurTikTok as e:
        print(f"Échec : {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
