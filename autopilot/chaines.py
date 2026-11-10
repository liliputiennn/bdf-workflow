"""Profils de chaîne : le moteur qui fait tourner plusieurs chaînes YouTube avec le même pipeline.

Un profil = un fichier `autopilot/chaines/<id>.json` (voir docs/superpowers/specs/2026-11-08-moteur-chaines-design.md).
Chaque épisode appartient à UNE chaîne : `episodes-b/<id>/status.json` porte `chaine_id` ; sans ce champ, l'épisode est
rattaché à la chaîne par défaut (`fr`), ce qui garde tous les épisodes existants valides sans migration obligatoire.

Ce module ne lit JAMAIS `autopilot/secrets/` : il ne connaît que le NOM du fichier de jeton (`jeton_fichier`).
Seul `autopilot/publish/` ouvre ces fichiers.

    python autopilot/chaines.py liste              # les chaînes, actives ou non
    python autopilot/chaines.py valider            # contrôle de tous les profils (code 1 s'il y a une erreur)
    python autopilot/chaines.py migrer [--dry-run] # rattache les épisodes existants à la chaîne par défaut (ajoute `chaine_id`, rien d'autre)

Bibliothèque standard seulement.
"""
import copy
import importlib
import json
import re
import sys
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

CHAINE_DEFAUT = common.CHAINE_DEFAUT
FORMATS = ("faits", "business", "histoire", "sommeil", "langues", "quiz", "musique_enfants", "meditation", "histoires_enfants", "finance", "asmr")
ID_VALIDE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
FICHIER_JETON_VALIDE = re.compile(r"^[A-Za-z0-9][\w.-]*\.json$")
# Réglages de publication qu'une chaîne peut surcharger. Le quota, les adresses d'API et les limites de YouTube restent communs.
REGLAGES_PUBLICATION = {
    "heures_shorts": list, "shorts_par_creneau": int, "ecart_creneau_minutes": int, "heure_long": str, "heure_publication": str,
    "jours_longs": list, "fuseau": str, "categorie_id": str, "langue": str, "max_envois_par_execution": int,
    "hashtags_chaine": list, "hashtag_shorts": bool, "hashtags_max": int, "hashtags_cible": int,
    "question_dans_description": bool, "mention_ia_description": bool, "commentaire_auto": bool,
    "mots_cles_dans_description": bool, "badge_ia_youtube": bool, "marge_minimale_minutes": int, "pour_enfants": bool,
}
# Crochets qu'un module de format de contenu (chantier 3) peut définir ; tous facultatifs.
MODES_SOURCE = ("traduction", "doublage")
OPTIONS_SOURCE = ("cible_jours_de_stock", "decalage_heures", "attente_claude_heures", "max_par_passage")
HOOKS_FORMAT = ("consignes", "sujets", "valider_episode", "brique_fabrique", "brique_miniature")

DEFAUT_PROFIL = {
    "id": "", "nom": "", "langue": "fr", "format": "faits", "niche": "", "active": False,
    "preparation": False,            # chantier 2 : fabrique du stock (voix, rendu, miniature) SANS publier ; seule `active` autorise la publication
    "vague": 1,                      # vague d'activation prévue (1 = la première)
    "jeton_fichier": None,           # NOM d'un fichier de `autopilot/secrets/` (jamais lu hors de publish/)
    "voix": {"dossier": None},       # dossier sous autopilot/ avec ref.wav, ref.txt (et chaine-nettoyage.txt) ; None = voix du projet
    "musique": {"dossier": None},    # dossier de pistes sous autopilot/ ; None = musique du projet
    "style": {"theme": None, "miniature": None},
    "publication": {},               # surcharges de publish/config.json (REGLAGES_PUBLICATION)
    "frequence": {},                 # {"shorts_par_jour", "longs_par_semaine"} ; sinon déduit de la publication
    "dossiers": {"sujets": None},    # banque de sujets propre (défaut : subjects/ pour la chaîne par défaut, subjects/<id>/ sinon)
    "source": None,                  # chantier 2 : {"chaine": "fr", "mode": "traduction"|"doublage", "cible_jours_de_stock": 4, "decalage_heures": 48,
                                     #               "attente_claude_heures": 36, "max_par_passage": 3} = cette chaîne reprend une autre
    "format_module": None,           # chantier 3 : module Python (ex. « autopilot.formats.histoire ») qui définit des HOOKS_FORMAT
    "format_options": {},
    "format_pret": False,            # le format de contenu est-il fabriqué de bout en bout ? (alimente la feuille de route)
    "tiktok": None,                  # le compte TikTok (un seul) reçoit-il les Shorts de cette chaîne ? None = seulement la chaîne par défaut
    "briques": {"fabrique": None, "miniature": None},  # scripts de remplacement, chemins relatifs à autopilot/
    "notes": "",
}


