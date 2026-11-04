"""Musique de fond automatique : mixée sous la voix avec ducking, jamais bloquante.

Les pistes (libres de droits, choisies par toi) sont dans `autopilot/musique/` (variable BDF_MUSIQUE pour un autre dossier).
Elles ne sont JAMAIS dans le dépôt (public) : en cloud elles viennent d'un jeu de données Kaggle privé.

Principe : un « lit » musical (une ou plusieurs pistes enchaînées en fondu, calées à la durée de la vidéo, volume fixe
bien sous la voix) est mixé avec la voix ; un compresseur à chaînage latéral (sidechain) baisse encore la musique
tant que la voix parle et la laisse remonter dans les pauses. La voix n'est pas touchée.
Sans piste ou avec `"musique": "aucune"` dans l'épisode, rien n'est mixé et la fonction renvoie None.

Usage : python autopilot/musique.py <voix.wav> <sortie.wav> [--id ID] [--piste NOM]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent / "musique"
EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
LUFS_LIT = -27.0  # niveau du lit seul (la voix est à -16 LUFS) : audible dans les pauses
DUCK = "sidechaincompress=threshold=0.06:ratio=2:attack=30:release=700:makeup=1"  # musique ~20 dB sous la voix pendant la parole, ~11 dB dans les pauses
FONDU_ENTREE_S, FONDU_SORTIE_S = 1.5, 4.0
RACCORD_S = 4.0  # fondu enchaîné entre deux pistes
DUREE_PISTE_MIN_S = 20.0


def dossier() -> Path:
    return Path(os.environ["BDF_MUSIQUE"]) if os.environ.get("BDF_MUSIQUE") else DOSSIER


def pistes(d: Path | None = None) -> list[Path]:
    d = d or dossier()
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS and not p.name.startswith("."))


def _ffmpeg(args: list[str]) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg a échoué : " + r.stderr[-400:])
    return r.stderr


def duree(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def volume_integre(p: Path) -> float:
    """Volume intégré (LUFS) d'un fichier, mesuré sans le modifier."""
    err = _ffmpeg(["-i", str(p), "-af", "loudnorm=I=-24:TP=-2:LRA=11:print_format=json", "-f", "null", "-"])
    return float(json.loads(re.search(r"\{[\s\S]*\}", err).group())["input_i"])


def _graine(ep_id: str, sel: str = "") -> int:
    return int(hashlib.sha256(f"{ep_id}|{sel}".encode()).hexdigest()[:8], 16)


def choisir(ep_id: str, dispo: list[Path], longueur: float, voulu: str | None = None, durees: dict | None = None) -> list[Path]:
    """Suite de pistes qui couvre `longueur` secondes : stable pour un épisode, variée d'un épisode à l'autre.

    `voulu` = nom (ou début de nom) d'une piste imposée, qui ouvre alors la suite.
    """
    if not dispo:
        return []
    durees = durees or {p: duree(p) for p in dispo}
    ordre = sorted(dispo, key=lambda p: _graine(ep_id, p.name))  # ordre propre à l'épisode
    if voulu:
        pref = [p for p in dispo if p.name.lower().startswith(voulu.lower())]
        if pref:
            ordre = pref[:1] + [p for p in ordre if p not in pref[:1]]
    suite, couvert, i = [], 0.0, 0
    while couvert < longueur + FONDU_SORTIE_S and len(suite) < 40:
        p = ordre[i % len(ordre)]
        suite.append(p)
        couvert += max(durees[p], 1.0) - (RACCORD_S if suite[:-1] else 0.0)
        i += 1
    return suite


def _construire_lit(suite: list[Path], longueur: float, decalage: float, dest: Path) -> None:
    """Enchaîne les pistes en fondu, applique un gain fixe, coupe à `longueur` avec fondus d'entrée et de sortie."""
    args, filtres = ["-y", "-v", "error"], []
    for n, p in enumerate(suite):
        if n == 0 and decalage > 0:
            args += ["-ss", f"{decalage:.2f}"]
        args += ["-i", str(p)]
        gain = LUFS_LIT - volume_integre(p)
        filtres.append(f"[{n}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume={gain:.2f}dB[p{n}]")
    cur = "p0"
    for n in range(1, len(suite)):
        filtres.append(f"[{cur}][p{n}]acrossfade=d={RACCORD_S}:c1=tri:c2=tri[x{n}]")
        cur = f"x{n}"
    sortie = max(longueur - FONDU_SORTIE_S, 0.0)
    filtres.append(f"[{cur}]atrim=0:{longueur:.3f},afade=t=in:d={FONDU_ENTREE_S},afade=t=out:st={sortie:.3f}:d={FONDU_SORTIE_S}[lit]")
    _ffmpeg([*args, "-filter_complex", ";".join(filtres), "-map", "[lit]", "-c:a", "pcm_s16le", str(dest)])


def mixer(voix: Path, dest: Path, ep_id: str, *, longueur: float | None = None, voulu: str | None = None, d: Path | None = None) -> dict | None:
    """Écrit `dest` (wav stéréo 48 kHz) = voix + musique ducking. Renvoie un compte rendu, ou None s'il n'y a rien à mixer.

    `longueur` : durée totale voulue (la voix est complétée par du silence si elle est plus courte, comme le fait make_long).
    """
    if voulu and voulu.strip().lower() in ("aucune", "non", "none"):
        return None
    dispo = [p for p in pistes(d)]
    durees = {p: duree(p) for p in dispo}
    dispo = [p for p in dispo if durees[p] >= DUREE_PISTE_MIN_S]
    if not dispo:
        return None
    total = longueur or duree(voix)
    suite = choisir(ep_id, dispo, total, voulu, durees)
    # un Short n'est qu'un extrait : on démarre la piste à un endroit propre à l'épisode pour varier les débuts
    decalage = 0.0
    if len(suite) == 1 and durees[suite[0]] > total + 30:
        decalage = float(_graine(ep_id, "debut") % int(durees[suite[0]] - total - 20))
    with tempfile.TemporaryDirectory() as tmp:
        lit = Path(tmp) / "lit.wav"
        _construire_lit(suite, total, decalage, lit)
        fc = (f"[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,apad=whole_dur={total:.3f},asplit=2[v1][v2];"
              f"[1:a][v1]{DUCK}[md];[v2][md]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[o]")
        _ffmpeg(["-y", "-v", "error", "-i", str(voix), "-i", str(lit), "-filter_complex", fc, "-map", "[o]", "-t", f"{total:.3f}",
                 "-c:a", "pcm_s16le", str(dest)])
    return {"pistes": [p.name for p in suite], "decalage_s": decalage, "lit_lufs": LUFS_LIT}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("voix", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--id", default="essai")
    ap.add_argument("--piste")
    a = ap.parse_args(argv)
    r = mixer(a.voix, a.sortie, a.id, voulu=a.piste)
    print(json.dumps(r, ensure_ascii=False) if r else "aucune piste : rien mixé")
    return 0


if __name__ == "__main__":
    sys.exit(main())
