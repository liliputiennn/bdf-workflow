"""Brique « miniatures » : rend la miniature YouTube (1280×720), la contrôle, puis fait passer l'épisode de `controle` à `pret`.

Usage :
  python autopilot/miniature.py <id>                      épisode en état `controle` -> `pret` (ou `quarantaine`)
  python autopilot/miniature.py <id> --sans-etat          rend + contrôle sans toucher à status.json (essais, exemples)
  python autopilot/miniature.py <id> --sortie f.png [--style chiffre|question|contraste|telephone|pile|createur] [--theme nuit-vert]
                                  [--miniature '{"gros":"14 %"}']   un seul rendu précis, sans alternative

Entrées   episodes-b/<id>/episode.json (+ faits.json, publication.json s'ils existent), miniatures-manuelles/<id>.png (prioritaire)
Sorties   episodes-b/<id>/miniature.png (≤ 2 Mo ; au-delà : miniature.jpg, signalé dans status.json), miniature_report.json
Code retour : 0 = prête, 2 = quarantaine, 1 = rien à faire (l'épisode n'est pas à l'état `controle`) ou verrou occupé.

Contrôle automatique (sur la version 168×94 px, taille d'une vignette mobile) :
  - le texte principal occupe au moins un tiers de la largeur ;
  - contraste texte / fond ≥ 4,5 (WCAG) ;
  - le texte ne touche pas les bords ni la zone de la durée affichée par YouTube (coin bas droit).
En cas d'échec, une autre mise en page est essayée ; si toutes échouent, l'épisode part en quarantaine avec la raison.
Le texte principal est repéré grâce à un second rendu « masque » (texte en rouge/vert/bleu pur sur noir) : aucune devinette.
"""
import argparse
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

W, H = 1280, 720
VW, VH = 168, 94
MAX_OCTETS = 2 * 1024 * 1024
STYLES = ["chiffre", "question", "contraste", "telephone", "pile", "createur"]
SEUIL_CONTRASTE = 4.5
SEUIL_LARGEUR = 1 / 3
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# zone masquée par la durée affichée par YouTube (coin bas droit), en fractions de l'image
ZONE_DUREE = (0.86, 0.90)


# ---------- logique de contrôle (pure, testée dans autopilot/tests/test_miniature.py) ----------

