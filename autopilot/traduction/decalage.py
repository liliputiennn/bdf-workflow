"""Décalage de publication : une adaptation ne sort jamais avant la version source, ni en même temps.

Règle : l'épisode traduit (`traduction.json` dans son dossier) n'est publiable que lorsque la version source est `publie` depuis au moins
`source.decalage_heures` (profil de la chaîne cible, 48 h par défaut). Les créneaux propres à la chaîne (fuseau de New York…) s'appliquent ensuite.
YouTube pénalise le contenu en série publié au même moment sur plusieurs chaînes : ce décalage évite cet effet.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chaines  # noqa: E402
import common  # noqa: E402

DECALAGE_DEFAUT_H = 48.0


def _date(valeur) -> datetime | None:
    if not valeur:
        return None
    try:
        d = datetime.fromisoformat(str(valeur).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.astimezone().astimezone(timezone.utc)  # sans fuseau : heure locale de la machine


def decalage_heures(profil: dict | None) -> float:
    src = (profil or {}).get("source") or {}
    v = src.get("decalage_heures")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else DECALAGE_DEFAUT_H


def source_de(ep_id: str) -> str | None:
    """Identifiant de l'épisode source si `ep_id` est une adaptation, sinon None."""
    t = common.read_json(common.ep_dir(ep_id) / "traduction.json", None)
    return t.get("source") if isinstance(t, dict) and t.get("source") else None


def pret_a_sortir(ep_id: str, maintenant: datetime | None = None) -> tuple[bool, str]:
    """(publiable, raison). Un épisode qui n'est pas une adaptation est toujours publiable."""
    src = source_de(ep_id)
    if not src:
        return True, ""
    maintenant = maintenant or datetime.now(timezone.utc)
    st = common.get_status(src) if (common.ep_dir(src) / "status.json").exists() else None
    if not st or st.get("etat") != "publie":
        return False, f"la version source « {src} » n'est pas encore publiée"
    publie = _date((st.get("youtube") or {}).get("publie_a")) or _date(st.get("maj"))
    if publie is None:
        return False, f"date de publication de la version source « {src} » inconnue"
    prof = chaines.profil(common.chaine_de(ep_id))
    h = decalage_heures(prof)
    attendre = publie + timedelta(hours=h)
    if maintenant < attendre:
        return False, f"décalage de {h:g} h après la version source « {src} » : publiable à partir de {attendre.astimezone().isoformat(timespec='minutes')}"
    return True, ""
