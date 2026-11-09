"""Stock d'épisodes et besoins du rédacteur.

Usage :
    python autopilot/writer/stock.py etat                 # tableau lisible
    python autopilot/writer/stock.py besoin [--cible N] [--max M]   # JSON : combien écrire et sur quels sujets

Stock = épisodes écrits mais pas encore publiés (hors quarantaine), plus les Shorts que les longs écrits vont encore donner (repères `short`).
Cadence (8 nov. 2026) : 8 Shorts par jour + 3 longs par semaine, soit ≈ 8,4 vidéos par jour : le stock se compte en vidéos, la cible en jours.
`besoin` attribue les sujets (ils ne seront pas redonnés pendant 2 jours) : à appeler une fois par passage.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.common import EPISODES, ETATS, STATE, ep_dir, get_status, list_episodes, now, read_json, write_json  # noqa: E402
from autopilot.writer import gabarits, sujets  # noqa: E402
from autopilot import chaines  # noqa: E402

CONFIG = read_json(Path(__file__).with_name("config.json"), {}) or {}
CIBLE = CONFIG.get("cible_jours_de_stock", 7)
MAX_PAR_PASSAGE = CONFIG.get("max_par_passage", 3)
SHORTS_PAR_JOUR = CONFIG.get("shorts_par_jour", 8)
LONGS_PAR_SEMAINE = CONFIG.get("longs_par_semaine", 3)             # rythme voulu : 3 longs publiés par semaine, les autres jours un Short tiré d'un long
SEMAINES_DE_LONGS = CONFIG.get("semaines_de_longs_en_stock", 2)    # on garde toujours 2 semaines de longs d'avance


def cadence(chaine: str | None = None) -> tuple[int, int]:
    """(Shorts par jour, longs par semaine) de la chaîne ; la chaîne par défaut garde la cadence de config.json."""
    p = chaines.profil(chaine or chaines.CHAINE_DEFAUT) or chaines.defaut_fr()
    return chaines.frequence(p, SHORTS_PAR_JOUR, LONGS_PAR_SEMAINE)


def rythme_par_jour(chaine: str | None = None) -> float:
    shorts, longs = cadence(chaine)
    return shorts + longs / 7


def shorts_attendus(dossier: Path) -> int:
    """Shorts qu'un long écrit va encore donner : ses repères `short`, tant qu'il n'a pas été découpé (cut_report.json absent)."""
    if (dossier / "cut_report.json").exists():
        return 0
    ep = read_json(dossier / "episode-long.json", None)
    if not isinstance(ep, dict):
        return 0
    return sum(1 for c in ep.get("chapitres") or [] if isinstance(c, dict) and c.get("short"))