def luminance(rgb) -> float:
    """Luminance relative WCAG d'une couleur sRGB (0-255)."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def ratio_contraste(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _dilate(m: list[list[bool]], r: int) -> list[list[bool]]:
    h, w = len(m), len(m[0])
    horiz = [[any(row[max(0, x - r):x + r + 1]) for x in range(w)] for row in m]
    return [[any(horiz[yy][x] for yy in range(max(0, y - r), min(h, y + r + 1))) for x in range(w)] for y in range(h)]


def decouper(rgb: bytes, w: int, h: int) -> list[list[tuple[int, int, int]]]:
    return [[(rgb[(y * w + x) * 3], rgb[(y * w + x) * 3 + 1], rgb[(y * w + x) * 3 + 2]) for x in range(w)] for y in range(h)]


def analyser_canal(vignette, masque, canal: int, w: int, h: int) -> dict:
    """Mesure un groupe de texte (canal du masque : 0 rouge, 1 vert, 2 bleu) dans la vignette."""
    coeur = [[masque[y][x][canal] >= 153 for x in range(w)] for y in range(h)]       # ≥ 0,6 : intérieur des lettres
    large = [[masque[y][x][canal] >= 77 for x in range(w)] for y in range(h)]        # ≥ 0,3 : emprise complète
    n = sum(map(sum, coeur))
    if n == 0:
        return {"present": False, "pixels": 0}
    xs = [x for y in range(h) for x in range(w) if large[y][x]]
    ys = [y for y in range(h) for x in range(w) if large[y][x]]
    x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    autre = [[max(masque[y][x]) >= 38 for x in range(w)] for y in range(h)]          # toute lettre, tout groupe
    proche = _dilate(coeur, 4)
    exclu = _dilate(autre, 1)
    anneau = [(x, y) for y in range(h) for x in range(w) if proche[y][x] and not exclu[y][x]]
    lt = statistics.median(luminance(vignette[y][x]) for y in range(h) for x in range(w) if coeur[y][x])
    out = {
        "present": True, "pixels": n, "largeur": (x1 - x0) / w, "hauteur": (y1 - y0) / h,
        "bbox": [x0, y0, x1, y1], "lum_texte": round(lt, 4),
    }
    if len(anneau) >= 10:
        lr = [luminance(vignette[y][x]) for x, y in anneau]
        out["lum_fond"] = round(statistics.median(lr), 4)
        out["contraste"] = round(ratio_contraste(lt, statistics.median(lr)), 2)
    else:
        out["contraste"] = None
    zx, zy = ZONE_DUREE
    out["sous_duree"] = any(large[y][x] for y in range(int(h * zy), h) for x in range(int(w * zx), w))
    out["coupe"] = x0 < 1 or y0 < 1 or x1 > w - 1 or y1 > h - 1
    return out


def controler(vignette, masque, w: int = VW, h: int = VH) -> dict:
    """Verdict du contrôle de lisibilité. Seul le groupe rouge (texte principal) bloque ; vert et bleu sont rapportés."""
    canaux = {nom: analyser_canal(vignette, masque, i, w, h) for i, nom in enumerate(["principal", "second", "legendes"])}
    raisons = []
    p = canaux["principal"]
    if not p["present"] or p["pixels"] < 12:
        raisons.append("texte principal introuvable ou trop petit en vignette 168×94")
    else:
        if p["largeur"] < SEUIL_LARGEUR:
            raisons.append(f"texte principal trop étroit : {p['largeur']:.0%} de la largeur (minimum {SEUIL_LARGEUR:.0%})")
        if p["contraste"] is None:
            raisons.append("contraste du texte principal non mesurable")
        elif p["contraste"] < SEUIL_CONTRASTE:
            raisons.append(f"contraste texte/fond trop faible : {p['contraste']} (minimum {SEUIL_CONTRASTE})")
        if p["coupe"]:
            raisons.append("texte principal coupé par le bord de l'image")
        if p["sous_duree"]:
            raisons.append("texte principal sous la durée affichée par YouTube (coin bas droit)")
    return {"ok": not raisons, "raisons": raisons, "canaux": canaux}


def lire_png(path: Path) -> tuple[int, int]:
    """Largeur, hauteur d'un PNG (en-tête IHDR). Lève ValueError si ce n'est pas un PNG."""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != PNG_SIGNATURE or head[12:16] != b"IHDR":
        raise ValueError("ce n'est pas un fichier PNG")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def verifier_manuelle(path: Path) -> list[str]:
    """Raisons pour lesquelles une miniature faite à la main est refusée (liste vide = acceptée)."""
    try:
        w, h = lire_png(path)
    except (ValueError, OSError) as e:
        return [f"fichier illisible ({e})"]
    raisons = []
    if (w, h) != (W, H):
        raisons.append(f"{w}×{h} au lieu de {W}×{H}")
    taille = path.stat().st_size
    if taille > MAX_OCTETS:
        raisons.append(f"{taille / 1048576:.1f} Mo au lieu de 2 Mo maximum")
    return raisons


def ordre_styles(demande: str | None, a_un_nombre: bool) -> list[str]:
    """Style demandé (ou le plus probable) d'abord, puis les autres : ce sont les mises en page de secours."""
    premier = demande if demande in STYLES else ("createur" if a_un_nombre else "question")
    # secours : les styles « créateur » d'abord (ils passent le même contrôle), puis les anciens
    preference = ["createur", "telephone", "pile", "chiffre", "question", "contraste"]
    return [premier] + [s for s in preference if s != premier and s in STYLES]


# ---------- rendu ----------

def _npx() -> str:
    exe = shutil.which("npx")
    if not exe:
        raise RuntimeError("npx introuvable dans le PATH")
    return exe


