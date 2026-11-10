"""Personnages de PomPikoBoo dessinés par code (style « 3D » doux : formes rondes, reflets, joues roses) : un petit éléphant rose et un cactus vert à fleur rose.

Aucune image tierce : tout est dessiné ici (PIL, suréchantillonné x2). Les sprites sont mis en cache par (bouche, yeux, bras) ;
l'animation (rebond, écrasement/étirement, balancement) est appliquée ensuite par image, à bas coût.
Les noms des personnages sont ceux de assets-persos/pompikoboo/persos.json (à confirmer par l'utilisateur).
"""
import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

L, H, SS = 560, 700, 2  # taille d'un sprite (px) et suréchantillonnage
COULEURS = {
    "elephant": {"corps": (255, 150, 190), "clair": (255, 205, 225), "ombre": (225, 105, 155), "oreille": (255, 120, 170)},
    "cactus": {"corps": (95, 205, 90), "clair": (165, 235, 140), "ombre": (55, 160, 70), "fleur": (255, 110, 175)},
}
ENCRE = (50, 35, 70)
BOUCHE_INT = (150, 40, 70)
LANGUE = (255, 130, 150)


def _s(v):
    return int(round(v * SS))


def _calque():
    return Image.new("RGBA", (L * SS, H * SS), (0, 0, 0, 0))


def _teinte(base, forme, col, flou, alpha=255):
    """Teinte `base` avec la couleur col dans la forme (fonction de dessin sur un masque L), bords flous : pas d'assombrissement des bords."""
    m = Image.new("L", base.size, 0)
    forme(ImageDraw.Draw(m), alpha)
    m = m.filter(ImageFilter.GaussianBlur(_s(flou)))
    return Image.composite(Image.new("RGBA", base.size, col + (255,)), base, m)


def _volume(base, boite, col, clair, ombre, r):
    """Ombre en bas à droite, reflet en haut à gauche, sur une forme déjà remplie."""
    x0, y0, x1, y1 = boite
    w, h = x1 - x0, y1 - y0
    base = _teinte(base, lambda d, a: d.ellipse((_s(x0 + w * 0.15), _s(y0 + h * 0.55), _s(x1 + w * 0.2), _s(y1 + h * 0.3)), fill=a), ombre, r * 0.3)
    base = _teinte(base, lambda d, a: d.ellipse((_s(x0 + w * 0.12), _s(y0 + h * 0.08), _s(x0 + w * 0.5), _s(y0 + h * 0.4)), fill=a), clair, r * 0.16)
    return base


def _ellipse(img, cx, cy, rx, ry, col, relief=True, clair=None, ombre=None):
    """Ellipse pleine avec ombrage doux pour un rendu volumétrique."""
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).ellipse((_s(cx - rx), _s(cy - ry), _s(cx + rx), _s(cy + ry)), fill=255)
    base = Image.new("RGBA", img.size, col + (255,))
    if relief:
        o = ombre or tuple(int(c * 0.86) for c in col)
        c2 = clair or tuple(min(255, int(c * 1.12 + 25)) for c in col)
        base = _volume(base, (cx - rx, cy - ry, cx + rx, cy + ry), col, c2, o, min(rx, ry))
    base.putalpha(m.filter(ImageFilter.GaussianBlur(0.6)) if False else m)
    img.alpha_composite(base)


def _capsule(img, x0, y0, x1, y1, col, clair, ombre):
    """Rectangle à bouts ronds (corps du cactus, bras)."""
    r = min(x1 - x0, y1 - y0) / 2
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((_s(x0), _s(y0), _s(x1), _s(y1)), radius=_s(r), fill=255)
    base = Image.new("RGBA", img.size, col + (255,))
    base = _teinte(base, lambda d, a: d.rounded_rectangle((_s(x0 + (x1 - x0) * 0.58), _s(y0 - 30), _s(x1 + 60), _s(y1 + 30)), radius=_s(r), fill=a), ombre, r * 0.45)
    base = _teinte(base, lambda d, a: d.rounded_rectangle((_s(x0 + (x1 - x0) * 0.12), _s(y0 + (y1 - y0) * 0.06), _s(x0 + (x1 - x0) * 0.36), _s(y1 - (y1 - y0) * 0.1)), radius=_s(r * 0.4), fill=a), clair, r * 0.28)
    base.putalpha(m)
    img.alpha_composite(base)


