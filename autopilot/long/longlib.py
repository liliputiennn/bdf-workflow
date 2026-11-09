"""Briques du format long : validation, aplatissement, calage par chapitre, extraction des Shorts, audio.

Bibliothèque standard seulement (Python 3.11 à 3.14). Voir `autopilot/long/CONCEPTION.md`.
Les numéros de phrase des scènes et des Shorts sont relatifs au chapitre ; `faits.json` et `timings.json` sont en numérotation globale.
"""
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

AUTOPILOT = Path(__file__).resolve().parent.parent
if str(AUTOPILOT) not in sys.path:
    sys.path.insert(0, str(AUTOPILOT))

import make_short  # noqa: E402  (validation des scènes et des Shorts, source unique)
import seo  # noqa: E402  (hashtags et mots-clés des descriptions)

CHAPITRES_MIN, CHAPITRES_MAX = 4, 12
PHRASES_MIN, PHRASES_MAX = 90, 260  # 6 à 12 minutes parlées
PHRASE_MAX_CAR = 160
SHORTS_MAX = 12  # un Short par chapitre au plus
SHORT_PHRASES = (4, 24)
SHORT_DUREE_MAX_S = 58.0
PAUSE_CHAPITRE_S = 2.0
LEAD_S, TAIL_S = 0.15, 0.3  # marge avant / après la parole d'un Short (comme voice.py : lead 0,15 s)


def _vide(x) -> bool:
    return not isinstance(x, str) or not x.strip()


def validate_long(ep: dict, *, minimum: bool = True) -> list[str]:
    """Contrôles de forme d'un `episode-long.json`. `minimum=False` désactive les seuils de taille (démo, tests)."""
    err: list[str] = []
    for k in ("id", "titre", "theme", "chaine", "chapitres"):
        if k not in ep:
            err.append(f"« {k} » manque")
    if err:
        return err
    if ep["theme"] not in make_short.THEMES:
        err.append(f"thème « {ep['theme']} » inconnu ({', '.join(sorted(make_short.THEMES))})")
    if ep.get("theme_accent") is not None and ep["theme_accent"] not in make_short.THEMES:
        err.append(f"thème d'accent « {ep['theme_accent']} » inconnu")
    chaps = ep["chapitres"]
    if not isinstance(chaps, list) or not chaps:
        return err + ["« chapitres » doit être une liste non vide"]
    if minimum and not CHAPITRES_MIN <= len(chaps) <= CHAPITRES_MAX:
        err.append(f"{len(chaps)} chapitres : il en faut de {CHAPITRES_MIN} à {CHAPITRES_MAX}")
    if not minimum and len(chaps) > CHAPITRES_MAX:
        err.append(f"{len(chaps)} chapitres : {CHAPITRES_MAX} au plus")
    total, shorts = 0, 0
    for c, ch in enumerate(chaps, 1):
        nom = f"chapitre {c}"
        if _vide(ch.get("titre")):
            err.append(f"{nom} : titre manquant")
        elif len(ch["titre"]) > 60:
            err.append(f"{nom} : titre trop long ({len(ch['titre'])} caractères, 60 au plus)")
        phrases, scenes = ch.get("phrases"), ch.get("scenes")
        if not isinstance(phrases, list) or not phrases or not isinstance(scenes, list) or not scenes:
            err.append(f"{nom} : « phrases » et « scenes » doivent être des listes non vides")
            continue
        n = len(phrases)
        total += n
        for i, p in enumerate(phrases, 1):
            if _vide(p):
                err.append(f"{nom}, phrase {i} : vide")
                continue
            if len(p) > PHRASE_MAX_CAR:
                err.append(f"{nom}, phrase {i} : trop longue ({len(p)} caractères, {PHRASE_MAX_CAR} au plus)")
            if make_short.FORBIDDEN.search(p):
                err.append(f"{nom}, phrase {i} : formulation interdite (promesse de gain)")
        prev, last_type = 0, ""
        for i, s in enumerate(scenes, 1):
            if s.get("type") not in make_short.SCENE_TYPES:
                err.append(f"{nom}, scène {i} : type « {s.get('type')} » inconnu")
                continue
            ph = s.get("phrase")
            if not isinstance(ph, int) or not 1 <= ph <= n:
                err.append(f"{nom}, scène {i} : « phrase » doit être entre 1 et {n}")
            elif ph <= prev:
                err.append(f"{nom}, scène {i} : les scènes doivent avancer dans le chapitre")
            else:
                prev = ph
            if i == 1 and ph != 1:
                err.append(f"{nom} : la première scène doit commencer à la phrase 1")
            if s["type"] == last_type:
                err.append(f"{nom}, scène {i} : deux « {s['type']} » de suite")
            last_type = s["type"]
            if s["type"] == "objet" and s.get("params", {}).get("icone") not in make_short.ICONES:
                err.append(f"{nom}, scène {i} : icône inconnue ({', '.join(sorted(make_short.ICONES))})")
        sh = ch.get("short")
        if sh is not None:
            shorts += 1
            d, f = sh.get("debut_phrase"), sh.get("fin_phrase")
            if _vide(sh.get("accroche")) or len(sh["accroche"]) > 70:
                err.append(f"{nom} : « accroche » du Short manquante ou > 70 caractères")
            if not (isinstance(d, int) and isinstance(f, int) and 1 <= d <= f <= n):
                err.append(f"{nom} : Short « debut_phrase » / « fin_phrase » doivent être entre 1 et {n}, début ≤ fin")
            elif not SHORT_PHRASES[0] <= f - d + 1 <= SHORT_PHRASES[1]:
                err.append(f"{nom} : un Short compte de {SHORT_PHRASES[0]} à {SHORT_PHRASES[1]} phrases (ici {f - d + 1})")
    if shorts > SHORTS_MAX:
        err.append(f"{shorts} Shorts marqués : {SHORTS_MAX} au plus")
    if minimum and not PHRASES_MIN <= total <= PHRASES_MAX:
        err.append(f"{total} phrases : il en faut de {PHRASES_MIN} à {PHRASES_MAX} pour 6 à 12 minutes")
    return err


