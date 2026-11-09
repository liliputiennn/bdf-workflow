"""Dépose dans le stock (release GitHub privée) les vidéos et miniatures fabriquées, pour l'étape de publication.

Usage : python autopilot/cloud/deposer.py [--dry-run]
Pour chaque épisode `controle` ou `pret` qui a une vidéo finale dans exports-b/<id>/, envoie :
  exports/<id>/<id>.mp4, exports/<id>/qa.json et (si elle existe) exports/<id>/miniature.png.
Pour un long, aussi : miniature_b / miniature_c (variantes à tester dans YouTube Studio, « Test et comparaison »)
et commentaire-epingle.txt (le cadeau, à coller et épingler sous la vidéo).
"""
import argparse, subprocess, sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import common  # noqa: E402
import commentaire  # noqa: E402
import stockage  # noqa: E402


class DepotImpossible(Exception):
    """Un fichier ne peut pas être déposé (trop gros, ou envoi refusé) : on passe à l'épisode suivant."""


def put(fichier: Path, cle: str, dry: bool) -> None:
    print(("[dry-run] " if dry else "") + f"{fichier.name} -> {cle} ({fichier.stat().st_size / 1048576:.1f} Mo)")
    try:
        stockage.verifier_taille(fichier)  # avant tout envoi : une vidéo de plusieurs heures peut dépasser les 2 Go d'une pièce jointe
    except stockage.TropGros as e:
        raise DepotImpossible(str(e)) from None
    if not dry:
        r = subprocess.run([sys.executable, str(ICI / "stockage.py"), "put", str(fichier), cle])
        if r.returncode:
            raise DepotImpossible(f"envoi de {cle} refusé (code {r.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    n = 0
    echecs: list[str] = []
    for ep in common.list_episodes():
        if common.get_status(ep)["etat"] not in ("controle", "pret"):
            continue
        mp4 = common.EXPORTS / ep / f"{ep}.mp4"
        if not mp4.exists():
            continue
        try:
            put(mp4, f"exports/{ep}/{ep}.mp4", a.dry_run)
            for nom, src in (("qa.json", common.EXPORTS / ep / "qa.json"), ("miniature.png", common.ep_dir(ep) / "miniature.png")):
                if src.exists():
                    put(src, f"exports/{ep}/{nom}", a.dry_run)
            for var in ("miniature_b", "miniature_c"):
                for ext in ("png", "jpg"):
                    f = common.ep_dir(ep) / f"{var}.{ext}"
                    if f.exists():
                        put(f, f"exports/{ep}/{f.name}", a.dry_run)
            txt = commentaire.texte(common.read_json(common.ep_dir(ep) / "publication.json", {}) or {})
            if txt:
                cible = common.EXPORTS / ep / "commentaire-epingle.txt"
                cible.write_text(txt, encoding="utf-8")
                put(cible, f"exports/{ep}/commentaire-epingle.txt", a.dry_run)
        except DepotImpossible as e:
            echecs.append(ep)
            print(f"::error::[{ep}] non déposé dans le stock : {e}")
            continue
        n += 1
    print(f"{n} épisode(s) déposé(s)")
    if echecs:  # les autres épisodes ont été déposés ; ceux-ci restent « controle » et seront retentés au prochain passage
        print(f"{len(echecs)} épisode(s) NON déposé(s) : {', '.join(echecs)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
