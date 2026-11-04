"""Images automatiques d'un épisode : trouve de vraies photos libres de droits qui montrent de quoi on parle.

Usage : python autopilot/visuels.py episodes-b/<id> [--dry-run]

Les scènes `photo` et `annonce` d'un épisode (Short : episode.json, long : episode-long.json, dans les chapitres) peuvent porter
`params.recherche` (mots-clés, de préférence en anglais, ex. « laser engraver wooden board »). Ce programme :
  1. cherche sur Wikimedia Commons puis Openverse, sans compte ni clé, des photos à licence commerciale (CC BY, CC BY-SA, CC0, domaine public ;
     jamais « NonCommercial » ni « NoDerivatives »), assez grandes ;
  2. les télécharge dans episodes-b/<id>/visuels/ ;
  3. renseigne `params.fichier` (chemin sous episodes-b) et `params.credit` dans le JSON de l'épisode ;
  4. ajoute à publication.json une ligne « Images : … » avec les auteurs et licences (l'attribution est obligatoire pour CC BY).
Une scène `photo` sans image trouvée est remplacée par de gros sous-titres (le rendu ne casse jamais) ; une scène `annonce` perd juste sa photo.
Idempotent : une scène déjà résolue (fichier présent) n'est pas refaite.
"""
import json, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import common  # noqa: E402

UA = "LaDebrouilleBot/1.0 (https://github.com/liliputiennn/bdf-workflow)"
LARGEUR_MIN = 900
LICENCE_OK = re.compile(r"\b(cc[- ]?by(?:[- ]sa)?|cc0|public domain|pd|domaine public)\b", re.I)
LICENCE_NON = re.compile(r"(\bnc\b|non[- ]?commercial|\bnd\b|no[- ]?deriv)", re.I)


def http_get(url: str, binaire: bool = False):
    """urllib d'abord ; si le certificat est refusé (antivirus qui s'interpose sur le PC), curl de Windows prend le relais."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=40).read()
    except Exception:  # noqa: BLE001
        data = subprocess.run(["curl", "-sL", "-m", "60", "-A", UA, url], capture_output=True, check=True).stdout
    return data if binaire else json.loads(data.decode("utf-8"))


def nettoie(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def pertinent(q: str, texte: str) -> bool:
    """Garde-fou : la photo doit parler du sujet (au moins un mot de la recherche dans son titre ou sa description)."""
    mots = [w for w in re.findall(r"[a-zà-ÿ0-9]+", q.lower()) if len(w) > 3]
    t = texte.lower()
    return not mots or any(w in t for w in mots)


def licence_ok(nom: str) -> bool:
    return bool(nom) and bool(LICENCE_OK.search(nom)) and not LICENCE_NON.search(nom)


def candidats_commons(q: str) -> list[dict]:
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 12,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1280, "format": "json"})
    out = []
    for p in sorted(((http_get(u).get("query") or {}).get("pages") or {}).values(), key=lambda x: x.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        em = ii.get("extmetadata") or {}
        lic = (em.get("LicenseShortName") or {}).get("value", "")
        desc = nettoie((em.get("ImageDescription") or {}).get("value", ""))
        if ii.get("mime") in ("image/jpeg", "image/png") and ii.get("width", 0) >= LARGEUR_MIN and licence_ok(lic) and pertinent(q, p.get("title", "") + " " + desc):
            out.append({"url": ii.get("thumburl") or ii["url"], "auteur": re.sub(r"^(auteur|author)\s*:\s*", "", nettoie((em.get("Artist") or {}).get("value", "")), flags=re.I) or "auteur inconnu",
                        "licence": lic, "source": "Wikimedia Commons", "titre": p.get("title", "")})
    return out


def candidats_openverse(q: str) -> list[dict]:
    u = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode({"q": q, "license_type": "commercial", "page_size": 12, "mature": "false"})
    out = []
    for r in http_get(u).get("results", []):
        lic = f"{r.get('license', '')} {r.get('license_version', '')}".strip()
        etiquettes = " ".join(t.get("name", "") for t in r.get("tags") or [])
        if r.get("width", 0) >= LARGEUR_MIN and licence_ok(lic) and r.get("url") and pertinent(q, f"{r.get('title', '')} {etiquettes}"):
            out.append({"url": r["url"], "auteur": r.get("creator") or "auteur inconnu", "licence": "CC " + lic.upper() if not lic.upper().startswith("CC") else lic,
                        "source": r.get("source") or "Openverse", "titre": r.get("title", "")})
    return out


def trouver(q: str) -> dict | None:
    for chercher in (candidats_commons, candidats_openverse):
        try:
            for c in chercher(q):
                return c
        except Exception as e:  # noqa: BLE001
            print(f"  recherche {chercher.__name__} impossible : {e}")
    return None


def scenes_a_resoudre(doc: dict):
    """Toutes les scènes photo/annonce avec une recherche, dans un Short (`scenes`) ou un long (`chapitres[*].scenes`)."""
    listes = [doc.get("scenes") or []] + [c.get("scenes") or [] for c in doc.get("chapitres") or []]
    for lst in listes:
        for s in lst:
            if s.get("type") in ("photo", "annonce") and (s.get("params") or {}).get("recherche"):
                yield lst, s


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    dossier = Path([a for a in argv if not a.startswith("--")][0]).resolve()
    ep_id = dossier.name
    fichier_json = dossier / "episode-long.json" if (dossier / "episode-long.json").exists() else dossier / "episode.json"
    doc = json.loads(fichier_json.read_text(encoding="utf-8"))
    credits: list[str] = []
    (dossier / "visuels").mkdir(exist_ok=True) if not dry else None
    n_ok = n_manque = 0
    for lst, s in list(scenes_a_resoudre(doc)):
        p = s["params"]
        if p.get("fichier") and (common.EPISODES / p["fichier"]).exists():
            continue
        q = p["recherche"]
        c = trouver(q)
        if not c:
            print(f"  « {q} » : aucune photo libre trouvée")
            n_manque += 1
            if s["type"] == "photo":
                s["type"], s["params"] = "titre-geant", {}
            else:
                p.pop("fichier", None)
            continue
        ext = ".png" if c["url"].lower().split("?")[0].endswith(".png") else ".jpg"
        nom = f"{re.sub(r'[^a-z0-9]+', '-', q.lower()).strip('-')[:40]}{ext}"
        print(f"  « {q} » -> {c['source']} : {c['titre'][:50]} ({c['licence']}, {c['auteur'][:30]})")
        if not dry:
            (dossier / "visuels" / nom).write_bytes(http_get(c["url"], binaire=True))
            p["fichier"] = f"{ep_id}/visuels/{nom}"
        p["credit"] = f"Photo : {c['auteur'][:40]}, {c['licence']}"
        credits.append(f"{c['auteur'][:60]} ({c['licence']}, {c['source']})")
        n_ok += 1
    if not dry:
        fichier_json.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        pub = dossier / "publication.json"
        if credits and pub.exists():
            d = json.loads(pub.read_text(encoding="utf-8"))
            if "Images :" not in d.get("description", ""):
                ligne = "Images : " + " ; ".join(dict.fromkeys(credits))
                d["description"] = (d["description"].rstrip() + "\n\n" + ligne[:600]).strip()
                pub.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"visuels : {n_ok} trouvée(s), {n_manque} manquante(s)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1:]))
