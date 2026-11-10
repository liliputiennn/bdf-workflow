"""Rendu « créateur » des formats maison : compositions Remotion (src/formats/) à la place des images Pillow.

- `disponible()` : Remotion utilisable ? (node + npx + dossier node_modules). Sinon les formats retombent sur le rendu Pillow (rendu.py), qui reste
  la référence légère et celle des tests : `BDF_RENDU=pillow` force ce repli, `BDF_RENDU=remotion` l'exige.
- `rendre_video(compo, props, sortie, ...)` : lance `remotion render` avec les props en JSON ; le son n'est PAS produit ici (la voix et l'ambiance
  sont mixées par ffmpeg comme avant, ce qui garde les contrôles de volume et de pic intacts).
- Polices : Bricolage Grotesque, Fraunces, Lexend (SIL OFL, via @remotion/google-fonts).
- Jamais de calcul lourd sur le PC de l'utilisateur : la fabrication tourne dans GitHub Actions (fabrique.yml) ; en local on ne rend que des aperçus courts.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]  # section3-motion/pixel-faits
ENTREE = "src/formats/entry.ts"


def _npx() -> str | None:
    return shutil.which("npx.cmd") or shutil.which("npx")


def disponible() -> bool:
    mode = os.environ.get("BDF_RENDU", "").lower()
    if mode == "pillow":
        return False
    ok = _npx() is not None and (RACINE / "node_modules" / "remotion").exists() and (RACINE / ENTREE).exists()
    if mode == "remotion" and not ok:
        raise RuntimeError("BDF_RENDU=remotion mais Remotion est introuvable (npm ci ?)")
    return ok


def rendre_video(compo: str, props: dict, sortie: Path, concurrence: int | None = None, crf: int = 23, echelle: float = 1.0, plage: tuple[int, int] | None = None) -> Path:
    """Rend `compo` en mp4 H.264 muet. `plage` = (première, dernière image) pour un extrait."""
    sortie = Path(sortie)
    fichier = sortie.with_suffix(".props.json")
    fichier.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    cmd = [_npx(), "--no-install", "remotion", "render", ENTREE, compo, str(sortie), f"--props={fichier}", "--codec=h264", f"--crf={crf}", "--muted",
           f"--concurrency={concurrence or int(os.environ.get('BDF_REMOTION_CONC', '2'))}", "--log=error", "--overwrite"]
    if echelle != 1.0:
        cmd.append(f"--scale={echelle}")
    if plage:
        cmd.append(f"--frames={plage[0]}-{plage[1]}")
    try:
        r = subprocess.run(cmd, cwd=RACINE, capture_output=True, text=True, timeout=int(os.environ.get("BDF_REMOTION_TIMEOUT_S", "7200")))
    finally:
        fichier.unlink(missing_ok=True)
    if r.returncode or not sortie.exists():
        raise RuntimeError(f"remotion a échoué ({compo}) : {(r.stderr or r.stdout)[-600:]}")
    return sortie


def rendre_image(compo: str, props: dict, sortie: Path, image: int) -> Path:
    sortie = Path(sortie)
    fichier = sortie.with_suffix(".props.json")
    fichier.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    cmd = [_npx(), "--no-install", "remotion", "still", ENTREE, compo, str(sortie), f"--props={fichier}", f"--frame={image}", "--log=error", "--overwrite"]
    try:
        r = subprocess.run(cmd, cwd=RACINE, capture_output=True, text=True, timeout=600)
    finally:
        fichier.unlink(missing_ok=True)
    if r.returncode or not sortie.exists():
        raise RuntimeError(f"remotion still a échoué ({compo}) : {(r.stderr or r.stdout)[-600:]}")
    return sortie


# ---------------------------------------------------------------- props par format
def _mots_alignes(texte: str, mots_voix: list[dict]) -> list[dict]:
    """Un objet {w, s, e} par mot du texte affiché, recalé sur les mots entendus (leur nombre peut différer)."""
    mots = texte.split()
    n, m = len(mots), len(mots_voix)
    if not n:
        return []
    out = []
    for k, w in enumerate(mots):
        if not m:
            out.append({"w": w, "s": 0.0, "e": 0.0})
            continue
        j = k if m == n else round(k * (m - 1) / max(1, n - 1))
        out.append({"w": w, "s": float(mots_voix[j]["start"]), "e": float(mots_voix[j].get("end", mots_voix[j]["start"] + 0.3))})
    return out


def props_langue(ep: dict, timings: dict, plan: list[dict], chrono: dict, w: int, h: int, fps: int, total: float, nom_chaine: str, nom_langue: str) -> dict:
    lg = timings["lines"]
    lecons = []
    for k, (p, c) in enumerate(zip(plan, chrono["lecons"])):
        l = ep["lecons"][k]
        lecons.append({"fr": l["fr"].strip(), "cible": l["cible"].strip(), "phonetique": (l.get("phonetique") or "").strip() or None,
                       "t_f": c["t_f"], "t_c": c["t_c"], "t_l": c["t_l"], "fin_l": c["fin_l"], "suite": c["suite"],
                       "mots_c": _mots_alignes(l["cible"], lg[p["cible"]]["words"]), "mots_l": _mots_alignes(l["cible"], lg[p["lent"]]["words"])})
    return {"w": w, "h": h, "fps": fps, "total": round(total, 3), "chaine": nom_chaine, "langue": nom_langue, "situation": ep["situation"].strip(),
            "t_outro": chrono["t_outro"], "lecons": lecons}


def props_boucle(format_: str, decor: str, graine: int, w: int, h: int, fps: int, boucle: int, titre: str = "") -> dict:
    return {"w": w, "h": h, "fps": fps, "boucle": boucle, "format": format_, "decor": decor, "graine": int(graine), "titre": titre}
