"""Épisode long de démonstration SANS voix réelle : textes, timings plausibles et audio synthétique (tons) dans episodes-b/_demo-long/.

Usage :  python autopilot/long/make_demo.py [dossier]
Le dossier `_demo-long` commence par « _ » : les listes d'épisodes de l'orchestrateur l'ignorent.
"""
import array
import math
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import common  # noqa: E402
import longlib as L  # noqa: E402

SR = 48000
MOTS_PAR_S = 3.0
GAP, LEAD = 0.18, 0.15  # mêmes valeurs que voice.py


def S(type_, phrase, **params):
    return {"type": type_, "phrase": phrase, "params": params}


DEMO = {
    "id": "_demo-long",
    "titre": "Comment Costco gagne de l'argent (démo du format long)",
    "theme": "papier-vert",
    "chaine": "Bureau des Faits",
    "pause_chapitre_s": 2.0,
    "chapitres": [
        {
            "titre": "Le paradoxe de la marge",
            "phrases": [
                "Costco gagne très peu sur ce qu'il vend.",
                "Alors, comment fait-il de l'argent ?",
                "Premier indice : sa marge est plafonnée à quatorze pour cent.",
                "Même si les clients accepteraient de payer plus.",
                "Beaucoup d'enseignes visent une marge bien plus haute.",
                "Ce plafond, c'est une règle que Costco s'impose.",
                "Donc le profit se cache ailleurs.",
                "Suivons l'argent, chapitre après chapitre.",
            ],
            "scenes": [
                S("titre-geant", 1, accents=["peu"]),
                S("question", 2, question="D'où vient l'argent ?", pistes=["Les ventes", "Le hot-dog", "Les cartes"]),
                S("barres", 3, titre="Pour 100 $ de coût", barres=[{"label": "coût", "valeur": 100}, {"label": "prix payé", "valeur": 114, "accent": True, "part": 14}], badge="+14 % max"),
                S("courbe", 4, titre="Plafond de marge", plafond=0.62, etiquettePlafond="plafond", etiquetteCourbe="pointillés : ce que les clients accepteraient"),
                S("duel", 5, titre="Marge visée", haut={"titre": "Enseigne classique", "part": 70}, bas={"titre": "Costco", "part": 14}),
                S("titre-geant", 6, accents=["règle"]),
                S("question", 7, question="Où est le vrai gain ?", pistes=["Les courses", "L'abonnement"]),
                S("titre-geant", 8),
            ],
            "short": {"debut_phrase": 1, "fin_phrase": 6, "accroche": "Costco ne gagne presque rien sur tes courses"},
        },
        {
            "titre": "Le hot-dog à un dollar cinquante",
            "phrases": [
                "Deuxième indice : le hot-dog.",
                "Un dollar cinquante, avec une boisson.",
                "Le prix n'a pas bougé depuis mille neuf cent quatre-vingt-cinq.",
                "Même quand les saucisses ont coûté plus cher.",
                "Ce hot-dog attire la foule, et c'est voulu.",
                "On vient pour le hot-dog, on repart avec un téléviseur.",
                "Le hot-dog ne rapporte presque rien.",
                "Mais ce n'est pas encore le vrai gain.",
            ],
            "scenes": [
                S("objet", 1, icone="hotdog", titre="Le hot-dog", sous="le produit qui fait venir"),
                S("chiffre", 2, valeur=1.5, decimales=2, suffixe=" $", etiquette="hot-dog + boisson", sous="menu à prix fixe"),
                S("ligne-temps", 3, de="1985", a="aujourd'hui", valeur="1,50 $", etiquette="le prix qui ne bouge pas"),
                S("titre-geant", 5, accents=["foule", "voulu"]),
                S("objet", 6, icone="panier", titre="Le panier", sous="on repart avec bien plus"),
                S("liste", 7, titre="Le calcul", items=[{"texte": "Le hot-dog", "valeur": "1,50 $"}, {"texte": "Le panier moyen", "valeur": "bien plus"}, {"texte": "Le gain", "valeur": "ailleurs"}]),
                S("question", 8, question="Alors, où ?", pistes=["Les cartes"]),
            ],
            "short": {"debut_phrase": 2, "fin_phrase": 8, "accroche": "Pourquoi le hot-dog Costco ne change jamais de prix"},
        },
        {
            "titre": "La carte de membre",
            "phrases": [
                "Le vrai gain, c'est la carte de membre.",
                "Entre soixante-six et soixante-treize pour cent du bénéfice.",
                "Il vient de l'abonnement, pas des courses.",
                "Les clients paient avant d'avoir acheté quoi que ce soit.",
                "Et presque tous la renouvellent chaque année.",
                "Costco gagne d'abord sur ton abonnement.",
                "Pas sur tes courses.",
                "Voilà pourquoi la marge peut rester toute petite.",
            ],
            "scenes": [
                S("objet", 1, icone="carte", titre="La carte de membre", sous="abonnement annuel"),
                S("anneau", 2, valeur=73, repere=66, centre="66–73 %", etiquette="du bénéfice vient des cartes"),
                S("duel", 3, titre="D'où vient le profit", haut={"titre": "Abonnement", "part": 88}, bas={"titre": "Courses", "part": 24}),
                S("liste", 4, titre="Payé d'avance", items=[{"texte": "La carte", "valeur": "avant les courses"}, {"texte": "Le renouvellement", "valeur": "chaque année"}]),
                S("titre-geant", 5, accents=["renouvellent"]),
                S("objet", 6, icone="pieces", titre="L'abonnement", sous="le vrai moteur du profit"),
                S("titre-geant", 7, accents=["courses"]),
            ],
            "short": {"debut_phrase": 1, "fin_phrase": 6, "accroche": "Le vrai secret de Costco : la carte de membre"},
        },
    ],
}