def still(props: dict, out: Path, work: Path) -> None:
    """Un rendu Remotion Still (2 tentatives)."""
    work.mkdir(parents=True, exist_ok=True)
    pf = work / f"props-{out.stem}.json"
    pf.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    cmd = [_npx(), "remotion", "still", "src/miniature/index.ts", "Miniature", str(out), f"--props={pf}", "--public-dir=episodes-b", "--log=error"]
    last = None
    for _ in range(2):
        last = subprocess.run(cmd, cwd=common.ROOT, capture_output=True, text=True, timeout=420)
        if last.returncode == 0 and out.exists():
            return
    raise RuntimeError(f"rendu Remotion échoué : {(last.stderr or last.stdout).strip()[-400:]}")


def pixels_vignette(png: Path) -> bytes:
    """L'image réduite à 168×94 (moyenne par zones, comme un affichage de vignette), en RGB brut."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(png), "-vf", f"scale={VW}:{VH}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=60,
    )
    if r.returncode != 0 or len(r.stdout) != VW * VH * 3:
        raise RuntimeError(f"réduction ffmpeg échouée : {r.stderr.decode(errors='replace')[-200:]}")
    return r.stdout


def png_vers_jpeg(png: Path, jpg: Path, q: int) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-q:v", str(q), str(jpg)], check=True, timeout=60)


def sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def essayer(props_base: dict, style: str, work: Path) -> dict:
    """Rend la miniature et son masque pour un style, puis la contrôle."""
    props = {**props_base, "style": style}
    img, msk = work / f"essai-{style}.png", work / f"masque-{style}.png"
    still(props, img, work)
    still({**props, "masque": True}, msk, work)
    vignette = decouper(pixels_vignette(img), VW, VH)
    masque = decouper(pixels_vignette(msk), VW, VH)
    verdict = controler(vignette, masque)
    return {"style": style, "image": img, "hash": sha(img), **verdict}


def ecrire_finale(src_png: Path, dest_dir: Path) -> Path:
    """Copie la miniature : miniature.png si ≤ 2 Mo, sinon JPEG de qualité décroissante nommé miniature.jpg."""
    png, jpg = dest_dir / "miniature.png", dest_dir / "miniature.jpg"
    if src_png.stat().st_size <= MAX_OCTETS:
        shutil.copyfile(src_png, png)
        jpg.unlink(missing_ok=True)
        return png
    for q in (2, 4, 6, 9, 13, 18, 24, 31):
        png_vers_jpeg(src_png, jpg, q)
        if jpg.stat().st_size <= MAX_OCTETS:
            png.unlink(missing_ok=True)
            return jpg
    raise RuntimeError("impossible de passer sous 2 Mo")


def fabriquer(ep_id: str, style: str | None = None, theme: str | None = None, miniature: dict | None = None, alternatives: bool = True) -> dict:
    """Rend la meilleure miniature automatique. Renvoie {ok, essais, retenu?, raison?}."""
    ep = common.read_json(common.ep_dir(ep_id) / "episode.json")
    if ep is None:
        raise RuntimeError("episode.json introuvable ou illisible")
    faits = common.read_json(common.ep_dir(ep_id) / "faits.json", []) or []
    a_un_nombre = any(any(c.isdigit() for c in str(f.get("valeur", ""))) for f in faits if isinstance(f, dict))
    voulu = style or (ep.get("miniature") or {}).get("style")
    ordre = ordre_styles(voulu, a_un_nombre) if alternatives else [style]
    work = common.ep_dir(ep_id) / "cache" / "miniature"
    base = {"id": ep_id}
    if theme:
        base["theme"] = theme
    if miniature:
        base["miniature"] = miniature
    essais, vus = [], set()
    for st in ordre:
        e = essayer(base, st, work)
        if e["hash"] in vus:  # style impossible faute de données : le moteur s'est replié sur un style déjà vu
            e["raisons"] = ["identique à un essai précédent (données insuffisantes pour ce style)"]
            e["ok"] = False
            e["doublon"] = True
        vus.add(e["hash"])
        essais.append(e)
        if e["ok"]:
            return {"ok": True, "essais": essais, "retenu": e}
    reels = [e for e in essais if not e.get("doublon")]
    meilleur = max(reels, key=lambda e: (e["canaux"]["principal"].get("contraste") or 0))
    return {"ok": False, "essais": essais, "meilleur": meilleur, "raison": "; ".join(f"{e['style']} : {' / '.join(e['raisons'])}" for e in reels)}


def resume(e: dict) -> dict:
    p = e["canaux"]["principal"]
    return {"style": e["style"], "ok": e["ok"], "raisons": e["raisons"], "contraste": p.get("contraste"), "largeur_texte": round(p["largeur"], 3) if p.get("present") else None}


def traiter(ep_id: str, sans_etat: bool = False) -> int:
    d = common.ep_dir(ep_id)
    if not (d / "episode.json").exists():
        print(f"épisode inconnu : {ep_id}")
        return 1
    st = common.get_status(ep_id)
    if not sans_etat and st["etat"] != "controle":
        print(f"{ep_id} : état « {st['etat']} », la brique miniatures n'agit que sur « controle » (rien fait)")
        return 1

    def quarantaine(raison: str) -> int:
        print(f"{ep_id} : quarantaine — {raison}")
        if not sans_etat:
            common.set_status(ep_id, "quarantaine", f"miniature : {raison}", tentatives=st.get("tentatives", 0) + 1)
        return 2

    manuelle = common.ROOT / "miniatures-manuelles" / f"{ep_id}.png"
    rapport = {"maj": common.now()}
    try:
        if manuelle.exists():
            refus = verifier_manuelle(manuelle)
            if refus:
                return quarantaine("miniature manuelle refusée : " + ", ".join(refus))
            shutil.copyfile(manuelle, d / "miniature.png")
            (d / "miniature.jpg").unlink(missing_ok=True)
            info = {"source": "manuelle", "fichier": "miniature.png", "octets": manuelle.stat().st_size}
            rapport.update(info)
        else:
            res = fabriquer(ep_id)
            rapport["essais"] = [resume(e) for e in res["essais"]]
            if not res["ok"]:
                m = res["meilleur"]["image"]
                shutil.copyfile(m, d / "miniature_refusee.png")
                common.write_json(d / "miniature_report.json", rapport)
                return quarantaine("contrôle de lisibilité échoué sur toutes les mises en page (" + res["raison"] + ")")
            fin = ecrire_finale(res["retenu"]["image"], d)
            info = {"source": "auto", "fichier": fin.name, "style": res["retenu"]["style"], "octets": fin.stat().st_size}
            rapport.update(info)
            (d / "miniature_refusee.png").unlink(missing_ok=True)
    except Exception as e:  # une brique qui échoue ne bloque pas les autres
        if re.search(r"ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED|ERR_CONNECTION_\w+|ERR_NETWORK_CHANGED|ENOTFOUND|EAI_AGAIN|ETIMEDOUT|ECONNRESET|getaddrinfo failed", str(e)):
            print(f"{ep_id} : réseau indisponible pendant le rendu ({type(e).__name__}) : pas de quarantaine, nouvel essai au prochain passage")
            return 1
        return quarantaine(f"erreur technique ({type(e).__name__} : {e})")
    common.write_json(d / "miniature_report.json", rapport)
    if not sans_etat:
        common.set_status(ep_id, "pret", None, miniature=info)
    print(f"{ep_id} : miniature prête ({info['source']}, {info['fichier']}, {info['octets'] // 1024} Ko)" + ("" if sans_etat else " -> état « pret »"))
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--sans-etat", action="store_true", help="ne lit ni n'écrit status.json, pas de verrou d'état")
    ap.add_argument("--sortie", help="rend un seul fichier précis (avec --style/--theme/--miniature), sans toucher à l'épisode")
    ap.add_argument("--style", choices=STYLES)
    ap.add_argument("--theme")
    ap.add_argument("--miniature", help="JSON qui remplace des champs du champ « miniature » de l'épisode")
    a = ap.parse_args()
    try:
        with common.episode_lock(a.id):
            if a.sortie:
                spec = json.loads(a.miniature) if a.miniature else None
                res = fabriquer(a.id, a.style, a.theme, spec, alternatives=False)
                e = res["essais"][0]
                out = Path(a.sortie)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(e["image"], out)
                print(json.dumps(resume(e), ensure_ascii=False))
                return 0 if e["ok"] else 2
            return traiter(a.id, a.sans_etat)
    except TimeoutError as e:
        print(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
