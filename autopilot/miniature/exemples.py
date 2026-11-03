"""Rend les exemples de miniatures d'un épisode (chaque style × chaque thème) et une planche de comparaison.

Usage :  python autopilot/miniature/exemples.py [<id>] [--sortie _test-comparatif/sorties-b/miniatures]
La planche montre chaque miniature en grand puis en 168×94 px (taille réelle d'une vignette mobile).
Les données de chaque exemple sont dans EXEMPLES ci-dessous : copiez un bloc dans le champ « miniature » d'un episode.json pour le réutiliser.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402
import miniature  # noqa: E402

THEMES = ["papier-vert", "nuit-vert"]
EXEMPLES = {
    "costco-carte-membre": {
        "chiffre": {"gros": "14 %", "texte_haut": "Marge maximale", "icone": "carte"},
        "question": {"texte_haut": "D'où vient l'argent", "icone": "hotdog"},
        "contraste": {"texte_haut": "Le vrai gain", "contraste": [{"valeur": "14 %", "label": "Marge max"}, {"valeur": "66 %", "label": "Bénéfice cartes"}]},
    },
}


def planche(images: list[Path], vignettes: list[Path], out: Path) -> None:
    """3 colonnes (styles) × 2 lignes (thèmes), puis la rangée des vignettes à l'échelle 1:1."""
    cols, w, h = 3, 640, 360
    entrees, filtres, pos = [], [], []
    for i, p in enumerate(images):
        entrees += ["-i", str(p)]
        filtres.append(f"[{i}:v]scale={w}:{h}:flags=lanczos[g{i}]")
        pos.append(f"{(i % cols) * w}_{(i // cols) * h}")
    base = len(images)
    for j, p in enumerate(vignettes):
        entrees += ["-i", str(p)]
        filtres.append(f"[{base + j}:v]scale={miniature.VW}:{miniature.VH}:flags=area[v{j}]")
        pos.append(f"{j * (miniature.VW + 12) + 12}_{2 * h + 14}")
    n = len(images) + len(vignettes)
    ordre = "".join(f"[g{i}]" for i in range(len(images))) + "".join(f"[v{j}]" for j in range(len(vignettes)))
    filtres.append(f"{ordre}xstack=inputs={n}:layout={'|'.join(pos)}:fill=0x202020[o]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *entrees, "-filter_complex", ";".join(filtres), "-map", "[o]", "-frames:v", "1", str(out)], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id", nargs="?", default="costco-carte-membre")
    ap.add_argument("--sortie", default="_test-comparatif/sorties-b/miniatures")
    a = ap.parse_args()
    out = common.ROOT / a.sortie
    out.mkdir(parents=True, exist_ok=True)
    jeux = EXEMPLES.get(a.id, {s: {} for s in miniature.STYLES})
    images, vignettes, bilan = [], [], {}
    for theme in THEMES:
        for style in miniature.STYLES:
            res = miniature.fabriquer(a.id, style, theme, jeux.get(style), alternatives=False)
            e = res["essais"][0]
            dest = out / f"{style}_{theme}.png"
            dest.write_bytes(e["image"].read_bytes())
            images.append(dest)
            vignettes.append(dest)
            bilan[dest.name] = miniature.resume(e)
            print(dest.name, json.dumps(bilan[dest.name], ensure_ascii=False), flush=True)
    planche(images, vignettes, out / "planche.png")
    (out / "controle.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