# ---------------------------------------------------------------- chemins (lus à l'appel : BDF_ROOT, tests)
def dossier_profils() -> Path:
    return common.ROOT / "autopilot" / "chaines"


def dossier_autopilot() -> Path:
    return common.ROOT / "autopilot"


# ---------------------------------------------------------------- profils
def defaut_fr() -> dict:
    """Profil de repli : la chaîne actuelle, telle qu'elle tourne depuis toujours (aucun fichier de profil requis)."""
    p = copy.deepcopy(DEFAUT_PROFIL)
    p.update(id=CHAINE_DEFAUT, nom="La Débrouille", langue="fr", format="business", niche="Faits et business", active=True,
             jeton_fichier="token.json", format_pret=True)
    p["dossiers"]["sujets"] = "subjects"
    return p


def _fusion(base: dict, sur: dict) -> dict:
    for cle, val in sur.items():
        if isinstance(val, dict) and isinstance(base.get(cle), dict):
            _fusion(base[cle], val)
        else:
            base[cle] = val
    return base


def normaliser(brut: dict, ident: str | None = None) -> dict:
    p = _fusion(copy.deepcopy(DEFAUT_PROFIL), brut if isinstance(brut, dict) else {})
    if ident and not p.get("id"):
        p["id"] = ident
    if not p["nom"]:
        p["nom"] = p["id"]
    if not p["dossiers"].get("sujets"):
        p["dossiers"]["sujets"] = "subjects" if p["id"] == CHAINE_DEFAUT else f"subjects/{p['id']}"
    if p["jeton_fichier"] is None:
        p["jeton_fichier"] = "token.json" if p["id"] == CHAINE_DEFAUT else f"token-{p['id']}.json"
    return p


def _chemin_sur(d) -> bool:
    """Chemin relatif à autopilot/, sans « .. » ni racine (sous Windows comme ailleurs)."""
    return (isinstance(d, str) and d != "" and ".." not in d.replace("\\", "/").split("/")
            and not d.startswith(("/", "\\")) and not Path(d).is_absolute() and not PureWindowsPath(d).is_absolute())


