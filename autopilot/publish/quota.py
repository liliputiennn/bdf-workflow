"""Registre de quota YouTube : `autopilot/state/youtube_quota.json`.

Deux compteurs, remis à zéro à minuit heure du Pacifique :
- `unites` : réserve générale (10 000/jour) — miniature 50, lecture 1, mise à jour 50 ;
- `envois` : compteur propre à `videos.insert` (100/jour, 1 par envoi).
Les coûts viennent de `config.json` (section `quota`) : si Google change les règles, on ajuste là.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
import horaire  # noqa: E402
from erreurs import ErreurQuota  # noqa: E402


def maintenant_utc() -> datetime:
    return datetime.now(timezone.utc)


class RegistreQuota:
    def __init__(self, cfg: dict, horloge=maintenant_utc):
        self.cfg = cfg["quota"]
        self.fuseau = cfg["fuseau"]
        self.horloge = horloge

    @property
    def chemin(self) -> Path:
        return common.STATE / "youtube_quota.json"

    def _verrou(self):
        return common.file_lock(common.STATE / "youtube_quota.lock", ttl_s=60, wait_s=15)

    def _charger(self) -> dict:
        jour = horaire.jour_pacifique(self.horloge()).isoformat()
        reg = common.read_json(self.chemin, None) or {}
        if reg.get("jour_pt") != jour:
            reg = {"jour_pt": jour, "unites": 0, "envois": 0, "epuise": False, "journal": []}
        reg["plafond_unites"] = self.cfg["plafond_unites"]
        reg["plafond_envois"] = self.cfg["plafond_envois"]
        return reg

    def etat(self) -> dict:
        return self._charger()

    def prochain_essai(self) -> str:
        return horaire.iso_utc(horaire.prochain_minuit_pacifique(self.horloge()))

    def _manque(self, reg: dict, unites: int, envois: int) -> str | None:
        if reg.get("epuise"):
            return "quota déclaré épuisé par YouTube pour aujourd'hui"
        if reg["unites"] + unites > reg["plafond_unites"]:
            return f"{reg['unites']} + {unites} unités dépasseraient le plafond de {reg['plafond_unites']}"
        if reg["envois"] + envois > reg["plafond_envois"]:
            return f"{reg['envois']} + {envois} envois dépasseraient le plafond de {reg['plafond_envois']}"
        return None

    def verifier(self, unites: int = 0, envois: int = 0) -> None:
        """Lève ErreurQuota (à reporter au lendemain) si l'opération ne tient pas dans la journée."""
        with self._verrou():
            manque = self._manque(self._charger(), unites, envois)
        if manque:
            raise ErreurQuota(manque, self.prochain_essai())

    def depenser(self, operation: str, unites: int = 0, envois: int = 0) -> None:
        with self._verrou():
            reg = self._charger()
            reg["unites"] += unites
            reg["envois"] += envois
            reg["journal"] = (reg["journal"] + [{"t": common.now(), "op": operation, "unites": unites, "envois": envois}])[-200:]
            reg["maj"] = common.now()
            common.write_json(self.chemin, reg)

    def declarer_epuise(self, raison: str) -> None:
        """YouTube a répondu « quota dépassé » : plus rien aujourd'hui, quoi que dise notre compteur."""
        with self._verrou():
            reg = self._charger()
            reg.update(epuise=True, raison=raison, maj=common.now())
            common.write_json(self.chemin, reg)

    def cout_envoi(self) -> tuple[int, int]:
        return self.cfg["cout_envoi_unites"], self.cfg["cout_envoi_compteur"]

    def cout_total_publication(self) -> tuple[int, int]:
        """(unités, envois) pour envoi + miniature + relecture."""
        u, e = self.cout_envoi()
        return u + self.cfg["cout_miniature"] + self.cfg["cout_lecture"], e
