"""Compte les épisodes qui attendent encore une fabrication (écrit, voix, rendu) : sert à enchaîner les fabrications de nuit.

Usage : python autopilot/cloud/restant.py      (affiche un nombre)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

print(sum(1 for e in common.list_episodes() if common.get_status(e)["etat"] in ("ecrit", "voix", "rendu")))
