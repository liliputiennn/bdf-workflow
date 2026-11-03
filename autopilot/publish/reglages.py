"""Réglages du publieur : valeurs par défaut fusionnées avec `config.json`."""
import copy
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent

DEFAUTS = {
    "heure_publication": "18:00",
    "fuseau": "Europe/Paris",
    "marge_minimale_minutes": 30,
    "categorie_id": "27",
    "langue": "fr",
    "max_envois_par_execution": 2,
    "chunk_octets": 8 * 1024 * 1024,
    "titre_max": 70,
    "description_max_octets": 5000,
    "tags_max_caracteres": 500,
    "miniature_max_octets": 2 * 1024 * 1024,
    "hashtag_shorts": True,
    "question_dans_description": True,
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
