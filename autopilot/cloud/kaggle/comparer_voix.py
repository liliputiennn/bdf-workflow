"""Compare des réglages de voix sur les mêmes phrases, sur le GPU gratuit de Kaggle, pour choisir la plus naturelle.

Usage : python autopilot/cloud/kaggle/comparer_voix.py [--episode appli-gratuite-argent] [--phrases 6]
Fabrique 4 versions dans voix-comparaison/ à la racine du projet (A.wav à D.wav) et écrit LISEZMOI.txt :
  A  modèle 0.6B, vitesse d'origine          (la voix actuelle)
  B  modèle 0.6B, 10 % plus rapide            (réglage par défaut maintenant)
  C  modèle 1.7B, 10 % plus rapide            (modèle plus gros : voix plus naturelle ?)
  D  modèle 1.7B, 20 % plus rapide
Chaque version prend environ 7 minutes sur Kaggle (la 1.7B télécharge son modèle) ; elles tournent l'une après l'autre.
"""
import argparse, json, os, shutil, subprocess, sys
os.environ.setdefault("BDF_KERNEL_SLUG", "bdf-voix-test")
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[2]
VARIANTES = {
    "A": ("", 1.00, "0.6B, vitesse d'origine (voix actuelle)"),
    "B": ("", 1.10, "0.6B, 10 % plus rapide"),
    "C": ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", 1.10, "1.7B, 10 % plus rapide"),
    "D": ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", 1.20, "1.7B, 20 % plus rapide"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", default="appli-gratuite-argent")
    ap.add_argument("--phrases", type=int, default=6)
    a = ap.parse_args()
    ep = json.loads((RACINE / "episodes-b" / a.episode / "episode.json").read_text(encoding="utf-8"))
    phrases = ep["phrases"][: a.phrases]
    sortie = RACINE / "voix-comparaison"
    sortie.mkdir(exist_ok=True)
    notes = ["Comparaison de voix (mêmes phrases) :", *[f"  {k} : {v[2]}" for k, v in VARIANTES.items()], "", "Phrases lues :", *[f"  - {p}" for p in phrases]]
    for cle, (modele, vitesse, _) in VARIANTES.items():
        dossier = RACINE / "episodes-b" / f"_voix-test-{cle}"  # dossier « _ » : ignoré par le workflow
        shutil.rmtree(dossier, ignore_errors=True)
        dossier.mkdir(parents=True)
        (dossier / "episode.json").write_text(json.dumps({"id": f"voix-test-{cle}", "phrases": phrases}, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(ICI / "lancer_voix.py"), str(dossier), "--essais", "2", "--vitesse", str(vitesse)] + (["--modele-hf", modele] if modele else [])
        print(f"=== version {cle} ===", flush=True)
        rc = subprocess.run(cmd).returncode
        wav = dossier / "voice.wav"
        if rc == 0 and wav.exists():
            shutil.copy(wav, sortie / f"{cle}.wav")
        else:
            notes.append(f"version {cle} : ÉCHEC (code {rc})")
        shutil.rmtree(dossier, ignore_errors=True)
    (sortie / "LISEZMOI.txt").write_text("\n".join(notes), encoding="utf-8")
    print("Terminé :", sortie)
    return 0


if __name__ == "__main__":
    sys.exit(main())
