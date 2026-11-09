"""Connecte une chaîne YouTube à son profil : autorisation dans ton navigateur, jeton enregistré, chaîne vérifiée.

    python autopilot/publish/connecter_chaine.py <id>                 # connexion + vérification
    python autopilot/publish/connecter_chaine.py <id> --verifier      # seulement vérifier le jeton déjà enregistré
    python autopilot/publish/connecter_chaine.py <id> --refaire       # reprendre la connexion d'une chaîne déjà connectée
    python autopilot/publish/connecter_chaine.py --liste              # chaînes, jeton présent ou non (aucun secret affiché)

Guide pas à pas : autopilot/publish/CONNECTER-UNE-CHAINE.md.

Ce que l'outil NE fait PAS : créer une chaîne ou un compte, saisir un mot de passe, activer la chaîne. Tu crées la chaîne dans YouTube,
tu cliques « Autoriser » dans ton navigateur (Google te demande lui-même ton mot de passe, jamais cet outil), puis tu passes `active` à `true`
dans le profil quand tu veux que la chaîne publie.

Sécurité : le jeton va dans autopilot/secrets/ (ignoré par git). Si le jeton donne accès à une chaîne DÉJÀ liée à un autre profil
(erreur classique : on a validé la mauvaise chaîne dans le sélecteur de Google), il est refusé et supprimé, pour ne jamais publier au mauvais endroit.
"""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (ICI, ICI.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import auth  # noqa: E402
import chaines  # noqa: E402
import common  # noqa: E402
import reglages  # noqa: E402
from erreurs import ErreurAuth, ErreurReseau  # noqa: E402
from quota import RegistreQuota  # noqa: E402
from youtube import YouTube  # noqa: E402


def chemin_liens() -> Path:
    """`state/chaines_youtube.json` : profil -> {id, titre} de la chaîne YouTube liée (informations publiques, pas des secrets)."""
    return common.STATE / "chaines_youtube.json"


def profil_connectable(ident: str) -> dict:
    p = chaines.profil(ident)
    if p is None:
        raise ErreurAuth(f"chaîne « {ident} » inconnue. Profils disponibles : {', '.join(chaines.charger_profils())}")
    if p["erreurs"] and not (p["active"] is False and all("sans voix propre" in e for e in p["erreurs"])):
        raise ErreurAuth(f"le profil {ident} est invalide : {' ; '.join(p['erreurs'])}")
    return p


def verifier(ident: str, yt: YouTube | None = None, afficher=print) -> dict:
    """Interroge YouTube avec le jeton de la chaîne, vérifie qu'elle n'est pas déjà liée à un autre profil, note le lien. Renvoie {id, titre}."""
    p = profil_connectable(ident)
    if yt is None:
        cfg = reglages.charger_chaine(p)
        yt = YouTube(auth.Jeton(chaine=ident), cfg, RegistreQuota(cfg).pour(ident))
    info = yt.ma_chaine()
    liens = common.read_json(chemin_liens(), {}) or {}
    for autre, lien in liens.items():
        if autre != ident and lien.get("id") == info["id"]:
            raise ErreurAuth(f"cette chaîne YouTube (« {info['titre']} ») est déjà liée au profil « {autre} » : "
                             "refais la connexion en choisissant la bonne chaîne dans la liste de Google")
    avant = liens.get(ident)
    if avant and avant.get("id") != info["id"]:
        afficher(f"ATTENTION : le profil {ident} pointait vers « {avant.get('titre')} », il pointe maintenant vers « {info['titre']} ».")
    liens[ident] = {"id": info["id"], "titre": info["titre"], "verifie": common.now()}
    common.write_json(chemin_liens(), liens)
    auth.noter_etat_auth("ok", chaine=ident)
    auth.ecrire_etat_jetons()
    return info


def connecter(ident: str, ouvrir_navigateur: bool = True, refaire: bool = False, afficher=print,
              autoriser=auth.autoriser, yt: YouTube | None = None) -> dict:
    """Flux complet. `autoriser` et `yt` sont remplaçables (tests). Lève ErreurAuth si la connexion échoue ou si la chaîne est déjà liée ailleurs."""
    p = profil_connectable(ident)
    jeton = auth.chemin_jeton(ident)
    existait = jeton.exists()
    if existait and not refaire:
        afficher(f"Un jeton existe déjà pour « {ident} » : vérification seulement (--refaire pour reprendre la connexion).")
        return verifier(ident, yt, afficher)
    ancien = jeton.read_bytes() if existait else None
    if not auth.chemin_client().exists():
        raise ErreurAuth("client_secret.json absent de autopilot/secrets/ : c'est le fichier du projet Google, le même pour toutes les chaînes (voir INSTALLATION.md)")
    afficher(f"Connexion de la chaîne « {p['nom']} » ({ident}). Dans la page Google : choisis le COMPTE puis la CHAÎNE « {p['nom']} » (compte de marque) avant d'autoriser.")
    autoriser(ouvrir_navigateur=ouvrir_navigateur, afficher=afficher, chaine=ident)
    try:
        return verifier(ident, yt, afficher)
    except (ErreurAuth, ErreurReseau):
        # jeton refusé ou chaîne déjà liée ailleurs : on ne garde pas un jeton dont on n'est pas sûr
        if ancien is not None:
            jeton.write_bytes(ancien)
        else:
            jeton.unlink(missing_ok=True)
        auth.ecrire_etat_jetons()
        raise


def liste() -> list[dict]:
    etat = auth.ecrire_etat_jetons()
    liens = common.read_json(chemin_liens(), {}) or {}
    return [{"chaine": i, "nom": p["nom"], "active": bool(p["active"]), "jeton": etat[i]["connecte"],
             "chaine_youtube": (liens.get(i) or {}).get("titre")} for i, p in chaines.charger_profils().items()]


def main(argv: list[str]) -> int:
    try:
        if "--liste" in argv:
            for c in liste():
                print(f"{c['chaine']:<16}{'active  ' if c['active'] else 'inactive'}  jeton : {'oui' if c['jeton'] else 'non'}  {c['chaine_youtube'] or ''}")
            return 0
        ids = [a for a in argv if not a.startswith("--")]
        if len(ids) != 1:
            print(__doc__)
            return 2
        ident = ids[0]
        if "--verifier" in argv:
            info = verifier(ident)
        else:
            info = connecter(ident, ouvrir_navigateur="--sans-navigateur" not in argv, refaire="--refaire" in argv)
        print(f"OK : la chaîne « {ident} » est reliée à la chaîne YouTube « {info['titre']} » ({info['id']}).")
        if not chaines.profil(ident)["active"]:
            print(f"Elle est encore inactive : quand tu es prêt, passe \"active\": true dans autopilot/chaines/{ident}.json.")
        return 0
    except (ErreurAuth, ErreurReseau) as e:
        print(f"ÉCHEC : {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
