"""Essai de bout en bout d'une chanson PomPikoBoo : paroles d'exemple -> ACE-Step sur Kaggle -> alignement -> clip animé -> contrôle qualité.

Usage : python autopilot/cloud/kaggle/essai_musique.py [--sortie musique-essai] [--fps 24] [--long]
Aucune publication, aucun état modifié dans episodes-b : tout est écrit dans le dossier de sortie (chanson.wav, alignement.json, <id>.mp4, miniature.png, qa.json).
Sert aussi de test de rendu dans GitHub Actions (workflow musique-essai.yml). Code de sortie 0 si le clip est publiable sans alerte, 2 sinon.
"""
import argparse, json, sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE))
from autopilot.formats import musique_enfants as m  # noqa: E402

COUPLETS = {
    "c1": ["Le soleil se lève sur le jardin", "Pompi secoue ses grandes oreilles", "Piko ouvre sa jolie fleur rose", "Les abeilles chantent bonjour"],
    "c2": ["Pompi tourne, Piko saute", "Les papillons font la danse", "On rit, on rit, on chante fort", "Le jardin danse avec nous"],
    "r": ["Tape des mains, tra la la", "Saute avec nous, tra la la", "Tourne, tourne, tra la la", "Pompi et Piko sont contents"],
}


def episode(long: bool) -> dict:
    ordre = ["c1", "r", "c2", "r", "r"] if long else ["c1", "r"]
    return {"id": "musique-essai-long" if long else "musique-essai", "titre": "Chanson du petit jardin pour enfants", "chaine": "PomPikoBoo", "theme": "musique",
            "video": "long" if long else "short", "format_contenu": "musique_enfants", "pour_enfants": True,
            "chanson": {"tempo": 100, "style": "comptine_joyeuse", "ordre": ordre, "strophes": {k: {"lignes": v} for k, v in COUPLETS.items() if k in ordre}},
            "miniature": {"texte_haut": "Chanson", "gros": "Le jardin"}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="musique-essai")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--long", action="store_true")
    a = ap.parse_args()
    ep = episode(a.long)
    pub = {"description": "Une petite chanson sur le jardin. Chanson originale à chanter avec les paroles à l'écran.", "langue": "fr"}
    err, av = m.valider_episode(ep, None, pub, {}, reseau=False)
    if err:
        print("épisode d'essai invalide :", err)
        return 2
    d = Path(a.sortie).resolve()
    d.mkdir(parents=True, exist_ok=True)
    (d / "episode.json").write_text(json.dumps(ep, ensure_ascii=False, indent=1), encoding="utf-8")
    m.generer_audio(ep, d)  # Kaggle (reprise automatique si chanson.wav et alignement.json existent déjà pour ces paroles)
    qa = {"id": ep["id"], "problemes": [], "alertes": []}
    final = m.rendre(ep, d, d, {"nom": "PomPikoBoo"}, qa, fps=a.fps)
    m.miniature(ep, {}).save(d / "miniature.png")
    bornes = m.DUREE_S["long" if a.long else "short"]
    if not bornes[0] <= qa["duree_s"] <= bornes[1]:
        qa["problemes"].append(f"durée {qa['duree_s']} s hors de {bornes}")
    if not m.LUFS - 1.5 <= qa["lufs"] <= m.LUFS + 1.5:
        qa["problemes"].append(f"volume {qa['lufs']} LUFS")
    if qa["pic_dbtp"] > -0.5:
        qa["problemes"].append(f"pic {qa['pic_dbtp']} dBTP")
    qa["publiable"] = not qa["problemes"] and not qa["alertes"] and Path(final).exists()
    (d / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=1))
    return 0 if qa["publiable"] else 2


if __name__ == "__main__":
    sys.exit(main())