def compter(chaine: str | None = None) -> dict:
    """Stock d'UNE chaîne (la chaîne par défaut si `chaine` est omis) : les épisodes des autres ne comptent pas."""
    ch = chaine or chaines.CHAINE_DEFAUT
    par_etat = {e: 0 for e in ETATS}
    for i in list_episodes(chaine=ch):
        par_etat[get_status(i)["etat"]] += 1
    brouillons = len(sujets.brouillons(ch))
    en_stock = sum(par_etat[e] for e in ("ecrit", "voix", "rendu", "controle", "pret", "programme"))
    futurs = sum(shorts_attendus(ep_dir(i)) for i in list_episodes(chaine=ch)
                 if (ep_dir(i) / "episode-long.json").exists() and get_status(i)["etat"] in ("ecrit", "voix", "rendu", "controle", "pret", "programme"))
    futurs += sum(shorts_attendus(d) for d in sujets.brouillons(ch) if (d / "episode-long.json").exists())
    return {"par_etat": par_etat, "brouillons": brouillons, "shorts_a_venir": futurs, "videos_en_stock": en_stock,
            "jours_de_stock": round((en_stock + futurs) / rythme_par_jour(ch), 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("commande", choices=["etat", "besoin"])
    ap.add_argument("--cible", type=int, default=CIBLE)
    ap.add_argument("--max", type=int, default=MAX_PAR_PASSAGE)
    ap.add_argument("--chaine", default=chaines.CHAINE_DEFAUT, help="chaîne pour laquelle écrire (profils : autopilot/chaines/)")
    a = ap.parse_args()
    profil = chaines.profil(a.chaine)
    if profil is None:
        raise SystemExit(f"chaîne inconnue : {a.chaine} (profils : {', '.join(chaines.charger_profils())})")
    c = compter(a.chaine)
    rythme = rythme_par_jour(a.chaine)
    longs_semaine = cadence(a.chaine)[1]
    if a.commande == "etat":
        print(f"Chaîne : {profil['nom']} ({a.chaine}){'' if profil['active'] else ' — INACTIVE'}")
        print(f"Stock : {c['videos_en_stock']} vidéo(s) + {c['shorts_a_venir']} Short(s) à venir des longs = {c['jours_de_stock']} jour(s) d'avance "
              f"(cible {a.cible}, à {rythme:.1f} vidéos/jour) | brouillons : {c['brouillons']} | sujets restants en banque : {sujets.restants(chaine=a.chaine)}")
        for e, n in c["par_etat"].items():
            if n:
                print(f"  {e:12s} {n}")
        return
    voulu = math.ceil(a.cible * rythme)
    manque = max(0, voulu - c["videos_en_stock"] - c["shorts_a_venir"] - c["brouillons"])
    # longs d'avance (écrits, pas encore publiés, hors quarantaine) + brouillons de longs
    longs_dispo = sum(1 for i in list_episodes(chaine=a.chaine) if (ep_dir(i) / "episode-long.json").exists()
                      and get_status(i)["etat"] in ("ecrit", "voix", "rendu", "controle", "pret", "programme")) + sum(
        1 for d in sujets.brouillons(a.chaine) if (d / "episode-long.json").exists())
    longs_a_ecrire = max(0, longs_semaine * SEMAINES_DE_LONGS - longs_dispo)
    a_ecrire = min(a.max, max(manque, longs_a_ecrire))
    reprise = profil.get("source")  # chaîne qui reprend une autre (multilingue) : rien à inventer, on adapte (traduction/traduire.py besoin)
    if reprise:
        a_ecrire, longs_a_ecrire = 0, 0
    # un seul long à la fois dans le workflow : il demande des heures de voix (GPU) et de rendu
    longs_en_cours = sum(1 for i in list_episodes(chaine=a.chaine) if (ep_dir(i) / "episode-long.json").exists()
                         and get_status(i)["etat"] in ("ecrit", "voix", "rendu", "controle")) + sum(
        1 for d in sujets.brouillons(a.chaine) if (d / "episode-long.json").exists())
    # les Shorts viennent des longs : on écrit d'abord les longs manquants (le cloud fabrique un long par nuit)
    choisis = sujets.prochains(a_ecrire, max_longs=min(longs_a_ecrire, a_ecrire) if longs_a_ecrire else max(0, 1 - longs_en_cours), chaine=a.chaine) if a_ecrire else []
    choisis = gabarits.attribuer(choisis)  # gabarit visuel, forme de titre et style de miniature qui tournent (variété contre le « contenu inauthentique »)
    bilan = {
        "cible": a.cible, "jours_de_stock": c["jours_de_stock"], "videos_en_stock": c["videos_en_stock"], "shorts_a_venir": c["shorts_a_venir"],
        "videos_voulues": voulu, "rythme_par_jour": round(rythme, 2), "a_ecrire": a_ecrire,
        "longs_disponibles": longs_dispo, "longs_a_ecrire": longs_a_ecrire,
        "longs_en_cours": longs_en_cours, "sujets": choisis, "sujets_restants_en_banque": sujets.restants(chaine=a.chaine),
        "proposer_de_nouveaux_sujets": False if reprise else sujets.a_reapprovisionner(a.chaine),
        "sujets_restants_shorts": sujets.restants("short", a.chaine), "sujets_restants_longs": sujets.restants("long", a.chaine),
        # la chaîne pour laquelle on écrit (le rédacteur passe `--chaine <id>` à valider.py) et ce qui la distingue
        "adaptation_de": reprise["chaine"] if reprise else None,
        "chaine": a.chaine, "chaine_active": bool(profil["active"]), "langue": profil["langue"], "format": profil["format"],
        "consignes_format": chaines.appeler_hook(profil, "consignes", profil, defaut=""),  # consignes propres au format de la chaîne (module de format)
        "style": profil["style"], "format_options": profil["format_options"],
    }
    # redaction.json : le haut du fichier reste celui de la chaîne par défaut (lu tel quel par l'orchestrateur et la web app) ;
    # `par_chaine` garde le dernier bilan de chacune. Le « dernier passage » avance pour toutes (c'est la même session de rédaction).
    ancien = read_json(STATE / "redaction.json", {}) or {}
    par_chaine = dict(ancien.get("par_chaine") or {})
    par_chaine[a.chaine] = {"dernier_passage": now(), **bilan}
    haut = bilan if a.chaine == chaines.CHAINE_DEFAUT else {k: v for k, v in ancien.items() if k not in ("dernier_passage", "par_chaine")}
    write_json(STATE / "redaction.json", {**haut, "dernier_passage": now(), "par_chaine": par_chaine})
    print(json.dumps(bilan, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
