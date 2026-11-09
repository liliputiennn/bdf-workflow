"""Moteur de traduction GRATUIT de repli (quand Claude est bloqué) : MarianMT, modèles OPUS-MT de Helsinki-NLP, sur CPU.

LICENCES (vérifiées sur les fiches Hugging Face le 2026-11-09) :
  - Helsinki-NLP/opus-mt-fr-en : Apache-2.0, 75 M de paramètres, ≈ 300 Mo.  OK pour une chaîne monétisée.
  - INTERDITS pour une chaîne monétisée : NLLB-200 (CC-BY-NC), XTTS-v2 (licence Coqui non commerciale), Qwen2.5-3B (licence de recherche),
    tout modèle « non commercial ». Le modèle NLLB qui traîne dans le cache Hugging Face de l'utilisateur (C:\\VoiceStudio\\models) n'est JAMAIS utilisé ici.
  - Autres paires (opus-mt-fr-es, opus-mt-fr-de…) : relire la licence de la fiche AVANT `installer`, puis l'ajouter à LICENCES_VERIFIEES.

Ce module a deux faces :
  - bibliothèque (Python du PATH, bibliothèque standard seulement) : `MoteurMarian` lance le Python du venv de la voix en sous-processus
    (c'est lui qui a transformers, torch et sentencepiece) et échange du JSON ;
  - ligne de commande (dans le venv) :  python moteurs.py installer fr-en       # télécharge le modèle (explicite, jamais automatique)
                                        python moteurs.py traduire fr-en entree.json sortie.json     # liste de textes -> liste de textes
                                        python moteurs.py etat

Le modèle est rangé dans `autopilot/state/modeles/<nom>/` (ignoré par git comme le reste de state/). Aucun jeton, aucun compte.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTOPILOT = HERE.parent
VENV_PY = os.environ.get("BDF_VENV_PY", r"C:\VoiceStudio\tts-direct\venv\Scripts\python.exe")

# paire "fr-en" -> (identifiant Hugging Face, licence relevée, date de vérification)
MODELES = {
    "fr-en": ("Helsinki-NLP/opus-mt-fr-en", "apache-2.0", "2026-11-09"),
    "fr-es": ("Helsinki-NLP/opus-mt-fr-es", None, None),
    "fr-de": ("Helsinki-NLP/opus-mt-fr-de", None, None),
}
LICENCES_OK = {"apache-2.0", "mit", "cc-by-4.0"}
LOT = 16


def dossier_modeles() -> Path:
    racine = Path(os.environ["BDF_ROOT"]) if os.environ.get("BDF_ROOT") else AUTOPILOT.parent
    return racine / "autopilot" / "state" / "modeles"


def dossier_modele(paire: str) -> Path:
    return dossier_modeles() / ("opus-mt-" + paire)


def licence_autorisee(paire: str) -> tuple[bool, str]:
    if paire not in MODELES:
        return False, f"paire « {paire} » inconnue (connues : {', '.join(MODELES)})"
    hf, lic, _ = MODELES[paire]
    if lic not in LICENCES_OK:
        return False, f"{hf} : licence non vérifiée — relis la fiche Hugging Face et ajoute-la à MODELES avant d'installer"
    return True, f"{hf} : {lic}"


def installe(paire: str) -> bool:
    d = dossier_modele(paire)
    return d.is_dir() and (any(d.glob("*.safetensors")) or any(d.glob("pytorch_model*.bin")))


def disponible(paire: str) -> tuple[bool, str]:
    """Le repli peut-il tourner pour cette paire ? (licence vérifiée, modèle installé, Python du venv présent)."""
    ok, msg = licence_autorisee(paire)
    if not ok:
        return False, msg
    if not installe(paire):
        return False, f"modèle {MODELES[paire][0]} non installé : python autopilot/traduction/moteurs.py installer {paire} (≈ 300 Mo, une fois)"
    if not Path(VENV_PY).exists():
        return False, f"Python du venv introuvable ({VENV_PY})"
    return True, msg


class MoteurMarian:
    """Traducteur appelable : `moteur(["phrase", ...]) -> ["sentence", ...]`, via un sous-processus du venv (CPU)."""
    nom = "marian"

    def __init__(self, de: str, vers: str, timeout_s: int = 900):
        self.paire, self.timeout_s = f"{de}-{vers}", timeout_s

    def __call__(self, textes: list[str]) -> list[str]:
        ok, msg = disponible(self.paire)
        if not ok:
            raise RuntimeError(msg)
        with tempfile.TemporaryDirectory(prefix="bdf-trad-") as tmp:
            e, s = Path(tmp) / "entree.json", Path(tmp) / "sortie.json"
            e.write_text(json.dumps(textes, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([VENV_PY, str(HERE / "moteurs.py"), "traduire", self.paire, str(e), str(s)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=self.timeout_s,
                               env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"})
            if r.returncode or not s.exists():
                raise RuntimeError("traduction de repli échouée : " + (r.stderr or r.stdout)[-300:])
            sortie = json.loads(s.read_text(encoding="utf-8"))
        if not isinstance(sortie, list) or len(sortie) != len(textes):
            raise RuntimeError("traduction de repli : nombre de textes inattendu")
        return [str(x) for x in sortie]


# ---------------------------------------------------------------- ligne de commande (dans le venv)
def _installer(paire: str) -> int:
    ok, msg = licence_autorisee(paire)
    print(msg)
    if not ok:
        return 2
    from huggingface_hub import snapshot_download  # dans le venv
    d = dossier_modele(paire)
    d.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=MODELES[paire][0], local_dir=str(d), allow_patterns=["*.json", "*.safetensors", "*.spm", "*.model", "vocab*", "*.txt", "source.spm", "target.spm"])
    print("installé dans", d)
    return 0


def _traduire(paire: str, entree: str, sortie: str) -> int:
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    d = str(dossier_modele(paire))
    tok = MarianTokenizer.from_pretrained(d, local_files_only=True)
    mod = MarianMTModel.from_pretrained(d, local_files_only=True).eval()
    textes = json.loads(Path(entree).read_text(encoding="utf-8"))
    out: list[str] = []
    with torch.no_grad():
        for i in range(0, len(textes), LOT):
            lot = textes[i:i + LOT]
            enc = tok(lot, return_tensors="pt", padding=True, truncation=True, max_length=256)
            gen = mod.generate(**enc, num_beams=4, max_new_tokens=256)
            out += tok.batch_decode(gen, skip_special_tokens=True)
    Path(sortie).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "etat"
    if cmd == "installer" and len(argv) > 1:
        return _installer(argv[1])
    if cmd == "traduire" and len(argv) > 3:
        return _traduire(argv[1], argv[2], argv[3])
    if cmd == "etat":
        for paire in MODELES:
            ok, msg = disponible(paire)
            print(f"{paire}: {'PRÊT' if ok else 'indisponible'} — {msg}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
