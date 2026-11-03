"""Faux serveur YouTube + OAuth local pour les tests (aucun accès réseau réel)."""
import json
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FauxYouTube:
    def __init__(self):
        self.demandes: list[tuple[str, str]] = []
        self.sessions: dict[str, dict] = {}
        self.videos: dict[str, dict] = {}
        self.appels_jeton = 0
        self.jeton_courant = None
        # comportements pilotables par les tests
        self.refus_jeton = False          # /token répond invalid_grant
        self.quota_ouverture = False      # ouverture de session -> 403 quotaExceeded
        self.erreur_ouverture: tuple[int, str] | None = None
        self.pannes_ouverture = 0         # nombre de 503 avant de réussir
        self.coupure_au_morceau: int | None = None  # coupe la connexion en plein 2e morceau, une fois
        self.force_prive = False          # relecture : privé sans publishAt (projet non audité)
        self.deja_public = False          # relecture : public
        self.miniature_refusee = False
        self.maj_ignoree = False          # videos.update sans effet (projet non audité)
        self.exiger_jeton_recent = False  # 401 si le jeton n'est pas le dernier émis
        self.morceaux_recus = 0
        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.serveur.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=lambda: self.serveur.serve_forever(poll_interval=0.02), daemon=True).start()

    def arreter(self):
        self.serveur.shutdown()
        self.serveur.server_close()

    def appels(self, debut: str) -> list[str]:
        return [c for m, c in self.demandes if c.startswith(debut)]

    def _handler(self):
        faux = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _corps(self) -> bytes:
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def _rep(self, code, obj=None, entetes=None):
                data = json.dumps(obj).encode() if obj is not None else b""
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for k, v in (entetes or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def _erreur(self, code, raison, message="erreur"):
                self._rep(code, {"error": {"code": code, "message": message, "errors": [{"reason": raison}]}})

            def _auth_ok(self) -> bool:
                if faux.exiger_jeton_recent and self.headers.get("Authorization") != f"Bearer {faux.jeton_courant}":
                    self._erreur(401, "authError", "jeton périmé")
                    return False
                return True

            def _statut_video(self, vid):
                v = faux.videos[vid]
                st = {"uploadStatus": "processed", **v["status"]}
                if faux.deja_public:
                    st.update(privacyStatus="public")
                    st.pop("publishAt", None)
                elif faux.force_prive:
                    st.update(privacyStatus="private")
                    st.pop("publishAt", None)
                return {"id": vid, "status": st}

            def do_POST(self):  # noqa: N802
                chemin = urllib.parse.urlparse(self.path)
                faux.demandes.append(("POST", chemin.path))
                corps = self._corps()
                if chemin.path == "/token":
                    champs = dict(urllib.parse.parse_qsl(corps.decode()))
                    faux.appels_jeton += 1
                    if faux.refus_jeton or champs.get("grant_type") != "refresh_token":
                        return self._rep(400, {"error": "invalid_grant"})
                    faux.jeton_courant = f"jeton-{faux.appels_jeton}"
                    return self._rep(200, {"access_token": faux.jeton_courant, "expires_in": 3600})
                if not self._auth_ok():
                    return
                if chemin.path == "/upload/youtube/v3/videos":
                    if faux.quota_ouverture:
                        return self._erreur(403, "quotaExceeded", "The request cannot be completed")
                    if faux.erreur_ouverture:
                        return self._erreur(*faux.erreur_ouverture)
                    if faux.pannes_ouverture > 0:
                        faux.pannes_ouverture -= 1
                        return self._erreur(503, "backendError")
                    meta = json.loads(corps)
                    sid = f"s{len(faux.sessions) + 1}"
                    faux.sessions[sid] = {"meta": meta, "data": bytearray(), "taille": int(self.headers["X-Upload-Content-Length"]),
                                          "ouverture_requete": dict(self.headers)}
                    return self._rep(200, None, {"Location": f"{faux.base}/session/{sid}"})
                if chemin.path == "/upload/youtube/v3/thumbnails/set":
                    if faux.miniature_refusee:
                        return self._erreur(403, "forbidden", "custom thumbnails need verification")
                    q = dict(urllib.parse.parse_qsl(chemin.query))
                    faux.videos[q["videoId"]]["miniature"] = corps
                    return self._rep(200, {"items": []})
                self._erreur(404, "notFound")

            def do_PUT(self):  # noqa: N802
                chemin = urllib.parse.urlparse(self.path)
                faux.demandes.append(("PUT", chemin.path))
                corps = self._corps()
                if not self._auth_ok():
                    return
                m = re.fullmatch(r"/session/(\w+)", chemin.path)
                if m:
                    return self._session(m.group(1), corps)
                if chemin.path == "/youtube/v3/videos":
                    maj = json.loads(corps)
                    if not faux.maj_ignoree:
                        faux.videos[maj["id"]]["status"].update(maj["status"])
                        faux.videos[maj["id"]]["status"].pop("publishAt", None)
                        faux.force_prive = False
                    return self._rep(200, {"id": maj["id"], "status": maj["status"]})
                self._erreur(404, "notFound")

            def _session(self, sid, corps):
                s = faux.sessions.get(sid)
                if not s:
                    return self._erreur(404, "notFound")
                cr = self.headers.get("Content-Range", "")
                recu = len(s["data"])
                if cr.startswith("bytes */"):
                    if recu >= s["taille"]:
                        return self._rep(201, faux._creer_video(sid))
                    return self._rep(308, None, {"Range": f"bytes=0-{recu - 1}"} if recu else {})
                a, b, _ = (int(x) for x in re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", cr).groups())
                if a != recu:
                    return self._erreur(400, "badContentRange")
                faux.morceaux_recus += 1
                if faux.coupure_au_morceau == faux.morceaux_recus:
                    faux.coupure_au_morceau = None
                    s["data"] += corps[: len(corps) // 2]
                    self.close_connection = True
                    return  # pas de réponse : connexion coupée
                s["data"] += corps
                if len(s["data"]) >= s["taille"]:
                    return self._rep(201, faux._creer_video(sid))
                self._rep(308, None, {"Range": f"bytes=0-{len(s['data']) - 1}"})

            def do_GET(self):  # noqa: N802
                chemin = urllib.parse.urlparse(self.path)
                q = dict(urllib.parse.parse_qsl(chemin.query))
                faux.demandes.append(("GET", chemin.path))
                if not self._auth_ok():
                    return
                if chemin.path == "/youtube/v3/videos":
                    ids = [i for i in q["id"].split(",") if i in faux.videos]
                    return self._rep(200, {"items": [faux._statut(i, self) for i in ids]})
                if chemin.path == "/youtube/v3/channels":
                    return self._rep(200, {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
                if chemin.path == "/youtube/v3/playlistItems":
                    return self._rep(200, {"items": [{"contentDetails": {"videoId": v}} for v in faux.videos]})
                self._erreur(404, "notFound")

        return H

    def _statut(self, vid, h):
        return h._statut_video(vid)

    def _creer_video(self, sid):
        s = self.sessions[sid]
        vid = f"vid{sid}"
        self.videos[vid] = {"status": dict(s["meta"]["status"]), "snippet": s["meta"]["snippet"], "octets": bytes(s["data"])}
        return {"id": vid, "status": s["meta"]["status"], "snippet": s["meta"]["snippet"]}