def _yeux(img, cx, cy, ecart, r, ferme):
    d = ImageDraw.Draw(img)
    for sx in (-1, 1):
        x = cx + sx * ecart
        if ferme:  # paupière fermée : petit arc souriant
            d.arc((_s(x - r * 0.9), _s(cy - r * 0.5), _s(x + r * 0.9), _s(cy + r * 0.9)), 200, 340, fill=ENCRE + (255,), width=_s(6))
            continue
        d.ellipse((_s(x - r), _s(cy - r * 1.15), _s(x + r), _s(cy + r * 1.15)), fill=(255, 255, 255, 255))
        d.ellipse((_s(x - r * 0.62), _s(cy - r * 0.8), _s(x + r * 0.62), _s(cy + r * 0.95)), fill=ENCRE + (255,))
        d.ellipse((_s(x - r * 0.38), _s(cy - r * 0.62), _s(x + r * 0.02), _s(cy - r * 0.2)), fill=(255, 255, 255, 255))  # reflet
        d.ellipse((_s(x + r * 0.05), _s(cy + r * 0.1), _s(x + r * 0.3), _s(cy + r * 0.35)), fill=(255, 255, 255, 200))


def _bouche(img, cx, cy, ouv):
    """ouv : 0 fermée (sourire) .. 3 grande ouverte."""
    d = ImageDraw.Draw(img)
    if ouv == 0:
        d.arc((_s(cx - 34), _s(cy - 24), _s(cx + 34), _s(cy + 22)), 15, 165, fill=ENCRE + (255,), width=_s(7))
        return
    w, h = [(26, 16), (32, 30), (36, 46)][ouv - 1]
    d.ellipse((_s(cx - w), _s(cy - h * 0.35), _s(cx + w), _s(cy + h)), fill=BOUCHE_INT + (255,))
    if ouv >= 2:
        d.ellipse((_s(cx - w * 0.6), _s(cy + h * 0.45), _s(cx + w * 0.6), _s(cy + h * 1.02)), fill=LANGUE + (255,))


def _joues(img, cx, cy, ecart):
    for sx in (-1, 1):
        x = cx + sx * ecart
        img.paste(_teinte(img.copy(), lambda d, al, x=x: d.ellipse((_s(x - 30), _s(cy - 18), _s(x + 30), _s(cy + 18)), fill=200), (255, 120, 150), 4), (0, 0), img.getchannel("A"))


def _bras(img, cx, cy, longueur, angle_deg, col, clair, ombre, sens):
    a = math.radians(angle_deg)
    for k in range(5):
        f = k / 4
        _ellipse(img, cx + sens * math.cos(a) * longueur * f, cy - math.sin(a) * longueur * f, 27, 27, col, clair=clair, ombre=ombre)
    _ellipse(img, cx + sens * math.cos(a) * longueur, cy - math.sin(a) * longueur, 31, 30, col, clair=clair, ombre=ombre)


def _elephant(bouche: int, ferme: bool, bras: float) -> Image.Image:
    c = COULEURS["elephant"]
    img = _calque()
    ang = 25 + 55 * (bras + 1) / 2  # -1 bras bas ; +1 bras haut
    # jambes
    for sx in (-1, 1):
        _ellipse(img, 280 + sx * 80, 640, 62, 42, c["ombre"], clair=c["corps"])
    # corps
    _ellipse(img, 280, 470, 150, 170, c["corps"], clair=c["clair"], ombre=c["ombre"])
    _ellipse(img, 280, 510, 95, 105, c["clair"], relief=False)  # ventre clair
    for sens in (-1, 1):
        _bras(img, 280 + sens * 120, 470, 70, ang if sens == 1 else 25 + 55 * (1 - bras) / 2, c["corps"], c["clair"], c["ombre"], sens)
    # oreilles
    for sx in (-1, 1):
        _ellipse(img, 280 + sx * 175, 240, 105, 120, c["oreille"], clair=c["clair"], ombre=c["ombre"])
        _ellipse(img, 280 + sx * 172, 245, 68, 82, c["clair"], relief=False)
    # tête
    _ellipse(img, 280, 250, 150, 140, c["corps"], clair=c["clair"], ombre=c["ombre"])
    # trompe courte et ronde, avec deux narines
    for (x, y, rr) in ((280, 292, 40), (281, 322, 38), (286, 346, 36)):
        _ellipse(img, x, y, rr, rr, c["corps"], clair=c["clair"], ombre=c["ombre"])
    d = ImageDraw.Draw(img)
    for sx in (-1, 1):
        d.ellipse((_s(286 + sx * 13 - 6), _s(352 - 5), _s(286 + sx * 13 + 6), _s(352 + 6)), fill=c["ombre"] + (255,))
    # visage
    _yeux(img, 280, 215, 52, 27, ferme)
    _joues(img, 280, 300, 112)
    return img


