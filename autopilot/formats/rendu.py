"""Rendu léger commun aux formats maison (quiz, leçons de langue, sommeil, chansons) : images dessinées avec Pillow, envoyées
à ffmpeg par un tuyau, aucun Remotion ni navigateur. Bibliothèques : Pillow + numpy + ffmpeg (déjà requis par le projet).

- `Encodeur` : écrit une vidéo H.264 image par image ;
- `lire_audio` / `ecrire_wav` : audio mono 48 kHz en numpy ;
- `muxer` : vidéo + audio -> mp4 final normalisé à -14 LUFS (deux passes) ;
- polices : un fichier TTF système si on en trouve un, sinon la police intégrée de Pillow (le rendu ne dépend d'aucune police installée).
"""
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SR = 48000
_POLICES_GRAS = ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
_POLICES = ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf")
_cache_polices: dict = {}


def police(taille: int, gras: bool = True) -> ImageFont.ImageFont:
    cle = (int(taille), gras)
    if cle not in _cache_polices:
        f = None
        for chemin in (_POLICES_GRAS if gras else _POLICES):
            try:
                f = ImageFont.truetype(chemin, int(taille))
                break
            except OSError:
                continue
        _cache_polices[cle] = f or ImageFont.load_default(int(taille))
    return _cache_polices[cle]


def hex_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def degrade(w: int, h: int, haut: str, bas: str) -> Image.Image:
    a, b = np.array(hex_rgb(haut), dtype=np.float32), np.array(hex_rgb(bas), dtype=np.float32)
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    arr = (a * (1 - t) + b * t).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, w, axis=1), "RGB")


def lignes(draw: ImageDraw.ImageDraw, texte: str, fonte, largeur_max: int) -> list[str]:
    """Coupe `texte` en lignes qui tiennent dans `largeur_max` pixels."""
    mots, out, cur = str(texte).split(), [], ""
    for m in mots:
        essai = (cur + " " + m).strip()
        if cur and draw.textlength(essai, font=fonte) > largeur_max:
            out.append(cur)
            cur = m
        else:
            cur = essai
    if cur:
        out.append(cur)
    return out or [""]


def texte_centre(draw: ImageDraw.ImageDraw, cx: float, y: float, texte: str, fonte, couleur, largeur_max: int, interligne: float = 1.18, ombre=None) -> float:
    """Dessine un texte centré sur `cx`, haut à `y`, retourne le bas du bloc."""
    h_ligne = fonte.size * interligne if hasattr(fonte, "size") else 20
    for ln in lignes(draw, texte, fonte, largeur_max):
        w = draw.textlength(ln, font=fonte)
        if ombre:
            draw.text((cx - w / 2 + 3, y + 3), ln, font=fonte, fill=ombre)
        draw.text((cx - w / 2, y), ln, font=fonte, fill=couleur)
        y += h_ligne
    return y


def hauteur_texte(draw: ImageDraw.ImageDraw, texte: str, fonte, largeur_max: int, interligne: float = 1.18) -> float:
    return len(lignes(draw, texte, fonte, largeur_max)) * fonte.size * interligne


def facilite(t: float) -> float:
    """Entrée douce 0 -> 1 (cubique), bornée."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# ---------------------------------------------------------------- vidéo
class Encodeur:
    """Vidéo H.264 sans son, image par image. `with Encodeur(chemin, w, h, fps) as e: e.ecrire(image_pil)`."""

    def __init__(self, chemin: Path, w: int, h: int, fps: int = 30, crf: int = 23):
        self.chemin, self.w, self.h, self.fps = Path(chemin), w, h, fps
        self.n = 0
        self.p = subprocess.Popen(
            ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-g", str(fps * 2), "-movflags", "+faststart", str(self.chemin)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def ecrire(self, img: Image.Image) -> None:
        if img.size != (self.w, self.h):
            img = img.resize((self.w, self.h))
        self.p.stdin.write(img.convert("RGB").tobytes())
        self.n += 1

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        try:
            self.p.stdin.close()
        finally:
            err = self.p.stderr.read().decode("utf-8", "replace")
            self.p.stderr.close()
            self.p.wait()
        if et is None and self.p.returncode:
            raise RuntimeError(f"ffmpeg a échoué : {err[-400:]}")
        return False


# ---------------------------------------------------------------- audio
def lire_audio(chemin: Path, sr: int = SR) -> np.ndarray:
    """Audio quelconque -> mono float32 à `sr`."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(chemin), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def ecrire_wav(chemin: Path, x: np.ndarray, sr: int = SR) -> None:
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def duree(chemin: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(chemin)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def mesure(chemin: Path, cible: float = -14.0, pic: float = -1.5, lra: float = 9.0) -> dict:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(chemin), "-af", f"loudnorm=I={cible}:TP={pic}:LRA={lra}:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"\{[\s\S]*\}", out)
    return json.loads(m.group()) if m else {"input_i": "-70", "input_tp": "-70", "input_lra": "0", "input_thresh": "-80", "target_offset": "0"}


def filtre_loudnorm(m: dict, cible: float = -14.0, pic: float = -1.5, lra: float = 9.0) -> str:
    return (f"loudnorm=I={cible}:TP={pic}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def muxer(video: Path, audio: Path, sortie: Path, cible: float = -14.0, boucle_video: bool = False, duree_s: float | None = None) -> dict:
    """Vidéo (copiée telle quelle, éventuellement bouclée jusqu'à `duree_s`) + audio normalisé à `cible` LUFS -> mp4 final. Retourne la mesure du fichier final."""
    m = mesure(audio, cible)
    entree = ["-stream_loop", "-1"] if boucle_video else []
    cmd = ["ffmpeg", "-y", "-v", "error", *entree, "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-af", filtre_loudnorm(m, cible), "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    cmd += ["-t", f"{duree_s:.3f}"] if duree_s else ["-shortest"]
    cmd += ["-movflags", "+faststart", str(sortie)]
    subprocess.run(cmd, check=True)
    return mesure(sortie, cible)
