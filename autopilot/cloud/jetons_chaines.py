"""Cloud : écrit dans autopilot/secrets/ le jeton YouTube de chaque chaîne, à partir des secrets GitHub (variables d'environnement).

Usage (étape « Identifiants » de publication.yml) : python autopilot/cloud/jetons_chaines.py [--liste]
Convention : le secret `YT_TOKEN_<ID>` (ID du profil en majuscules, « - » devient « _ ») devient le fichier `jeton_fichier` du profil
(ex. profil `musique-enfants` : secret YT_TOKEN_MUSIQUE_ENFANTS -> autopilot/secrets/token-musique-enfants.json).
La chaîne par défaut (fr) garde le secret historique `YT_TOKEN` -> token.json (traité par le workflow lui-même).
Ne lit jamais autopilot/secrets/ ; n'affiche jamais une valeur : seulement « présent » ou « absent » par chaîne.
Une valeur qui n'est pas du JSON avec un `refresh_token` est refusée (message sans la valeur), le fichier n'est pas écrit.
"""
import json
import os
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent.parent))
from autopilot import chaines  # noqa: E402

INTERDITS = {"client_secret.json", "tiktok_token.json", "tiktok_client.json"}


def nom_secret(ident: str) -> str:
    """Nom du secret GitHub d'une chaîne : `en` -> YT_TOKEN_EN, `musique-enfants` -> YT_TOKEN_MUSIQUE_ENFANTS (fr : YT_TOKEN)."""
    if ident == chaines.CHAINE_DEFAUT:
        return "YT_TOKEN"
    return "YT_TOKEN_" + ident.upper().replace("-", "_")


def planifier(profils: dict, env: dict) -> list[dict]:
    """Pour chaque chaîne : {id, secret, fichier, present, valide} (fonction pure, testée). Ne renvoie jamais la valeur du secret."""
    plan = []
    for ident in sorted(profils):
        fichier = profils[ident].get("jeton_fichier") or "token.json"
        if not chaines.FICHIER_JETON_VALIDE.match(fichier) or fichier in INTERDITS:
            plan.append({"id": ident, "secret": nom_secret(ident), "fichier": fichier, "present": False, "valide": False, "erreur": "jeton_fichier invalide"})
            continue
        brut = (env.get(nom_secret(ident)) or "").strip()
        valide = False
        if brut:
            try:
                valide = bool(json.loads(brut).get("refresh_token"))
            except (ValueError, AttributeError):
                valide = False
        plan.append({"id": ident, "secret": nom_secret(ident), "fichier": fichier, "present": bool(brut), "valide": valide})
    return plan


def ecrire(plan: list[dict], env: dict, dossier: Path) -> int:
    """Écrit les jetons valides ; renvoie le nombre de fichiers écrits. Un fichier déjà posé par le workflow (YT_TOKEN -> token.json) n'est pas touché."""
    dossier.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in plan:
        if p["id"] == chaines.CHAINE_DEFAUT or not p["valide"]:
            continue
        (dossier / p["fichier"]).write_text(env[p["secret"]].strip(), encoding="utf-8")
        n += 1
    return n


def main() -> int:
    liste = "--liste" in sys.argv
    profils = chaines.charger_profils()
    plan = planifier(profils, os.environ)
    for p in plan:
        etat = "valide" if p["valide"] else ("PRÉSENT MAIS INVALIDE (JSON avec refresh_token attendu)" if p["present"] else "absent")
        actif = "active" if chaines.est_active(p["id"], profils) else "inactive"
        print(f"{p['id']:<16} secret {p['secret']:<28} -> {p['fichier']:<28} {etat} (chaîne {actif})")
        if p["present"] and not p["valide"]:
            print(f"::warning::{p['secret']} n'est pas un jeton exploitable ; il est ignoré")
    if liste:
        return 0
    n = ecrire(plan, os.environ, ICI.parent / "secrets")
    print(f"{n} jeton(s) de chaîne écrit(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
