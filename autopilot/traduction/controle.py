"""Contrôles propres à une ADAPTATION (épisode d'une chaîne cible tiré d'un épisode de sa chaîne source), appelés par `writer/valider.py`.

En plus de tous les contrôles ordinaires du rédacteur dans la langue cible (faits, sources, durée, titre, mentions interdites, chiffres en
lettres…), une adaptation doit :
  - garder la structure de la source (scènes, numéros de phrase, chiffres, faits, sources) : `parite.py` ;
  - ne pas être une copie : titre différent, phrases réécrites (pas recopiées), description différente ;
  - être dans la langue de la chaîne cible.

Une adaptation se reconnaît à sa demande `episodes-b/_traductions/<id>/demande.json` (écrite par `traduction/file.py`).
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from autopilot.common import EPISODES, now, read_json, write_json  # noqa: E402
from autopilot import langues  # noqa: E402
from autopilot.traduction import parite  # noqa: E402

PART_PHRASES_COPIEES_MAX = 0.2   # au-delà, le texte est jugé recopié de la source


def dossier_demande(ep_id: str) -> Path:
    return EPISODES / "_traductions" / ep_id


def demande_de(ep_id: str) -> dict | None:
    """La demande d'adaptation de cet identifiant, ou None si ce n'est pas une adaptation."""
    d = read_json(dossier_demande(ep_id) / "demande.json", None)
    return d if isinstance(d, dict) and d.get("source") else None


def nom_episode(source_id: str) -> str:
    return "episode-long.json" if (EPISODES / source_id / "episode-long.json").exists() else "episode.json"


def charger_source(source_id: str) -> dict | None:
    d = EPISODES / source_id
    ep = read_json(d / nom_episode(source_id), None)
    if not isinstance(ep, dict):
        return None
    return {"ep": ep, "faits": read_json(d / "faits.json", []), "pub": read_json(d / "publication.json", {}) or {},
            "long": nom_episode(source_id) == "episode-long.json"}


def _phrases(ep: dict) -> list[str]:
    if isinstance(ep.get("chapitres"), list):
        return [p for c in ep["chapitres"] for p in c.get("phrases", [])]
    return list(ep.get("phrases") or [])


def controles_traduction(ep: dict, faits, pub, demande: dict, langue: str, long: bool = False, brouillon: Path | None = None) -> tuple[list[str], list[str]]:
    """(erreurs, avertissements) propres à l'adaptation."""
    err: list[str] = []
    avert: list[str] = []
    src = charger_source(demande["source"])
    if src is None:
        return [f"épisode source « {demande['source']} » introuvable : impossible de vérifier l'adaptation"], avert
    if src["long"] != long:
        err.append("la source est un " + ("long" if src["long"] else "Short") + " : l'adaptation doit avoir le même format")
        return err, avert
    err += parite.comparer_episode(src["ep"], ep)
    err += parite.comparer_faits(src["faits"], faits)
    err += parite.comparer_publication(src["pub"], pub)
    ph_s, ph_c = _phrases(src["ep"]), _phrases(ep)
    if len(ph_s) == len(ph_c) and ph_s:
        copiees = sum(1 for a, b in zip(ph_s, ph_c) if a.strip().lower() == b.strip().lower())
        if copiees / len(ph_s) > PART_PHRASES_COPIEES_MAX:
            err.append(f"{copiees} phrase(s) sur {len(ph_s)} recopiées telles quelles de la source : adapte-les dans la langue cible")
    ms, mc = (src["ep"].get("miniature") or {}), (ep.get("miniature") or {})
    if ms.get("style") and ms.get("style") == mc.get("style"):
        avert.append(f"miniature : même style « {mc.get('style')} » que la version source : un style différent aide à distinguer les deux chaînes")
    for cle in ("texte_haut", "gros"):
        if ms.get(cle) and str(ms.get(cle)).strip().lower() == str(mc.get(cle, "")).strip().lower() and not str(ms[cle]).strip().replace(" ", "").isdigit() \
                and not any(ch.isdigit() for ch in str(ms[cle])):
            err.append(f"miniature : « {cle} » est identique à la source (« {ms[cle]} ») : traduis-le")
    return err, avert


def finaliser(ep_id: str, demande: dict, avertissements: list[str], accepte: bool = True) -> None:
    """Adaptation acceptée (ou mise en quarantaine) : `traduction.json` dans le dossier de l'épisode (source, moteur, date), puis la demande est consommée."""
    d = EPISODES / ep_id
    ancien = read_json(d / "traduction.json", None)
    ancien = ancien if isinstance(ancien, dict) else {}
    write_json(d / "traduction.json", {
        "source": demande["source"], "chaine_source": demande.get("chaine_source"), "langue": demande.get("langue"),
        "moteur": ancien.get("moteur") or "claude", "demande_le": demande.get("cree_le"), "acceptee_le": now() if accepte else None, "acceptee": accepte,
        "a_relire": bool(ancien.get("a_relire")), "avertissements": avertissements[:10],
    })
    shutil.rmtree(dossier_demande(ep_id), ignore_errors=True)
