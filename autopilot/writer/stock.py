"""Stock d'épisodes et besoins du rédacteur.

Usage :
    python autopilot/writer/stock.py etat                 # tableau lisible
    python autopilot/writer/stock.py besoin [--cible N] [--max M]   # JSON : combien écrire et sur quels sujets

Stock = épisodes écrits mais pas encore publiés (hors quarantaine), à 1 vidéo par jour = nombre de jours d'avance.
`besoin` attribue les sujets (ils ne seront pas redonnés pendant 2 jours) : à appeler une fois par passage.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.common import EPISODES, ETATS, STATE, ep_dir, get_status, list_episodes, now, read_json, write_json  # noqa: E402
from autopilot.writer import sujets  # noqa: E402

CONFIG = read_json(Path(__file__).with_name("config.json"), {}) or {}
CIBLE = CONFIG.get("cible_jours_de_stock", 7)
MAX_PAR_PASSAGE = CONFIG.get("max_par_passage", 3)
LONGS_PAR_SEMAINE = CONFIG.get("longs_par_semaine", 3)             # rythme voulu : 3 longs publiés par semaine, les autres jours un Short tiré d'un long
SEMAINES_DE_LONGS = CONFIG.get("semaines_de_longs_en_stock", 2)    # on garde toujours 2 semaines de longs d'avance


def compter() -> dict:
    par_etat = {e: 0 for e in ETATS}
    for i in list_episodes():
        par_etat[get_status(i)["etat"]] += 1
    brouillons = len([d for d in (EPISODES / "_brouillons").glob("*") if d.is_dir()])
    en_stock = sum(par_etat[e] for e in ("ecrit", "voix", "rendu", "controle", "pret", "programme"))
    return {"par_etat": par_etat, "brouillons": brouillons, "jours_de_stock": en_stock}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("commande", choices=["etat", "besoin"])
    ap.add_argument("--cible", type=int, default=CIBLE)
    ap.add_argument("--max", type=int, default=MAX_PAR_PASSAGE)
    a = ap.parse_args()
    c = compter()
    if a.commande == "etat":
        print(f"Stock : {c['jours_de_stock']} jour(s) d'avance (cible {a.cible}) | brouillons : {c['brouillons']} | sujets restants en banque : {sujets.restants()}")
        for e, n in c["par_etat"].items():
            if n:
                print(f"  {e:12s} {n}")
        return
    manque = max(0, a.cible - c["jours_de_stock"] - c["brouillons"])
    # longs d'avance (écrits, pas encore publiés, hors quarantaine) + brouillons de longs
    longs_dispo = sum(1 for i in list_episodes() if (ep_dir(i) / "episode-long.json").exists()
                      and get_status(i)["etat"] in ("ecrit", "voix", "rendu", "controle", "pret", "programme")) + sum(
        1 for d in (EPISODES / "_brouillons").glob("*") if (d / "episode-long.json").exists())
    longs_a_ecrire = max(0, LONGS_PAR_SEMAINE * SEMAINES_DE_LONGS - longs_dispo)
    a_ecrire = min(a.max, max(manque, longs_a_ecrire))
    # un seul long à la fois dans le workflow : il demande des heures de voix (GPU) et de rendu
    longs_en_cours = sum(1 for i in list_episodes() if (ep_dir(i) / "episode-long.json").exists()
                         and get_status(i)["etat"] in ("ecrit", "voix", "rendu", "controle")) + sum(
        1 for d in (EPISODES / "_brouillons").glob("*") if (d / "episode-long.json").exists())
    # les Shorts viennent des longs : on écrit d'abord les longs manquants (le cloud fabrique un long par nuit)
    choisis = sujets.prochains(a_ecrire, max_longs=min(longs_a_ecrire, a_ecrire) if longs_a_ecrire else max(0, 1 - longs_en_cours)) if a_ecrire else []
    bilan = {
        "cible": a.cible, "jours_de_stock": c["jours_de_stock"], "a_ecrire": a_ecrire,
        "longs_disponibles": longs_dispo, "longs_a_ecrire": longs_a_ecrire,
        "longs_en_cours": longs_en_cours, "sujets": choisis, "sujets_restants_en_banque": sujets.restants(),
        "proposer_de_nouveaux_sujets": sujets.restants() < 10,
    }
    write_json(STATE / "redaction.json", {"dernier_passage": now(), **bilan})
    print(json.dumps(bilan, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
