"""Miniature des formats maison : le module de format du profil dessine l'image 1280x720 (`miniature(ep, profil)`), enregistrée en miniature.png.

Usage :  python autopilot/formats/miniature_formats.py <id>      (remplace miniature.py via `briques.miniature` du profil)
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from autopilot import chaines, common  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    ep_id = argv[0]
    profil = chaines.profil(common.chaine_de(ep_id)) or chaines.defaut_fr()
    module = chaines.charger_format(profil)
    ep = common.read_json(common.ep_dir(ep_id) / "episode.json", None)
    if module is None or not hasattr(module, "miniature") or not isinstance(ep, dict):
        print("module de format, crochet miniature() ou episode.json introuvable")
        return 2
    img = module.miniature(ep, profil).convert("RGB")
    if img.size != (1280, 720):
        img = img.resize((1280, 720))
    tmp = common.ep_dir(ep_id) / "miniature.png.tmp"
    img.save(tmp, "PNG", optimize=True)
    tmp.replace(common.ep_dir(ep_id) / "miniature.png")
    print("miniature.png écrite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
