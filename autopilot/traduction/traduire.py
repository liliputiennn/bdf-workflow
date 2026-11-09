"""Traduction automatique des chaînes cibles : file de demandes pour Claude (chemin principal) + repli gratuit.

    python autopilot/traduction/traduire.py besoin [--chaine en] [--max N]   # crée les demandes qui manquent, affiche la file (lu par le rédacteur planifié)
    python autopilot/traduction/traduire.py repli  [--chaine en] [--max N] [--forcer] [--sans-reseau]   # moteur gratuit pour les demandes que Claude n'a pas prises
    python autopilot/traduction/traduire.py demander <id-source> --chaine en  # demande manuelle (même une source déjà découpée d'un long)
    python autopilot/traduction/traduire.py etat [--json]

Chemin principal : le rédacteur planifié (Claude) lit `besoin`, écrit `episodes-b/_brouillons/<cible>-<id>/{episode,faits,publication}.json` puis lance
`python autopilot/writer/valider.py <cible>-<id> --chaine <cible>` : circuit du rédacteur, avec ses lots et son quota d'usage (voir CONSIGNES-TRADUCTION.md).
Repli : Claude bloqué (`state/claude_blocked.json`) ou sans réponse depuis `source.attente_claude_heures` -> MarianMT (Apache-2.0), puis le même `valider.py`.
Rien ici n'active une chaîne ni ne publie : `active` reste une décision de l'utilisateur.
"""
import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot import chaines, langues  # noqa: E402
from autopilot.common import EPISODES, STATE, get_status, now, read_json, set_status, write_json  # noqa: E402
from autopilot.traduction import adaptation, file as file_, moteurs  # noqa: E402
from autopilot.writer import valider  # noqa: E402

MAX_ECHECS_MOTEUR = 3
FICHIER_ETAT = "traduction.json"


def claude_bloque() -> bool:
    return (STATE / "claude_blocked.json").exists()


def age_heures(dem: dict) -> float:
    try:
        return (datetime.now() - datetime.fromisoformat(dem["cree_le"])).total_seconds() / 3600
    except (KeyError, ValueError, TypeError):
        return 0.0


def a_traiter_par_repli(p: dict, forcer: bool = False) -> list[str]:
    """Demandes de la chaîne que le repli peut prendre : sans brouillon de Claude et (Claude bloqué, ou demande trop ancienne, ou --forcer)."""
    opt = file_.options(p)
    ids = []
    for i in file_.demandes_ouvertes(p["id"]):
        if (EPISODES / "_brouillons" / i).exists():
            continue  # Claude (ou un passage précédent) a déjà écrit un brouillon : valider.py décide
        dem = read_json(file_.dossier_demandes() / i / "demande.json", {}) or {}
        if forcer or claude_bloque() or age_heures(dem) >= opt["attente_claude_heures"]:
            ids.append(i)
    return ids


def ecrire_brouillon(dem: dict, p: dict, traducteur, moteur_nom: str) -> Path:
    """Traduit la source avec `traducteur` et écrit le brouillon (mêmes fichiers que ceux de Claude) dans `_brouillons/<id>/`."""
    if dem.get("format") != "short":
        raise NotImplementedError("le repli gratuit ne traduit que les Shorts : un long attend Claude")
    langue = dem["langue"]
    etiquette = p["nom"].split(" (")[0]
    ep = adaptation.adapter_episode(dem["episode"], traducteur, langue, etiquette, dem["id"])
    faits = adaptation.adapter_faits(dem["faits"], traducteur, langue)
    pub = adaptation.adapter_publication(dem["publication"], traducteur, langue, p["id"])
    d = EPISODES / "_brouillons" / dem["id"]
    write_json(d / "episode.json", ep)
    write_json(d / "faits.json", faits)
    write_json(d / "publication.json", pub)
    write_json(d / "traduction.json", {"moteur": moteur_nom, "a_relire": True})
    return d


