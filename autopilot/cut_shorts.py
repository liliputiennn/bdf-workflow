"""Découpe un long en Shorts 9:16 : jusqu'à 12 épisodes (un par chapitre marqué) `episodes-b/<id>-sN/` prêts pour `make_short.py`.

Usage :  python autopilot/cut_shorts.py <id> [--max 3] [--force]
Entrée   episodes-b/<id>/episode-long.json (segments marqués `short`), timings.json, voice.wav  (+ faits.json, publication.json s'ils existent)
Sortie   episodes-b/<id>-sN/ : episode.json, timings.json, voice.wav (extrait + normalisé), faits.json, publication.json,
         voice_report.json (vide), origine.json, status.json à « ecrit ». Rapport : episodes-b/<id>/cut_report.json
Les Shorts sont ensuite rendus par :  python autopilot/make_short.py <id>-sN --voix-prete   (voice.py n'est jamais appelé)
Code retour 0 = au moins un Short créé ; 2 = rien de créé.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "long"))

import common  # noqa: E402
import longlib as L  # noqa: E402
import make_short  # noqa: E402

EN_COURS = {"voix", "rendu", "controle", "pret", "programme", "publie"}


def cut(long_id: str, *, maximum: int = L.SHORTS_MAX, force: bool = False) -> dict:
    """Crée les Shorts d'un long. Renvoie le rapport (aussi écrit dans cut_report.json)."""
    base = common.EPISODES
    src = base / long_id
    ep = common.read_json(src / "episode-long.json")
    timings = common.read_json(src / "timings.json")
    rapport = {"long": long_id, "shorts": [], "ignores": []}
    if ep is None or timings is None or not (src / "voice.wav").exists():
        rapport["erreur"] = "episode-long.json, timings.json et voice.wav sont nécessaires"
        return rapport
    problemes = L.validate_long(ep, minimum=False)
    if problemes:
        rapport["erreur"] = "épisode long invalide : " + " ; ".join(problemes[:5])
        return rapport
    plan = L.flatten(ep)
    faits = common.read_json(src / "faits.json", [])
    pub_long = common.read_json(src / "publication.json")
    url_long = (common.read_json(src / "status.json", {}) or {}).get("youtube", {}).get("url")

    marques = [(k, ch) for k, ch in enumerate(ep["chapitres"]) if ch.get("short")]
    for n, (k, ch) in enumerate(marques[:maximum], 1):
        sid = f"{long_id}-s{n}"
        sdir = base / sid
        d, f = ch["short"]["debut_phrase"], ch["short"]["fin_phrase"]
        first = plan["chapitres"][k]["first"]
        g0, g1 = first + d - 1, first + f - 1
        sep, notes = L.build_short_episode(ep, k, sid)
        probs = make_short.validate(sep)
        rt, t0, t1 = L.rebase_timings(timings, g0, g1)
        parole = timings["lines"][g1 - 1]["end"] - timings["lines"][g0 - 1]["start"]
        if parole > L.SHORT_DUREE_MAX_S:
            probs.append(f"{parole:.0f} s de parole : un Short tient en {L.SHORT_DUREE_MAX_S:.0f} s au plus")
        if probs:
            rapport["ignores"].append({"id": sid, "chapitre": k + 1, "raison": probs})
            continue
        st = common.get_status(sid) if (sdir / "status.json").exists() else None
        if st and st["etat"] in EN_COURS and not force:
            rapport["ignores"].append({"id": sid, "chapitre": k + 1, "raison": [f"déjà à l'état « {st['etat']} » (--force pour refaire)"]})
            continue
        sdir.mkdir(parents=True, exist_ok=True)
        L.decouper_voix(src / "voice.wav", sdir / "voice.wav", t0, t1)
        common.write_json(sdir / "timings.json", rt)
        common.write_json(sdir / "episode.json", sep)
        common.write_json(sdir / "voice_report.json", {"seuil": 0.9, "a_relire": [], "duree_s": rt["total"], "calcul_s": 0, "origine": long_id})
        common.write_json(sdir / "faits.json", L.faits_du_short(faits, g0, g1))
        pub_path = sdir / "publication.json"
        if force or not pub_path.exists():
            common.write_json(pub_path, L.publication_du_short(pub_long, ep, ch["short"]["accroche"], url_long))
        common.write_json(sdir / "origine.json", {"long": long_id, "chapitre": k + 1, "phrases_chapitre": [d, f], "phrases_globales": [g0, g1],
                                                   "de_s": round(t0, 3), "a_s": round(t1, 3), "notes": notes})
        common.set_status(sid, "ecrit", None, origine=long_id, chaine_id=common.chaine_de(long_id))  # le Short reste dans la chaîne de son long
        rapport["shorts"].append({"id": sid, "chapitre": k + 1, "phrases": f - d + 1, "duree_s": rt["total"], "notes": notes})
    for k, ch in marques[maximum:]:
        rapport["ignores"].append({"id": None, "chapitre": k + 1, "raison": [f"plus de {maximum} Shorts : segment ignoré"]})
    common.write_json(src / "cut_report.json", rapport)
    return rapport


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--max", type=int, default=L.SHORTS_MAX)
    ap.add_argument("--force", action="store_true", help="refait aussi les Shorts déjà avancés dans le parcours")
    a = ap.parse_args()
    r = cut(a.id, maximum=a.max, force=a.force)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["shorts"] else 2


if __name__ == "__main__":
    sys.exit(main())
