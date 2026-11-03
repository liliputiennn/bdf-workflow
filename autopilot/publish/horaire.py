"""Heures et fuseaux sans base de fuseaux (Windows n'a pas `tzdata`) : règles d'heure d'été écrites en dur."""
from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc


def _dimanche(annee: int, mois: int, rang: int) -> date:
    """rang > 0 : n-ième dimanche du mois ; rang = -1 : dernier dimanche."""
    if rang > 0:
        d = date(annee, mois, 1)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=rang - 1)
    d = date(annee + (mois == 12), mois % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def decalage(fuseau: str, instant_utc: datetime) -> timedelta:
    """Décalage par rapport à UTC pour un instant donné."""
    a = instant_utc.year
    if fuseau == "Europe/Paris":
        debut = datetime.combine(_dimanche(a, 3, -1), datetime.min.time(), UTC) + timedelta(hours=1)
        fin = datetime.combine(_dimanche(a, 10, -1), datetime.min.time(), UTC) + timedelta(hours=1)
        return timedelta(hours=2 if debut <= instant_utc < fin else 1)
    if fuseau == "America/Los_Angeles":
        debut = datetime.combine(_dimanche(a, 3, 2), datetime.min.time(), UTC) + timedelta(hours=10)
        fin = datetime.combine(_dimanche(a, 11, 1), datetime.min.time(), UTC) + timedelta(hours=9)
        return timedelta(hours=-7 if debut <= instant_utc < fin else -8)
    if fuseau in ("UTC", "Etc/UTC"):
        return timedelta(0)
    raise ValueError(f"fuseau non géré : {fuseau} (utiliser Europe/Paris, America/Los_Angeles ou UTC)")


def vers_local(instant_utc: datetime, fuseau: str) -> datetime:
    return (instant_utc + decalage(fuseau, instant_utc)).replace(tzinfo=None)


def local_vers_utc(naif: datetime, fuseau: str) -> datetime:
    approx = naif.replace(tzinfo=UTC)
    for _ in range(2):
        approx = naif.replace(tzinfo=UTC) - decalage(fuseau, approx)
    return approx


def jour_pacifique(instant_utc: datetime) -> date:
    return vers_local(instant_utc, "America/Los_Angeles").date()


def prochain_minuit_pacifique(instant_utc: datetime) -> datetime:
    demain = jour_pacifique(instant_utc) + timedelta(days=1)
    return local_vers_utc(datetime.combine(demain, datetime.min.time()), "America/Los_Angeles")


def prochain_creneau(heure: str, fuseau: str, maintenant_utc: datetime, jours_pris: set[date], marge_min: int = 30) -> datetime:
    """Premier jour libre dont l'heure choisie est à plus de `marge_min` minutes. Retourne un instant UTC."""
    h, m = (int(x) for x in heure.split(":"))
    jour = vers_local(maintenant_utc, fuseau).date()
    while True:
        if jour not in jours_pris:
            cand = local_vers_utc(datetime.combine(jour, datetime.min.time()).replace(hour=h, minute=m), fuseau)
            if cand > maintenant_utc + timedelta(minutes=marge_min):
                return cand
        jour += timedelta(days=1)


def iso_utc(instant_utc: datetime) -> str:
    return instant_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def lire_iso(texte: str) -> datetime:
    return datetime.fromisoformat(texte.replace("Z", "+00:00")).astimezone(UTC)