def _echec(dem: dict, raison: str) -> str:
    """Un échec du moteur (modèle absent, plantage…) : on le note sur la demande ; au bout de MAX_ECHECS_MOTEUR, l'épisode part en quarantaine avec la raison."""
    f = file_.dossier_demandes() / dem["id"] / "demande.json"
    cur = read_json(f, dem) or dem
    cur["echecs"] = int(cur.get("echecs", 0)) + 1
    cur["derniere_erreur"] = raison[:300]
    write_json(f, cur)
    if cur["echecs"] >= MAX_ECHECS_MOTEUR:
        ep_dir = EPISODES / dem["id"]
        write_json(ep_dir / "episode.json", {**cur["episode"], "id": dem["id"]})
        write_json(ep_dir / "traduction.json", {"source": dem["source"], "moteur": "marian", "acceptee": False, "raison": raison[:300]})
        set_status(dem["id"], "quarantaine", f"traduction impossible ({cur['echecs']} échecs) : {raison[:200]}", chaine_id=dem["chaine_cible"])
        import shutil
        shutil.rmtree(file_.dossier_demandes() / dem["id"], ignore_errors=True)
        return "quarantaine"
    return "echec"


def repli(p: dict, maximum: int | None = None, forcer: bool = False, traducteur=None, sans_reseau: bool = False) -> dict:
    """Traduit avec le moteur gratuit les demandes laissées par Claude. Chaque demande est isolée : une erreur n'arrête pas les autres."""
    bilan = {"chaine": p["id"], "acceptes": [], "a_corriger": [], "quarantaine": [], "echecs": [], "ignores": [], "moteur": None}
    de = langues.langue_de((chaines.profil(p["source"]["chaine"]) or {}).get("langue", "fr"))
    vers = langues.langue_de(p["langue"])
    if traducteur is None:
        ok, msg = moteurs.disponible(f"{de}-{vers}")
        bilan["moteur"] = msg
        if not ok:
            bilan["indisponible"] = msg
            return bilan
        traducteur = moteurs.MoteurMarian(de, vers)
    else:
        bilan["moteur"] = getattr(traducteur, "nom", "injecte")
    nom = getattr(traducteur, "nom", "marian")
    todo = a_traiter_par_repli(p, forcer)
    maxi = file_.options(p)["max_par_passage"] if maximum is None else maximum
    for i in todo[:maxi]:
        dem = read_json(file_.dossier_demandes() / i / "demande.json", None)
        if not isinstance(dem, dict):
            continue
        if dem.get("format") != "short":
            bilan["ignores"].append({"id": i, "raison": "long : attend Claude"})
            continue
        try:
            ecrire_brouillon(dem, p, traducteur, nom)
        except Exception as e:  # noqa: BLE001 — isolation : un épisode raté ne bloque pas les suivants
            bilan["echecs"].append({"id": i, "raison": str(e)[:200], "suite": _echec(dem, f"{type(e).__name__}: {e}")})
            continue
        for _ in range(valider.MAX_ESSAIS):  # même circuit que le rédacteur ; un moteur déterministe échoue 3 fois de suite puis part en quarantaine
            code, res = valider.valider_brouillon(i, p["id"], sans_reseau=sans_reseau)
            if code != 1:
                break
        (bilan["acceptes"] if code == 0 else bilan["quarantaine"] if code == 2 else bilan["a_corriger"]).append(i if code != 2 else {"id": i, "erreurs": res.get("erreurs", [])[:4]})
    return bilan


def passe(chaine: str | None = None, maximum: int | None = None, avec_repli: bool = True, dry_run: bool = False,
          traducteur=None, sans_reseau: bool = False, forcer: bool = False) -> dict:
    """Une passe d'alimentation de toutes les chaînes cibles (ou d'une seule) : demandes, puis repli. Isolation par chaîne."""
    bilan: dict = {}
    for p in file_.chaines_cibles(chaine):
        b: dict = {}
        try:
            if dry_run:
                b = {"stock": file_.stock_cible(p), "sources_eligibles": file_.sources_eligibles(p)[: file_.options(p)["max_par_passage"]], "dry_run": True}
            else:
                b["demandes"] = file_.alimenter(p, maximum)
                if avec_repli:
                    b["repli"] = repli(p, maximum, forcer=forcer, traducteur=traducteur, sans_reseau=sans_reseau)
        except Exception:  # noqa: BLE001
            b["erreur"] = traceback.format_exc()[-400:]
        bilan[p["id"]] = b
    if not dry_run:
        ecrire_etat()
    return bilan