FAITS = [
    {"claim": "Marge plafonnée à 14 %", "valeur": "14 %", "phrase": 3, "sources": ["https://example.org/a", "https://example.org/b"], "check": ["14"], "verified": []},
    {"claim": "Hot-dog à 1,50 $ depuis 1985", "valeur": "1,50 $", "phrase": 10, "sources": ["https://example.org/c", "https://example.org/d"], "check": ["1,50"], "verified": []},
    {"claim": "66 à 73 % du bénéfice", "valeur": "66-73 %", "phrase": 18, "sources": ["https://example.org/e", "https://example.org/f"], "check": ["66"], "verified": []},
]


def timings_pour(ep: dict) -> dict:
    """Timings plausibles : ~3 mots/s, mots répartis au prorata des lettres, mêmes écarts que voice.py."""
    fl = L.flatten(ep)
    t, lines = LEAD, []
    for i, texte in enumerate(fl["phrases"], 1):
        t += fl["pauses"].get(i, 0.0) if i > 1 else 0.0
        mots = texte.replace("…", " ").split()
        dur = 0.35 + len(mots) / MOTS_PAR_S
        poids = [len(m) + 1.5 for m in mots]
        acc, words = t, []
        for m, p in zip(mots, poids):
            d = dur * p / sum(poids)
            words.append({"w": m, "start": round(acc, 3), "end": round(acc + d, 3)})
            acc += d
        lines.append({"start": round(t, 3), "end": round(t + dur, 3), "words": words})
        t += dur + GAP
    return {"total": round(t, 3), "lines": lines}


def ecrire_audio(timings: dict, dest: Path) -> None:
    """Un ton par mot (hauteur variable), silence entre : de quoi vérifier le calage et les volumes."""
    n = int(timings["total"] * SR)
    buf = array.array("h", bytes(2 * n))
    for line in timings["lines"]:
        for k, w in enumerate(line["words"]):
            a, b = int(w["start"] * SR), min(n, int(w["end"] * SR))
            freq = 170 + 35 * (k % 5)
            for j in range(b - a):
                env = min(1.0, j / 400, (b - a - j) / 400)
                buf[a + j] = int(9000 * env * math.sin(2 * math.pi * freq * j / SR))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(buf.tobytes())


def build(dest: Path) -> dict:
    """Écrit la démonstration dans `dest` ; renvoie les timings."""
    dest.mkdir(parents=True, exist_ok=True)
    tm = timings_pour(DEMO)
    common.write_json(dest / "episode-long.json", DEMO)
    common.write_json(dest / "timings.json", tm)
    common.write_json(dest / "faits.json", FAITS)
    ecrire_audio(tm, dest / "voice.wav")
    return tm


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else common.EPISODES / "_demo-long"
    tm = build(out)
    print(f"démo écrite dans {out} : {tm['total']:.1f} s, {len(tm['lines'])} phrases")