def valider_profil(p: dict, tous_ids: set | None = None) -> list[str]:
    """Liste des défauts du profil (vide = bon). Un profil invalide n'est jamais activé par le moteur."""
    e: list[str] = []
    if not ID_VALIDE.match(str(p.get("id", ""))):
        e.append("identifiant invalide (minuscules, chiffres et tirets, 31 caractères au plus)")
    if not re.match(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$", str(p.get("langue", ""))):
        e.append(f"langue « {p.get('langue')} » invalide (code comme fr, en, es)")
    if p.get("format") not in FORMATS:
        e.append(f"format « {p.get('format')} » inconnu (attendu : {', '.join(FORMATS)})")
    jeton = p.get("jeton_fichier")
    if not isinstance(jeton, str) or not FICHIER_JETON_VALIDE.match(jeton) or jeton in ("client_secret.json", "tiktok_token.json", "tiktok_client.json"):
        e.append("jeton_fichier doit être un nom de fichier .json simple, propre à la chaîne")
    if tous_ids is not None:
        autres = [i for i in tous_ids if i != p.get("id")]
        src = p.get("source")
        if src is not None:
            if not isinstance(src, dict) or src.get("chaine") not in autres:
                e.append("source : doit nommer une AUTRE chaîne existante ({\"chaine\": \"fr\", \"mode\": ...})")
            else:
                if src.get("mode", "traduction") not in MODES_SOURCE:
                    e.append(f"source.mode « {src.get('mode')} » inconnu (attendu : {', '.join(MODES_SOURCE)})")
                for cle in OPTIONS_SOURCE:
                    v = src.get(cle)
                    if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0):
                        e.append(f"source.{cle} : nombre positif attendu")
    tt = p.get("tiktok")
    if tt is not None and not isinstance(tt, (bool, dict)):
        e.append("tiktok : true, false ou un objet attendu")
    elif isinstance(tt, dict):
        for cle, valeur in tt.items():
            ok = {"actif": isinstance(valeur, bool), "audit_confirme": isinstance(valeur, bool), "ia": isinstance(valeur, bool),
                  "mode": valeur in ("boite", "direct"),
                  "visibilite": valeur in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"),
                  "max_par_24h": isinstance(valeur, int) and not isinstance(valeur, bool) and 1 <= valeur <= 15,
                  "moteur": valeur in ("boite", "planificateur"),
                  "planificateur": isinstance(valeur, dict) and set(valeur) <= {"service", "profil", "cle_fichier", "compte", "consentement"}
                                   and valeur.get("service", "upload-post") in ("upload-post", "zernio")
                                   and isinstance(valeur.get("consentement", False), bool),
                  "hashtags": isinstance(valeur, list) and all(isinstance(h, str) for h in valeur),
                  "creneaux": isinstance(valeur, list) and bool(valeur) and all(isinstance(h, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", h) for h in valeur),
                  "jeton_fichier": isinstance(valeur, str) and bool(FICHIER_JETON_VALIDE.match(valeur)) and valeur not in ("client_secret.json", "tiktok_client.json"),
                  }.get(cle)
            if ok is None:
                e.append(f"tiktok.{cle} : réglage inconnu")
            elif not ok:
                e.append(f"tiktok.{cle} : valeur invalide")
    if not isinstance(p.get("preparation", False), bool):
        e.append("preparation : true ou false attendu")
    for cle, valeur in (p.get("publication") or {}).items():
        if cle not in REGLAGES_PUBLICATION:
            e.append(f"publication.{cle} : réglage non surchargeable par une chaîne")
        elif not isinstance(valeur, REGLAGES_PUBLICATION[cle]) or (REGLAGES_PUBLICATION[cle] is int and isinstance(valeur, bool)):
            e.append(f"publication.{cle} : type invalide")
    for cle in ("voix", "musique"):
        d = (p.get(cle) or {}).get("dossier")
        if d is not None and not _chemin_sur(d):
            e.append(f"{cle}.dossier : chemin relatif à autopilot/ sans « .. » attendu")
    for nom, chemin in (p.get("briques") or {}).items():
        if chemin is not None and not _chemin_sur(chemin):
            e.append(f"briques.{nom} : chemin relatif à autopilot/ sans « .. » attendu")
    if (p.get("active") or p.get("preparation")) and p.get("langue") != "fr" and not (p.get("voix") or {}).get("dossier"):
        e.append("chaîne active ou en préparation dans une autre langue que le français sans voix propre (voix.dossier) : elle parlerait avec la voix française")
    return e


def charger_profils() -> dict[str, dict]:
    """Tous les profils {id: profil}. Sans dossier `autopilot/chaines/`, seule la chaîne par défaut existe (comportement historique)."""
    profils: dict[str, dict] = {}
    d = dossier_profils()
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            if f.name.startswith("_"):
                continue
            brut = common.read_json(f, None)
            if not isinstance(brut, dict):
                continue
            p = normaliser(brut, f.stem)
            if p["id"] != f.stem:
                p["erreur_nom"] = True  # le fichier doit porter l'identifiant
            profils[p["id"]] = p
    if CHAINE_DEFAUT not in profils:
        profils[CHAINE_DEFAUT] = defaut_fr()
    profils = dict(sorted(profils.items(), key=lambda kv: (kv[1]["vague"] if isinstance(kv[1]["vague"], int) else 99, kv[0])))  # ordre d'activation
    ids = set(profils)
    for p in profils.values():
        p["erreurs"] = valider_profil(p, ids) + (["le nom du fichier doit être <id>.json"] if p.get("erreur_nom") else [])
        p["valide"] = not p["erreurs"]
    return profils


def profil(ident: str) -> dict | None:
    return charger_profils().get(ident)


def preparees(profils: dict | None = None) -> list[dict]:
    """Chaînes dont on FABRIQUE les épisodes : les actives et celles en préparation (stock constitué sans publier). Le publieur, lui, ne lit que `actives`."""
    return [p for p in (profils or charger_profils()).values() if (p.get("active") or p.get("preparation")) and p.get("valide")]


def est_active(ident: str, profils: dict | None = None) -> bool:
    p = (profils or charger_profils()).get(ident)
    return bool(p and p.get("active") and p.get("valide"))


def actives(profils: dict | None = None) -> list[dict]:
    return [p for p in (profils or charger_profils()).values() if p.get("active") and p.get("valide")]


# ---------------------------------------------------------------- appartenance d'un épisode
def chaine_de(ep_id: str) -> str:
    """Chaîne d'un épisode : `chaine_id` de son status.json, sinon la chaîne par défaut (épisodes antérieurs aux profils)."""
    return common.chaine_de(ep_id)


def rattacher(ep_id: str, chaine: str) -> None:
    """Marque un épisode comme appartenant à `chaine` (sans toucher à son état)."""
    st = common.get_status(ep_id)
    if st.get("chaine_id") != chaine:
        common.set_status(ep_id, st["etat"], st.get("raison"), chaine_id=chaine)


def migrer(dry_run: bool = False) -> dict:
    """Ajoute `chaine_id` (chaîne par défaut) aux status.json qui n'en ont pas. N'efface ni ne modifie rien d'autre ; idempotent."""
    rattaches, deja = [], 0
    for d in sorted(common.EPISODES.glob("*")):
        f = d / "status.json"
        if not d.is_dir() or d.name.startswith("_") or not f.exists():
            continue
        st = common.read_json(f, None)
        if not isinstance(st, dict):
            continue
        if st.get("chaine_id"):
            deja += 1
            continue
        rattaches.append(d.name)
        if not dry_run:
            st["chaine_id"] = CHAINE_DEFAUT
            common.write_json(f, st)
    return {"rattaches": rattaches, "deja_rattaches": deja, "dry_run": dry_run}


# ---------------------------------------------------------------- ce que le pipeline donne aux briques
def env_briques(p: dict) -> dict:
    """Variables d'environnement transmises aux briques d'une chaîne : voix et musique propres si le profil les déclare."""
    env = {"BDF_CHAINE": p["id"], "BDF_LANGUE": p["langue"]}
    base = dossier_autopilot()
    v = (p.get("voix") or {}).get("dossier")
    if v:
        for cle, nom in (("BDF_REF_WAV", "ref.wav"), ("BDF_REF_TXT", "ref.txt"), ("BDF_CHAIN", "chaine-nettoyage.txt")):
            if (base / v / nom).exists():
                env[cle] = str(base / v / nom)
        info = voix_info(p)
        if info["mode"] == "integree":  # voix intégrée de Qwen3-TTS CustomVoice : pas de clonage, pas de fichier de référence
            env["BDF_LOCUTEUR"] = info["locuteur"]
            if info.get("style"):
                env["BDF_STYLE"] = info["style"]
        if info.get("vitesse"):
            env["BDF_VITESSE"] = str(info["vitesse"])
    m = (p.get("musique") or {}).get("dossier")
    if m and (base / m).is_dir():
        env["BDF_MUSIQUE"] = str(base / m)
    return env


def voix_info(p: dict) -> dict:
    """Voix de la chaîne : {"mode": "clone"|"integree"|"projet"|None, "disponible": bool, "locuteur", "style", "vitesse", "langue"}.
    - clone : `ref.wav` + `ref.txt` dans le dossier de voix (voix de référence de l'utilisateur) — prioritaire ;
    - integree : `voix.json` = {"locuteur": "Ryan", "style": "...", "vitesse": 1.0} (voix intégrée de Qwen3-TTS CustomVoice, Apache-2.0) ;
    - projet : pas de dossier de voix (chaîne française historique : la voix du projet) ;
    - None : un dossier est déclaré mais ne contient rien d'utilisable (la chaîne ne peut pas encore parler)."""
    v = (p.get("voix") or {}).get("dossier")
    if not v:
        return {"mode": "projet", "disponible": p.get("langue") == "fr", "locuteur": None, "style": None, "vitesse": None, "langue": p.get("langue")}
    d = dossier_autopilot() / v
    cfg = common.read_json(d / "voix.json", None)
    cfg = cfg if isinstance(cfg, dict) else {}
    vitesse = cfg.get("vitesse")
    base = {"locuteur": None, "style": None, "vitesse": vitesse if isinstance(vitesse, (int, float)) and not isinstance(vitesse, bool) else None, "langue": p.get("langue")}
    if (d / "ref.wav").exists() and (d / "ref.txt").exists():
        return {**base, "mode": "clone", "disponible": True}
    if isinstance(cfg.get("locuteur"), str) and cfg["locuteur"].strip():
        return {**base, "mode": "integree", "disponible": True, "locuteur": cfg["locuteur"].strip(),
                "style": cfg.get("style") if isinstance(cfg.get("style"), str) else None}
    return {**base, "mode": None, "disponible": False}


def brique(p: dict, nom: str, defaut: Path) -> Path:
    """Script d'une étape pour cette chaîne : le remplaçant déclaré dans `briques` (chantier 3), sinon le script standard."""
    chemin = (p.get("briques") or {}).get(nom)
    if not chemin:
        return defaut
    base = dossier_autopilot().resolve()
    cible = (base / chemin).resolve()
    try:
        cible.relative_to(base)
    except ValueError:
        return defaut  # jamais en dehors de autopilot/
    return cible


def charger_format(p: dict):
    """Module de format de contenu déclaré par le profil (ou None). Une erreur d'import n'arrête rien : la chaîne reste sur le pipeline standard."""
    nom = p.get("format_module")
    if not nom:
        return None
    try:
        return importlib.import_module(nom)
    except Exception:
        return None


def appeler_hook(p: dict, nom: str, *args, defaut=None, sur_erreur=None, options: dict | None = None):
    """Appelle le crochet `nom` (un de HOOKS_FORMAT) du module de format du profil. `defaut` : pas de module ou crochet absent ;
    `sur_erreur` (sinon `defaut`) : le crochet a levé une exception (jamais propagée : une chaîne ne casse pas les autres).
    `options` : arguments nommés transmis SEULEMENT si le crochet les déclare (ex. `reseau` pour vérifier les sources en ligne)."""
    if nom not in HOOKS_FORMAT:
        raise ValueError(f"crochet inconnu : {nom} ({', '.join(HOOKS_FORMAT)})")
    module = charger_format(p)
    fonction = getattr(module, nom, None) if module else None
    if not callable(fonction):
        return defaut
    try:
        kw = {}
        if options:
            import inspect
            params = inspect.signature(fonction).parameters
            kw = {k: v for k, v in options.items() if k in params}
        return fonction(*args, **kw)
    except Exception:
        return defaut if sur_erreur is None else sur_erreur


def frequence(p: dict, shorts_defaut: int = 8, longs_defaut: int = 3) -> tuple[int, int]:
    """(Shorts par jour, longs par semaine) voulus pour la chaîne : `frequence` du profil, sinon déduit de ses créneaux de publication,
    sinon les valeurs par défaut de l'appelant (la cadence historique de la chaîne française)."""
    f, pub = p.get("frequence") or {}, p.get("publication") or {}
    shorts = f.get("shorts_par_jour")
    if shorts is None:
        shorts = len(pub["heures_shorts"]) * pub.get("shorts_par_creneau", 1) if "heures_shorts" in pub else shorts_defaut
    longs = f.get("longs_par_semaine")
    if longs is None:
        longs = len(pub["jours_longs"]) if "jours_longs" in pub else longs_defaut
    return int(shorts), int(longs)


def fichier_etat_auth(ident: str) -> str:
    """Nom (dans autopilot/state/) du fichier d'état de connexion YouTube de la chaîne. Ne contient aucun secret."""
    return "youtube_auth.json" if ident == CHAINE_DEFAUT else f"youtube_auth-{ident}.json"


def dossier_sujets(p: dict) -> Path:
    return common.ROOT / p["dossiers"]["sujets"]


# ---------------------------------------------------------------- ligne de commande
def _main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "liste"
    profils = charger_profils()
    if cmd == "liste":
        for p in profils.values():
            marque = "ACTIVE  " if p["active"] and p["valide"] else "inactive"
            print(f"{p['id']:<10} {marque} {p['langue']:<3} {p['format']:<16} {p['nom']}")
        return 0
    if cmd == "valider":
        bad = 0
        for p in profils.values():
            for err in p["erreurs"]:
                print(f"{p['id']} : {err}")
                bad += 1
        print("profils valides" if not bad else f"{bad} défaut(s)")
        return 1 if bad else 0
    if cmd == "migrer":
        print(json.dumps(migrer("--dry-run" in argv), ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