# ─────────── aplatissement et calage ───────────

def flatten(ep: dict) -> dict:
    """Phrases bout à bout, scènes en numérotation globale, pauses (secondes avant la phrase globale n)."""
    pause = float(ep.get("pause_chapitre_s", PAUSE_CHAPITRE_S))
    phrases, scenes, chapitres, pauses = [], [], [], {}
    for k, ch in enumerate(ep["chapitres"]):
        first = len(phrases) + 1
        phrases += ch["phrases"]
        for s in ch["scenes"]:
            scenes.append({**s, "phrase": first + s["phrase"] - 1})
        carte = bool(ch.get("carte", k > 0)) and first > 1
        if carte and pause > 0:
            pauses[first] = pause
        chapitres.append({"n": k + 1, "titre": ch["titre"], "first": first, "last": len(phrases), "carte": carte})
    return {"phrases": phrases, "scenes": scenes, "chapitres": chapitres, "pauses": pauses}


def voix_entree(ep: dict) -> dict:
    """Entrée de `voice.py --episode-file` (le cache est indexé par texte de phrase)."""
    fl = flatten(ep)
    return {"phrases": fl["phrases"], "pauses": {str(k): v for k, v in fl["pauses"].items()}}


def sha(obj) -> str:
    return hashlib.sha1(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def chapitres_temps(ep: dict, timings: dict) -> list[dict]:
    """Début / fin de chaque chapitre en secondes (même logique que `src/long/plan.ts`)."""
    fl = flatten(ep)
    lines = timings["lines"]
    if len(lines) != len(fl["phrases"]):
        raise ValueError(f"timings.json : {len(lines)} lignes pour {len(fl['phrases'])} phrases")
    out = []
    for c in fl["chapitres"]:
        debut = lines[c["first"] - 1]["start"]
        fin = lines[c["last"] - 1]["end"]
        carte_de = round(lines[c["first"] - 2]["end"] + 0.1, 3) if c["carte"] else None
        out.append({"n": c["n"], "titre": c["titre"], "phrase_debut": c["first"], "phrase_fin": c["last"],
                    "debut_s": round(debut, 3), "fin_s": round(fin, 3), "carte_de_s": carte_de})
    # frontières de segments : la carte (ou la 1re parole) ouvre le segment, le suivant le ferme
    for k, c in enumerate(out):
        c["borne_s"] = 0.0 if k == 0 else (c["carte_de_s"] if c["carte_de_s"] is not None else c["debut_s"])
        c["borne_fin_s"] = out[k + 1]["carte_de_s"] if k + 1 < len(out) and out[k + 1]["carte_de_s"] is not None else (out[k + 1]["debut_s"] if k + 1 < len(out) else float(timings["total"]))
        c["duree_s"] = round(c["borne_fin_s"] - c["borne_s"], 3)
    return out


# ─────────── extraction d'un Short ───────────

_MOTS_VIDES = set("le la les l un une des du de d et ou où a à au aux en dans sur sous par pour avec sans ce cet cette ces son sa ses leur leurs "
                  "qui que quoi dont est sont être avoir fait comment pourquoi quand combien quel quelle pas plus très il elle ils elles on nous vous je tu "
                  "y se s qu n m t c ne mais donc car si ton ta tes".split())


def titre_miniature(titre: str, n: int = 4) -> str:
    """Texte de miniature tiré du titre d'un chapitre : sans ponctuation ni mots vides, 1 à `n` mots, en capitales."""
    mots = re.findall(r"[A-Za-zÀ-ÿ0-9]+", titre or "")
    utiles = [m for m in mots if m.lower() not in _MOTS_VIDES] or mots
    return " ".join(utiles[:n]).upper()



# Les Shorts d'un même long n'ont pas tous la même miniature : le style tourne d'un chapitre à l'autre (le moteur de miniature se replie
# tout seul sur un autre style quand les données manquent pour celui-ci).
STYLES_MINIATURE_TOURNANTS = ("createur", "chiffre", "telephone", "pile")


def style_miniature_du_short(ep: dict, ch_index: int) -> str:
    base = (ep.get("miniature") or {}).get("style")
    ordre = [base] + [x for x in STYLES_MINIATURE_TOURNANTS if x != base] if base in STYLES_MINIATURE_TOURNANTS else list(STYLES_MINIATURE_TOURNANTS)
    return ordre[ch_index % len(ordre)]


def build_short_episode(ep: dict, ch_index: int, short_id: str) -> tuple[dict, list[str]]:
    """Épisode 9:16 d'un Short marqué : phrases d..f du chapitre, scènes recalées. Renvoie (épisode, notes)."""
    ch = ep["chapitres"][ch_index]
    d, f = ch["short"]["debut_phrase"], ch["short"]["fin_phrase"]
    notes: list[str] = []
    actives = [s for s in ch["scenes"] if s["phrase"] <= d]
    scenes = [{**copy.deepcopy(actives[-1]), "phrase": 1}]
    for s in ch["scenes"]:
        if d < s["phrase"] <= f:
            ns = {**copy.deepcopy(s), "phrase": s["phrase"] - d + 1}
            if ns["type"] == scenes[-1]["type"]:
                notes.append(f"scène « {ns['type']} » à la phrase {ns['phrase']} fusionnée avec la précédente")
                continue
            scenes.append(ns)
    return {
        "id": short_id, "titre": ch["short"]["accroche"], "theme": ep["theme"], "chaine": ep["chaine"],
        **({"langue": ep["langue"]} if ep.get("langue") else {}),
        **({"theme_accent": ep["theme_accent"]} if ep.get("theme_accent") else {}),
        "miniature": {"style": style_miniature_du_short(ep, ch_index), "texte_haut": titre_miniature(ch["titre"]),
                      "icone": (ep.get("miniature") or {}).get("icone", "pieces")},
        "phrases": ch["phrases"][d - 1:f], "scenes": scenes,
    }, notes


def rebase_timings(timings: dict, g0: int, g1: int, lead: float = LEAD_S, tail: float = TAIL_S) -> tuple[dict, float, float]:
    """Timings des phrases globales g0..g1 (1 = première), recalés pour commencer à `lead`. Renvoie (timings, t0, t1)."""
    lines = timings["lines"][g0 - 1:g1]
    t0 = max(0.0, lines[0]["start"] - lead)
    t1 = min(float(timings["total"]), lines[-1]["end"] + tail)
    sh = lambda x: round(x - t0, 3)  # noqa: E731
    new = [{"start": sh(ln["start"]), "end": sh(ln["end"]),
            "words": [{"w": w["w"], "start": sh(w["start"]), "end": sh(w["end"])} for w in ln["words"]]} for ln in lines]
    return {"total": round(t1 - t0, 3), "lines": new}, t0, t1


def faits_du_short(faits: list[dict], g0: int, g1: int) -> list[dict]:
    """Faits dont la phrase (numérotation globale) tombe dans le Short, renumérotés."""
    out = []
    for fa in faits or []:
        p = fa.get("phrase")
        if isinstance(p, int) and g0 <= p <= g1:
            out.append({**fa, "phrase": p - g0 + 1})
    return out


def publication_du_short(pub_long: dict | None, ep: dict, accroche: str, url_long: str | None) -> dict:
    """Publication d'un Short découpé dans un long : titre court (mot-clé en tête), description avec lien vers le long, mots-clés et une dizaine
    de hashtags repris du long ; le publieur remplace le titre du long par son adresse dès qu'elle existe (voir seo.py)."""
    base = pub_long or {}
    tags_long = list(base.get("tags", []))
    question = base.get("question_commentaires", "")
    langue = base.get("langue") or ep.get("langue") or "fr"
    desc = seo.description_short(accroche, ep["titre"], url_long, question, tags_long, seo.hashtags_du_texte(base.get("description", "")), langue=langue)
    return {
        "titre": accroche[:70], "description": desc, "tags": seo.tags_du_short(tags_long, accroche),
        "question_commentaires": question, "langue": langue, "contenu_ia": True,
    }


# ─────────── audio (ffmpeg) ───────────

def _run_ffmpeg(args: list[str]) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg a échoué : " + r.stderr[-400:])
    return r.stderr


def mesure(path: Path, i: float = -14.0, tp: float = -1.5, lra: float = 9.0) -> dict:
    err = _run_ffmpeg(["-i", str(path), "-af", f"loudnorm=I={i}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"])
    return json.loads(re.search(r"\{[\s\S]*\}", err).group())


def filtre_loudnorm(m: dict, i: float, tp: float, lra: float) -> str:
    return (f"loudnorm=I={i}:TP={tp}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def decouper_voix(src: Path, dst: Path, t0: float, t1: float, cible_lufs: float = -16.0) -> None:
    """Extrait [t0, t1] de la voix du long, fondus courts aux bords, normalisé (deux passes) comme `voice.py`."""
    dur = t1 - t0
    bords = f"afade=t=in:d=0.03,afade=t=out:st={max(0.0, dur - 0.08):.3f}:d=0.08"
    tmp = dst.with_suffix(".tmp.wav")
    _run_ffmpeg(["-y", "-v", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", str(src), "-af", bords, "-ar", "48000", "-ac", "1", str(tmp)])
    try:
        m = mesure(tmp, cible_lufs, -1.5, 7.0)
        if m["input_i"] in ("-inf", "inf"):  # silence total : rien à normaliser
            tmp.replace(dst)
            return
        _run_ffmpeg(["-y", "-v", "error", "-i", str(tmp), "-af", filtre_loudnorm(m, cible_lufs, -1.5, 7.0), "-ar", "48000", "-ac", "1", str(dst)])
    finally:
        tmp.unlink(missing_ok=True)


def duree(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())
