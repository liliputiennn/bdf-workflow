"""Vérifie les faits d'un épisode dans leurs sources : les mots-clés `check` doivent apparaître dans la page.

Même principe que `tools/verify_facts.py` (garde-fou contre les chiffres inventés ou mal recopiés, pas une preuve
absolue). Les pages sont mises en cache 7 jours dans `autopilot/state/pages/`. `curl` utilise le magasin de
certificats de Windows (nécessaire derrière l'antivirus qui inspecte le HTTPS).
"""
import hashlib
import html
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.common import STATE  # noqa: E402

CACHE = STATE / "pages"
TTL_S = 7 * 24 * 3600
REFUSES = ("google.", "bing.com", "duckduckgo.", "facebook.", "twitter.com", "x.com", "tiktok.", "instagram.", "youtube.com", "pinterest.")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"(?<=\d)[\s,.  ](?=\d{3}\b)", "", s)  # 12,262 / 12 262 -> 12262
    s = re.sub(r"\s+%", "%", s)  # 14 % -> 14%
    return re.sub(r"\s+", " ", s)


def variantes(terme: str) -> list[str]:
    """Un terme peut s'écrire 1,50 ou 1.50 selon la page."""
    t = norm(terme)
    return list({t, re.sub(r"(?<=\d),(?=\d)", ".", t), re.sub(r"(?<=\d)\.(?=\d)", ",", t)})


def domaine(url: str) -> str:
    h = urlparse(url).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def url_valide(url: str) -> str | None:
    """Renvoie une raison de refus, ou None si l'adresse est acceptable comme source."""
    u = urlparse(url)
    if u.scheme != "https" or not u.netloc:
        return "adresse non https"
    if any(r in u.netloc.lower() for r in REFUSES):
        return "source non sérieuse (moteur de recherche ou réseau social)"
    return None


def page(url: str, reseau: bool = True) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt")
    if f.exists() and time.time() - f.stat().st_mtime < TTL_S:
        return f.read_text(encoding="utf-8")
    if not reseau:
        return ""
    try:
        raw = subprocess.run(
            ["curl", "-sL", "--max-time", "30", "--max-filesize", "6000000", "-A", "Mozilla/5.0 (BureauDesFaits verification de faits)", url],
            capture_output=True, check=True,
        ).stdout.decode("utf-8", "ignore")
    except Exception:
        return ""
    txt = norm(html.unescape(re.sub(r"<(script|style)[\s\S]*?</\1>|<[^>]+>", " ", raw)))
    if txt:
        f.write_text(txt, encoding="utf-8")
    return txt


def verifier(fait: dict, reseau: bool = True) -> list[str]:
    """Renvoie les sources où TOUS les mots-clés `check` sont retrouvés."""
    termes = fait.get("check") or []
    ok = []
    for u in fait.get("sources", []):
        p = page(u, reseau)
        if p and all(any(v in p for v in variantes(t)) for t in termes):
            ok.append(u)
    return ok