def etat(chaine: str | None = None) -> dict:
    return {"maj": now(), "claude_bloque": claude_bloque(),
            "moteur_repli": {paire: dict(zip(("disponible", "detail"), moteurs.disponible(paire))) for paire in ("fr-en",)},
            "chaines": {p["id"]: file_.etat_chaine(p) for p in file_.chaines_cibles(chaine)}}


def ecrire_etat() -> dict:
    """`autopilot/state/traduction.json` : lu par l'orchestrateur (`etat`) et la web app (écrans Chaînes et Feuille de route)."""
    e = etat()
    write_json(STATE / FICHIER_ETAT, e)
    return e


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("besoin")
    b.add_argument("--chaine")
    b.add_argument("--max", type=int)
    r = sub.add_parser("repli")
    r.add_argument("--chaine")
    r.add_argument("--max", type=int)
    r.add_argument("--forcer", action="store_true", help="traduire aussi les demandes récentes (sans attendre Claude)")
    r.add_argument("--sans-reseau", action="store_true")
    d = sub.add_parser("demander")
    d.add_argument("source")
    d.add_argument("--chaine", required=True)
    e = sub.add_parser("etat")
    e.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "besoin":
        cibles = file_.chaines_cibles(a.chaine)
        if not cibles:
            print(json.dumps({"ok": True, "chaines": [], "message": "aucune chaîne cible (profil avec `source`, active ou en préparation)"}, ensure_ascii=False))
            return 0
        sortie = []
        for p in cibles:
            bilan = file_.alimenter(p, a.max)
            ouvertes = [i for i in file_.demandes_ouvertes(p["id"]) if not (EPISODES / "_brouillons" / i).exists()]
            sortie.append({**bilan, "langue": p["langue"], "consignes": file_.CONSIGNES, "a_traduire": [
                {"id": i, "dossier_demande": str((file_.dossier_demandes() / i).relative_to(EPISODES.parent)),
                 "brouillon_a_ecrire": f"episodes-b/_brouillons/{i}/", "valider": f"python autopilot/writer/valider.py {i} --chaine {p['id']}"} for i in ouvertes]})
        ecrire_etat()
        print(json.dumps({"ok": True, "chaines": sortie}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "repli":
        cibles = file_.chaines_cibles(a.chaine)
        res = {p["id"]: repli(p, a.max, forcer=a.forcer, sans_reseau=a.sans_reseau) for p in cibles}
        ecrire_etat()
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "demander":
        cibles = file_.chaines_cibles(a.chaine)
        if not cibles:
            print(f"chaîne cible « {a.chaine} » inconnue, invalide ou sans `source`")
            return 1
        res = file_.alimenter(cibles[0], seulement_source=a.source)
        ecrire_etat()
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["creees"] else 1
    e_ = ecrire_etat()
    if a.json:
        print(json.dumps(e_, ensure_ascii=False, indent=1))
    else:
        for ident, c in e_["chaines"].items():
            print(f"{ident} ← {c['source']} ({c['mode']}, {c['langue']}) | voix : {c['voix']['mode'] or 'MANQUANTE'} | stock {c['stock']['jours_de_stock']} j "
                  f"(cible {c['cible_jours_de_stock']}) | file : {c['file']['demandes']} demande(s), {c['file']['brouillons']} brouillon(s) | adaptés : {c['adaptes']} "
                  f"{c['adaptes_par_etat']} | sources restantes : {c['sources_restantes']} | Claude bloqué : {c['claude_bloque']}")
        print("moteur de repli :", {k: v["disponible"] for k, v in e_["moteur_repli"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
