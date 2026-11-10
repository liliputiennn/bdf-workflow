"""Réglages du publieur : valeurs par défaut fusionnées avec `config.json`."""
import copy
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent

DEFAUTS = {
    "heure_publication": "18:00",    # repli : une seule heure, si `heures_shorts` est vide
    "heures_shorts": ["07:30", "12:00", "16:00", "18:30", "21:00"],  # créneaux de mise en ligne des Shorts (heure locale du fuseau)
    "shorts_par_creneau": 2,         # 5 créneaux x 2 = 10 Shorts par jour (limité en pratique par le stock)
    "ecart_creneau_minutes": 15,     # écart entre deux Shorts du même créneau (08:00 et 08:15)
    "heure_long": "17:00",           # heure de mise en ligne d'un long, les `jours_longs`
    "fuseau": "Europe/Paris",
    "marge_minimale_minutes": 30,
    "categorie_id": "27",
    "langue": "fr",
    "max_envois_par_execution": 15,   # 2 passages par jour x 15 = 30 envois possibles pour 10 Shorts + 1 long par jour (le plafond YouTube est de 100 envois par jour)
    "rapprochements_max": 40,        # vidéos déjà programmées dont on avance la date par passage (videos.update : 50 unités chacune)
    "chunk_octets": 8 * 1024 * 1024,
    "titre_max": 70,
    "description_max_octets": 5000,
    "tags_max_caracteres": 500,
    "miniature_max_octets": 2 * 1024 * 1024,
    "jours_longs": [0, 1, 2, 3, 4, 5, 6],  # jours de la semaine où part un long (0 = lundi) : tous les jours tant qu'il y a du stock ; les Shorts partent aussi tous les jours
    "hashtag_shorts": True,
    "hashtags_max": 15,              # au-delà de 15 hashtags, YouTube les ignore tous
    "hashtags_cible": 12,            # on complète la description jusqu'à ce nombre (une dizaine), jamais plus de `hashtags_max`
    "hashtags_chaine": ["#LaDébrouille", "#Business", "#Argent", "#GagnerDeLArgent", "#IdéesBusiness", "#RevenusComplémentaires"],  # thèmes de la chaîne, utilisés pour compléter
    "mots_cles_dans_description": True,  # ajoute un bloc « Mots-clés : … » (tags du rédacteur) s'il manque
    "badge_ia_youtube": False,       # True = coche aussi l'option « contenu modifié ou synthétique » de YouTube (badge IA sur la vidéo)
    "mention_ia_description": False, # ajoute une ligne « voix de synthèse » à la description quand publication.json a contenu_ia: true
    "question_dans_description": True,
    "commentaire_auto": True,        # poste sous chaque long le commentaire du cadeau (messages à copier, suite, abonnement) dès que la vidéo est publique ; YouTube ne permet pas de l'épingler par programme
    "pour_enfants": False,           # True = déclare la vidéo « conçue pour les enfants » (selfDeclaredMadeForKids) ; réservé à la chaîne de musique enfantine
    "tentatives_max_avant_quarantaine": 6,
    "reseau": {"tentatives_max": 8, "attente_initiale_s": 2.0, "attente_max_s": 120.0, "timeout_s": 120.0},
    "quota": {
        "plafond_unites": 10000,
        "plafond_envois": 100,
        "cout_envoi_unites": 0,
        "cout_envoi_compteur": 1,
        "cout_miniature": 50,
        "cout_lecture": 1,
        "cout_mise_a_jour": 50,
        "cout_commentaire": 50,
    },
    "urls": {
        "api": "https://www.googleapis.com/youtube/v3",
        "upload": "https://www.googleapis.com/upload/youtube/v3",
    },
}


def _fusion(base: dict, sur: dict) -> dict:
    for cle, val in sur.items():
        if isinstance(val, dict) and isinstance(base.get(cle), dict):
            _fusion(base[cle], val)
        else:
            base[cle] = val
    return base


def charger_chaine(profil: dict, chemin: Path | None = None, surcharge: dict | None = None) -> dict:
    """Réglages d'une chaîne : ceux du projet (config.json) + les surcharges de son profil (`publication`) + sa langue.
    Le quota, les adresses d'API et les limites YouTube restent communs. Une chaîne autre que la chaîne par défaut ne reprend pas
    les hashtags de la chaîne par défaut (ils lui sont propres) tant que son profil n'en donne pas."""
    cfg = copy.deepcopy(charger(chemin, surcharge))
    dessus = dict(profil.get("publication") or {})
    dessus.setdefault("langue", profil.get("langue", cfg["langue"]))
    if profil.get("id") != "fr" and "hashtags_chaine" not in dessus:
        dessus["hashtags_chaine"] = []
    _fusion(cfg, dessus)
    if surcharge:  # les surcharges explicites (tests, essais) passent encore devant le profil
        _fusion(cfg, surcharge)
    return cfg


def charger(chemin: Path | None = None, surcharge: dict | None = None) -> dict:
    cfg = copy.deepcopy(DEFAUTS)
    chemin = chemin or ICI / "config.json"
    try:
        _fusion(cfg, json.loads(chemin.read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    if surcharge:
        _fusion(cfg, surcharge)
    return cfg