def _cactus(bouche: int, ferme: bool, bras: float) -> Image.Image:
    c = COULEURS["cactus"]
    img = _calque()
    ang = 30 + 60 * (bras + 1) / 2
    for sx in (-1, 1):
        _ellipse(img, 280 + sx * 62, 650, 58, 38, c["ombre"], clair=c["corps"])
    # bras latéraux
    for sens in (-1, 1):
        a = ang if sens == 1 else 30 + 60 * (1 - bras) / 2
        x0 = 280 + sens * 105
        _capsule(img, min(x0, x0 + sens * 90), 430, max(x0, x0 + sens * 90), 485, c["corps"], c["clair"], c["ombre"])
        _capsule(img, x0 + sens * 90 - 26, 430 - 36 * (a / 90) - 70, x0 + sens * 90 + 26, 485, c["corps"], c["clair"], c["ombre"])
    # corps
    _capsule(img, 160, 130, 400, 665, c["corps"], c["clair"], c["ombre"])
    d = ImageDraw.Draw(img)
    for dx in (-52, 52):  # côtes
        d.line((_s(280 + dx), _s(210), _s(280 + dx), _s(600)), fill=c["ombre"] + (120,), width=_s(5))
    for (x, y) in ((205, 330), (355, 360), (215, 520), (350, 500), (300, 600)):  # petites épines claires
        d.ellipse((_s(x - 4), _s(y - 4), _s(x + 4), _s(y + 4)), fill=(255, 250, 215, 255))
    # fleur rose sur la tête
    fx, fy = 300, 112
    for k in range(6):
        a = k * math.pi / 3 + 0.3
        _ellipse(img, fx + math.cos(a) * 38, fy + math.sin(a) * 30, 34, 30, c["fleur"], clair=(255, 175, 215), ombre=(215, 70, 135))
    _ellipse(img, fx, fy, 24, 22, (255, 215, 80), clair=(255, 240, 150), ombre=(235, 175, 40))
    _yeux(img, 280, 270, 52, 27, ferme)
    _joues(img, 280, 340, 92)
    return img


@lru_cache(maxsize=512)
def sprite(nom: str, bouche: int = 0, ferme: bool = False, bras: int = 0) -> Image.Image:
    """Sprite RGBA L x H. bras : -2..2 (hauteur des bras)."""
    b = max(-1.0, min(1.0, bras / 2))
    img = (_elephant if nom == "elephant" else _cactus)(bouche, ferme, b)
    # bouche dessinée après coup (au centre du visage, sous les yeux)
    _bouche(img, 280, 408 if nom == "cactus" else 378, bouche)
    return img.resize((L, H), Image.LANCZOS)


def animer(nom: str, t: float, beat: float, ouv: float, chante: bool, phase: float = 0.0) -> tuple[Image.Image, float, float]:
    """Sprite pour l'instant t : (image déjà écrasée/étirée/tournée, décalage vertical, échelle).
    ouv : ouverture de bouche 0..1 (voix) ; chante : le personnage chante (sinon il danse)."""
    ph = (t / beat + phase) % 1.0
    rebond = abs(math.sin(math.pi * ph))  # 0 au sol, 1 en haut
    squash = 1 + 0.07 * math.cos(2 * math.pi * ph) * (1.0 if chante else 0.8)  # écrasé au sol, étiré en l'air
    bouche = 0 if ouv < 0.15 else 1 if ouv < 0.45 else 2 if ouv < 0.75 else 3
    bouche = bouche if chante else 0
    bl = int(t * 1000 + sum(map(ord, nom)) * 37 % 1700) % 3200  # clignement environ toutes les 3 s
    ferme = bl < 130
    bras = 2 if (int(t / beat + phase) % 2) else -1
    img = sprite(nom, bouche, ferme, bras if chante else 2 * (1 if int(t / beat * 2) % 2 else -1))
    w, h = img.size
    img = img.resize((int(w / squash ** 0.5), int(h * squash)), Image.BICUBIC)
    rot = 4.5 * math.sin(math.pi * (t / beat + phase))
    img = img.rotate(rot, resample=Image.BICUBIC, expand=True, center=(img.width / 2, img.height))
    return img, -rebond * 70, squash
