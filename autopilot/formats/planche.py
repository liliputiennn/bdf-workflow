"""Planche de styles : quelques images clés des rendus « créateur » (langues, sommeil, méditation) sur une seule feuille PNG + un extrait vidéo.

Usage : python autopilot/formats/planche.py [dossier_sortie]      (calcul léger : images fixes + un extrait de 8 s en demi-taille)
La voix est simulée (bips, tests/faux.py) : seul le style compte ici.
"""
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from autopilot.formats import apprendre, rendu, rendu_remotion as rr  # noqa: E402
from autopilot.formats.tests import faux  # noqa: E402


def props_langue_demo(tmp: Path, w=1080, h=1920, fps=30) -> dict:
    ep = json.loads((RACINE / "episodes-b" / "langues-anglais-au-cafe" / "episode.json").read_text(encoding="utf-8"))
    script = apprendre.script_voix(ep)
    tim = faux.fausse_voix(tmp, script["phrases"], script["pauses"])
    chrono = apprendre._chronologie(tim, script["plan"])
    return rr.props_langue(ep, tim, script["plan"], chrono, w, h, fps, chrono["total"] + 0.8, "La Débrouille", "Anglais"), chrono


def main(sortie: Path) -> None:
    sortie.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    props, chrono = props_langue_demo(tmp)
    L = chrono["lecons"]
    instants = [("intro", 0.9), ("mot 1", L[0]["t_c"] + 0.45), ("mot 3", L[0]["t_c"] + 1.0), ("lent", L[0]["t_l"] + 0.9), ("répète", L[0]["fin_l"] + 0.8), ("leçon 2", L[1]["t_c"] + 0.8), ("transition", L[1]["t_f"] - 0.25), ("fin", chrono["t_outro"] + 1.2)]
    imgs: list[tuple[str, Image.Image]] = []
    for nom, t in instants:
        p = sortie / f"langue-{nom.replace(' ', '_')}.png"
        rr.rendre_image("Fmt-Langue", props, p, int(t * props["fps"]))
        imgs.append((f"Langues · {nom}", Image.open(p).convert("RGB")))
    boucles = [("sommeil", "lune-sur-mer", 4, 7.0), ("sommeil", "nuit-etoilee", 7, 7.0), ("sommeil", "foret-brume", 3, 20.0), ("meditation", "aube-collines", 5, 3.0), ("meditation", "lac-doux", 9, 8.0), ("meditation", "souffle", 2, 12.0)]
    for fmt, decor, g, t in boucles:
        p = sortie / f"boucle-{fmt}-{decor}.png"
        rr.rendre_image("Fmt-Boucle", rr.props_boucle(fmt, decor, g, 1280, 720, 15, 30, "Séance du soir" if fmt == "meditation" else ""), p, int(t * 15))
        imgs.append((f"{fmt.capitalize()} · {decor}", Image.open(p).convert("RGB")))
    # feuille : 8 portraits (4 x 2) puis 6 paysages (3 x 2)
    pw, ph = 360, 640
    lw, lh = 480, 270
    marge = 24
    W = max(marge + 4 * (pw + marge), marge + 3 * (480 + marge + 100))
    H = marge + 2 * (ph + 50 + marge) + 2 * (lh + 50 + marge) + 70
    feuille = Image.new("RGB", (W, H), "#0B0B14")
    d = ImageDraw.Draw(feuille)
    d.text((marge, 20), "PLANCHE DE STYLES - formats créateur (Remotion)", font=rendu.police(30), fill="#FFFFFF")
    for i, (nom, im) in enumerate(imgs[:8]):
        x, y = marge + (i % 4) * (pw + marge), 70 + (i // 4) * (ph + 50 + marge)
        feuille.paste(im.resize((pw, ph), Image.LANCZOS), (x, y + 40))
        d.text((x, y + 4), nom, font=rendu.police(22), fill="#C9D3FF")
    y0 = 70 + 2 * (ph + 50 + marge)
    for i, (nom, im) in enumerate(imgs[8:]):
        x, y = marge + (i % 3) * (lw + marge + 100), y0 + (i // 3) * (lh + 50 + marge)
        feuille.paste(im.resize((lw, lh), Image.LANCZOS), (x, y + 40))
        d.text((x, y + 4), nom, font=rendu.police(22), fill="#C9D3FF")
    feuille.save(sortie / "planche.png")
    # extrait vidéo : leçon 1 de bout en bout, demi-taille
    fin = int((L[0]["suite"] + 0.6) * props["fps"])
    rr.rendre_video("Fmt-Langue", props, sortie / "extrait-langues.mp4", concurrence=2, echelle=0.5, plage=(0, fin))
    print("planche :", sortie / "planche.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RACINE / "apercus" / "planche-formats")
