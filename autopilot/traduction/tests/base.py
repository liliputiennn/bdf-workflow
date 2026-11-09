"""Socle commun des tests de la traduction : dossier temporaire (BDF_ROOT), profils fr/en, un épisode source français, une adaptation anglaise de référence.

Aucun réseau, aucune voix, aucun GPU, aucune publication. Le « moteur » de repli est un faux dictionnaire.
Lancer :  python -m unittest discover -s autopilot/traduction/tests      (depuis pixel-faits/)
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
TMP = Path(tempfile.mkdtemp(prefix="bdf-trad-"))
os.environ["BDF_ROOT"] = str(TMP)
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "autopilot"))

from autopilot import chaines, common, langues  # noqa: E402
from autopilot.traduction import adaptation, controle, file as file_, parite, traduire  # noqa: E402
from autopilot.writer import valider  # noqa: E402

assert common.ROOT == TMP.resolve(), "BDF_ROOT n'est pas pris en compte"

SRC = "10-business-test-s2"
FR_PHRASES = [
    "Une idée : aider les petits artisans à répondre aux marchés publics.",
    "Une mairie cherche un peintre ou un jardinier, et doit publier son besoin.",
    "Un petit artisan n'ose pas toujours répondre, car les dossiers font peur.",
    "Toi, tu surveilles les annonces et tu prépares le dossier avec lui.",
    "Le BOAMP et le portail de l'État listent toutes les offres.",
    "Même une micro-entreprise peut répondre à un marché public.",
    "Pour candidater, il existe le DUME, un formulaire européen en ligne.",
    "Pour certains marchés, le numéro SIRET suffit pour candidater.",
]
EN_PHRASES = [
    "An idea: help small craftsmen answer public tenders in France.",
    "A town hall needs a painter or a gardener, and it must publish that need.",
    "A small craftsman does not always dare to answer, because the paperwork looks scary.",
    "You watch the announcements and you build the file together with them.",
    "The BOAMP and the state portal list all the offers.",
    "Even a micro business can answer a public tender in France.",
    "To apply there is the DUME, a European online form.",
    "For some tenders, the SIRET company number is enough to apply.",
]
SOURCE_EP = {
    "id": SRC, "titre": "Marchés publics : une micro-entreprise peut-elle répondre ?", "theme": "chocolat-lait", "chaine": "Bureau des Faits",
    "theme_accent": "chocolat-caramel",
    "miniature": {"style": "createur", "texte_haut": "MARCHÉS PUBLICS PETITS ARTISANS", "gros": "12 500 €", "icone": "pieces"},
    "phrases": FR_PHRASES,
    "scenes": [
        {"type": "titre-geant", "phrase": 1, "params": {"accents": ["petits", "artisans"]}},
        {"type": "liste", "phrase": 5, "params": {"titre": "TES OUTILS", "items": [{"texte": "BOAMP"}, {"texte": "Portail des marchés publics"}, {"texte": "DUME (formulaire en ligne)"}]}},
        {"type": "chiffre", "phrase": 7, "params": {"valeur": 12500, "suffixe": " €", "etiquette": "coût moyen d'un dossier", "sous": "en 2024"}},
    ],
}
SOURCE_FAITS = [{
    "claim": "Une micro-entreprise peut répondre à un marché public ; la candidature passe par le DUME.", "valeur": "DUME", "phrase": 6,
    "sources": ["https://entreprendre.service-public.gouv.fr/vosdroits/F32144", "https://www.economie.gouv.fr/guide-marches-publics"],
    "check": ["DUME"], "verified": ["https://entreprendre.service-public.gouv.fr/vosdroits/F32144"],
}]
SOURCE_PUB = {
    "titre": "Marchés publics : une micro-entreprise peut-elle répondre ?",
    "description": "Marchés publics : une micro-entreprise peut-elle répondre ? Un tour des outils gratuits pour aider les petits artisans.\n\n#MarchésPublics #Artisans",
    "tags": ["marchés publics", "micro-entreprise", "artisans", "outils gratuits"],
    "question_commentaires": "Quel thème veux-tu ensuite : cuisine, maison, argent ou voyage ?", "langue": "fr", "contenu_ia": True,
}

DICO = {
    **dict(zip(FR_PHRASES, EN_PHRASES)),
    SOURCE_EP["titre"]: "Public tenders: can a tiny business bid?",
    "TES OUTILS": "YOUR TOOLS", "BOAMP": "BOAMP", "Portail des marchés publics": "Public procurement portal", "DUME (formulaire en ligne)": "DUME (online form)",
    "coût moyen d'un dossier": "average cost of an application", "en 2024": "in 2024",
    "MARCHÉS PUBLICS PETITS ARTISANS": "PUBLIC TENDERS FOR SMALL CRAFTSMEN",
    SOURCE_FAITS[0]["claim"]: "A micro business can answer a public tender; the application goes through the DUME form.",
    "DUME": "DUME",
    SOURCE_PUB["description"].split("\n")[0]: "Public tenders: can a tiny business bid? A tour of the free tools that help small craftsmen win their first contract in France.",
    "marchés publics": "public tenders", "micro-entreprise": "micro business", "artisans": "craftsmen", "outils gratuits": "free tools",
    SOURCE_PUB["question_commentaires"]: "Which theme do you want next: cooking, home, money or travel?",
}


class FauxMoteur:
    """Traducteur à dictionnaire : déterministe, sans modèle. `casser` = textes pour lesquels il plante (test d'isolation)."""
    nom = "faux"

    def __init__(self, dico=None, casser=()):
        self.dico, self.casser, self.appels = dico or DICO, set(casser), 0

    def __call__(self, textes):
        self.appels += 1
        for t in textes:
            if t in self.casser:
                raise RuntimeError("moteur en panne")
        return [self.dico[t] for t in textes]


class Base(unittest.TestCase):
    def setUp(self):
        for d in ("episodes-b", "autopilot/state", "autopilot/chaines", "autopilot/voix"):
            shutil.rmtree(TMP / d, ignore_errors=True)
        (TMP / "episodes-b").mkdir(parents=True)
        (TMP / "autopilot" / "state").mkdir(parents=True)
        self.profil("fr", active=True, langue="fr")
        self.profil("en", langue="en", preparation=True, voix={"dossier": "voix/en"},
                    source={"chaine": "fr", "mode": "traduction", "cible_jours_de_stock": 4, "decalage_heures": 48, "attente_claude_heures": 36, "max_par_passage": 3},
                    frequence={"shorts_par_jour": 2, "longs_par_semaine": 3}, nom="Business Facts (EN)")
        self.ecrire("autopilot/voix/en/voix.json", {"locuteur": "Ryan", "style": "steady", "vitesse": 1.0})
        self.source()

    def ecrire(self, rel, contenu):
        p = TMP / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")

    def profil(self, ident, **extra):
        base = {"id": ident, "nom": ident.upper(), "langue": "fr", "format": "business", "jeton_fichier": "token.json" if ident == "fr" else f"token-{ident}.json"}
        self.ecrire(f"autopilot/chaines/{ident}.json", {**base, **extra})

    def source(self, ident=SRC, etat="pret", **statut):
        d = f"episodes-b/{ident}"
        self.ecrire(f"{d}/episode.json", {**copy.deepcopy(SOURCE_EP), "id": ident})
        self.ecrire(f"{d}/faits.json", copy.deepcopy(SOURCE_FAITS))
        self.ecrire(f"{d}/publication.json", copy.deepcopy(SOURCE_PUB))
        self.ecrire(f"{d}/status.json", {"etat": etat, "maj": "2026-11-05T10:00:00", "raison": None, "tentatives": 0, "chaine_id": "fr",
                                         "youtube": {"video_id": None, "url": None, "visibilite": None, "publie_a": None}, **statut})

    def en(self):
        return chaines.charger_profils()["en"]

    def brouillon(self, ident, ep=None, faits=None, pub=None):
        """Écrit l'adaptation de référence (celle d'un bon passage de Claude) dans _brouillons/<ident>/, modifiable avant validation."""
        faits_en = adaptation.adapter_faits(copy.deepcopy(SOURCE_FAITS), FauxMoteur(), "en")
        ep_en = adaptation.adapter_episode(copy.deepcopy(SOURCE_EP), FauxMoteur(), "en", "Business Facts", ident)
        pub_en = adaptation.adapter_publication(copy.deepcopy(SOURCE_PUB), FauxMoteur(), "en", "en")
        d = f"episodes-b/_brouillons/{ident}"
        self.ecrire(f"{d}/episode.json", ep if ep is not None else ep_en)
        self.ecrire(f"{d}/faits.json", faits if faits is not None else faits_en)
        self.ecrire(f"{d}/publication.json", pub if pub is not None else pub_en)
        return ep_en, faits_en, pub_en

    def lire(self, rel):
        return json.loads((TMP / rel).read_text(encoding="utf-8"))
