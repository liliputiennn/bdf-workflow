"""Format musique pour enfants (PomPikoBoo) : sécurité des paroles, alignement paroles/chant, personnages, rendu, déclaration « conçu pour les enfants ». Aucun réseau, aucun GPU."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from autopilot.formats import alignement, pompikoboo, rendu
from autopilot.formats import musique_enfants as m

RACINE = Path(__file__).resolve().parents[3]
DESC = {"description": "Une petite chanson sur le jardin. Chanson originale à chanter avec les paroles à l'écran.", "langue": "fr"}


def episode():
    return {"id": "musique-test", "titre": "Chanson du petit jardin pour enfants", "chaine": "PomPikoBoo", "theme": "musique", "video": "short",
            "format_contenu": "musique_enfants", "pour_enfants": True,
            "chanson": {"tempo": 100, "style": "comptine_joyeuse", "ordre": ["c1", "r"], "strophes": {
                "c1": {"lignes": ["Le soleil se lève sur le jardin", "Pompi saute dans l'herbe", "Piko ouvre sa jolie fleur", "Les abeilles chantent bonjour"]},
                "r": {"lignes": ["Tape des mains, tra la la", "Saute avec nous, tra la la", "Tourne, tourne, tra la la"]}}},
            "miniature": {"texte_haut": "Chanson", "gros": "Le jardin"}}


def fausse_chanson(ep, dossier: Path, appariement_ok: bool = True) -> None:
    """chanson.wav (salves de sons par mot, 48 kHz) + alignement.json cohérent avec les paroles : remplace le noyau Kaggle dans les tests."""
    lignes = [l["texte"] for l in m.lignes_dans_l_ordre(ep["chanson"])]
    sr = rendu.SR
    total = 6 + 4.5 * len(lignes) + 3
    x = np.zeros(int(total * sr), dtype=np.float32)
    mots = []
    t = 6.0
    for l in lignes:
        for w in l.split():
            d = 0.5
            k = np.arange(int(d * sr))
            x[int(t * sr):int(t * sr) + len(k)] += 0.3 * np.sin(2 * np.pi * 330 * k / sr) * np.hanning(len(k))
            mots.append({"mot": w, "debut": t, "fin": t + d})
            t += d + 0.08
        t += 0.5
    rendu.ecrire_wav(dossier / "chanson.wav", x)
    al = alignement.aligner(lignes, mots if appariement_ok else [], total)
    al.update(duree=round(total, 2), graine=1)
    (dossier / "alignement.json").write_text(json.dumps(al), encoding="utf-8")


def valider(ep, pub=None):
    return m.valider_episode(ep, None, DESC if pub is None else pub, {}, reseau=False)


class Validation(unittest.TestCase):
    def refuse(self, ep, morceau, pub=None):
        err, _ = valider(ep, pub)
        self.assertTrue(any(morceau in e for e in err), err)

    def test_chanson_valide(self):
        self.assertEqual(valider(episode())[0], [])

    def test_style_ferme(self):
        ep = episode()
        ep["chanson"]["style"] = "dans le style de quelqu'un"
        self.refuse(ep, "style")

    def test_tempo(self):
        ep = episode()
        ep["chanson"]["tempo"] = 200
        self.refuse(ep, "tempo")

    def test_lignes_courtes(self):
        ep = episode()
        ep["chanson"]["strophes"]["c1"]["lignes"][0] = "Un deux trois quatre cinq six sept huit neuf dix onze"
        self.refuse(ep, "2 à 9 mots")
        ep = episode()
        ep["chanson"]["strophes"]["r"]["lignes"] = ["Seule"]
        self.refuse(ep, "2 à 8 lignes")

    def test_air_connu_refuse(self):
        ep = episode()
        ep["chanson"]["strophes"]["r"]["lignes"][0] = "Frère Jacques dort encore"
        self.refuse(ep, "existante")
        ep = episode()
        ep["titre"] = "Chanson de la petite étoile pour enfants"
        self.refuse(ep, "existante")

    def test_mots_interdits_pour_enfants(self):
        ep = episode()
        ep["titre"] = "Chanson du monstre pour enfants"
        self.refuse(ep, "interdit sur une chaîne pour enfants")
        ep = episode()
        ep["chanson"]["strophes"]["c1"]["lignes"][3] = "Zou zou, cocomelon bonjour"
        self.refuse(ep, "interdit sur une chaîne pour enfants")

    def test_chiffres_et_pour_enfants(self):
        ep = episode()
        ep["titre"] = "Chanson des 3 petits chats pour enfants"
        self.refuse(ep, "pas de chiffres")
        ep = episode()
        ep["pour_enfants"] = False
        self.refuse(ep, "pour_enfants")

    def test_durees_et_refrain(self):
        ep = episode()
        ep["chanson"]["ordre"] = ["r"]
        ep["chanson"]["strophes"]["r"]["lignes"] = ep["chanson"]["strophes"]["r"]["lignes"][:2]
        self.refuse(ep, "la chanson durera")
        ep = episode()
        ep["chanson"]["strophes"] = {"c1": ep["chanson"]["strophes"]["c1"], "c2": ep["chanson"]["strophes"]["r"]}
        ep["chanson"]["ordre"] = ["c1", "c2"]
        self.refuse(ep, "refrain")

    def test_description_sans_lien_ni_appel(self):
        self.refuse(episode(), "aucun lien", pub={"description": "Chanson originale. Voir https://exemple.com", "langue": "fr"})
        self.refuse(episode(), "interdit", pub={"description": "Chanson originale. Abonne-toi !", "langue": "fr"})
        self.refuse(episode(), "mention", pub={"description": "Une chanson.", "langue": "fr"})

    def test_titre_et_miniature(self):
        ep = episode()
        ep["titre"] = "Le petit jardin"
        self.refuse(ep, "chanson")
        ep = episode()
        del ep["miniature"]
        self.refuse(ep, "miniature")

    def test_forme_illisible(self):
        self.assertTrue(valider({"id": "x"})[0])
        self.assertTrue(m.valider_episode(None, None, None, {})[0])
        ep = episode()
        ep["chanson"]["ordre"] = ["zzz"]
        self.assertTrue(valider(ep)[0])


class Paroles(unittest.TestCase):
    def test_balises_et_entree_modele(self):
        ep = episode()
        p = m.paroles_balisees(ep["chanson"])
        self.assertTrue(p.startswith("[Intro]") and p.rstrip().endswith("[Outro]"))
        self.assertIn("[Verse 1]\nLe soleil", p)
        self.assertIn("[Chorus]\nTape des mains", p)
        e = m.entree_musique(ep)
        self.assertEqual(len(e["lignes"]), 7)
        self.assertEqual(e["langue"], "fr")
        self.assertNotRegex(e["caption"].lower(), r"disney|cocomelon|pinkfong")  # style fermé : jamais de nom d'artiste ni de marque
        self.assertEqual(m.script_voix(ep)["phrases"], [])

    def test_styles_sans_marque(self):
        for s in m.STYLES.values():
            self.assertIsNone(m.RE_MOT_INTERDIT.search(s))


class Alignement(unittest.TestCase):
    LIGNES = ["Le soleil se lève", "Pompi saute dans l'herbe", "Tape des mains"]

    def mots(self, deb=5.0):
        out, t = [], deb
        for l in self.LIGNES:
            for w in l.split():
                out.append({"mot": w, "debut": t, "fin": t + 0.4})
                t += 0.5
            t += 1.0
        return out

    def test_whisper_parfait(self):
        al = alignement.aligner(self.LIGNES, self.mots(), 30)
        self.assertEqual(al["methode"], "whisper")
        self.assertGreater(al["appariement"], 0.9)
        self.assertAlmostEqual(al["lignes"][0]["debut"], 5.0, delta=0.2)
        self.assertGreater(al["lignes"][1]["debut"], al["lignes"][0]["fin"] - 0.01)

    def test_transcription_bruitee_et_mots_manquants(self):
        mots = [dict(w, mot=w["mot"].replace("o", "ou")) if i % 4 == 0 else w for i, w in enumerate(self.mots()) if i != 3]
        al = alignement.aligner(self.LIGNES, mots, 30)
        self.assertEqual(al["methode"], "whisper")
        debuts = [l["debut"] for l in al["lignes"]]
        self.assertEqual(debuts, sorted(debuts))

    def test_repli_regulier_si_chant_inintelligible(self):
        al = alignement.aligner(self.LIGNES, [{"mot": "zzz", "debut": 1, "fin": 2}], 40)
        self.assertEqual(al["methode"], "regulier")
        self.assertLess(al["appariement"], alignement.MIN_APPARIEMENT)
        self.assertEqual(len(al["lignes"]), 3)
        self.assertGreater(al["lignes"][2]["fin"], al["lignes"][0]["debut"])

    def test_enveloppe_bouche(self):
        sr, fps = rendu.SR, 24
        x = np.zeros(sr * 2, dtype=np.float32)
        x[sr:] = 0.4 * np.sin(2 * np.pi * 400 * np.arange(sr) / sr)
        e = alignement.enveloppe_voix(x, sr, fps)
        self.assertLess(e[:20].mean(), 0.1)
        self.assertGreater(e[30:46].mean(), 0.7)


class Personnages(unittest.TestCase):
    def test_sprites_et_animation(self):
        for nom in ("elephant", "cactus"):
            s = pompikoboo.sprite(nom, 2, False, 1)
            self.assertEqual(s.size, (pompikoboo.L, pompikoboo.H))
            self.assertGreater(np.array(s.getchannel("A")).mean(), 40)  # le personnage est bien dessiné (pas un calque vide)
            img, dy, _ = pompikoboo.animer(nom, 1.3, 0.6, 0.8, True)
            self.assertEqual(img.mode, "RGBA")
            self.assertLessEqual(dy, 0)
        a = np.array(pompikoboo.sprite("elephant", 0, False, 0))
        b = np.array(pompikoboo.sprite("elephant", 3, False, 0))
        self.assertGreater(np.abs(a.astype(int) - b.astype(int)).sum(), 1000)  # la bouche ouverte change l'image


class Rendu(unittest.TestCase):
    def test_rendu_complet(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-mus-"))
        try:
            ep = episode()
            fausse_chanson(ep, tmp)
            qa = {}
            final = m.rendre(ep, tmp, tmp, {"nom": "PomPikoBoo"}, qa, fps=6)
            self.assertTrue(final.exists())
            self.assertTrue(25 <= qa["duree_s"] <= 80, qa)
            self.assertTrue(-17.5 <= qa["lufs"] <= -14.5, qa)
            self.assertTrue(qa["pour_enfants"])
            self.assertGreater(qa["appariement"], 0.9)
            self.assertFalse(qa.get("alertes"))
            self.assertEqual(m.miniature(ep, {}).size, (1280, 720))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_chant_inintelligible_alerte(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-mus-"))
        try:
            ep = episode()
            fausse_chanson(ep, tmp, appariement_ok=False)
            qa = {}
            m.rendre(ep, tmp, tmp, {}, qa, fps=4)
            self.assertTrue(any("peu intelligible" in a for a in qa["alertes"]), qa)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_audio_manquant_sans_cloud(self):
        tmp = Path(tempfile.mkdtemp(prefix="bdf-mus-"))
        try:
            with self.assertRaises(FileNotFoundError):
                m.generer_audio(episode(), tmp, sans_cloud=True)
            fausse_chanson(episode(), tmp)
            m.generer_audio(episode(), tmp, sans_cloud=True)  # fichiers présents : rien à faire
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Banque(unittest.TestCase):
    def test_sujets_de_depart(self):
        s = json.loads((RACINE / "subjects" / "musique-enfants" / "00-sujets-de-depart.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s), 25)
        self.assertEqual(len({x["titre"] for x in s}), len(s))
        txt = " ".join(x["titre"] + x.get("angle", "") for x in s)
        self.assertIsNone(m.RE_MOT_INTERDIT.search(txt), m.RE_MOT_INTERDIT.search(txt))


if __name__ == "__main__":
    unittest.main()
