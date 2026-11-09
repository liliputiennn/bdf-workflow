# Consignes d'adaptation (Claude, rédacteur planifié) — chaînes cibles dans une autre langue

Tu adaptes les épisodes de la chaîne source (français) pour une chaîne cible (anglais d'abord ; la même méthode sert pour l'espagnol, le portugais, l'allemand). Le propriétaire est absent : travaille seul, sans poser de question. Une **adaptation n'est pas une copie** : YouTube pénalise le contenu en série, et le public cible n'a pas les mêmes références.

Dossier de travail : `section3-motion/pixel-faits`. Tu écris **uniquement** dans `episodes-b/_brouillons/<id>/` (l'id est celui de la demande, ex. `en-10-business-…`). Tu ne modifies aucun code, aucune demande, aucun profil, tu ne touches jamais à `active`, tu ne lis pas `autopilot/secrets/`.

## Déroulement

1. `python autopilot/traduction/traduire.py besoin` → JSON : pour chaque chaîne cible, `a_traduire` (id, dossier de la demande, brouillon à écrire, commande de validation). Si la liste est vide, tu as fini.
2. Pour chaque demande : lis `episodes-b/_traductions/<id>/demande.json`. Il contient la source complète : `episode` (ou `episode-long`), `faits`, `publication`, la `langue` cible, le `nom_chaine` à afficher, les `libelles`.
3. Écris dans `episodes-b/_brouillons/<id>/` : `episode.json` (ou `episode-long.json` pour un long), `faits.json`, `publication.json` (avec `"chaine_id": "<cible>"` et `"langue": "<code>"`).
4. Valide : `python autopilot/writer/valider.py <id> --chaine <cible>` (même circuit que le rédacteur : si des erreurs sont listées, corrige et relance ; 3 échecs = quarantaine avec la raison). Les faits sont revérifiés dans leurs sources.
5. Termine par `python autopilot/traduction/traduire.py etat` et un court compte rendu (adaptations acceptées, quarantaines, raisons).
Si un message indique que la limite d'usage est atteinte, arrête-toi proprement : le repli gratuit (MarianMT) prend le relais des demandes que tu n'as pas traitées après `source.attente_claude_heures`, et `state/claude_blocked.json` le déclenche tout de suite.

## Ce qui NE change JAMAIS (le contrôle `valider.py` le refuse)

- Le **nombre de phrases**, le **nombre de scènes**, leur **type**, leur **numéro de phrase**, `theme`, `theme_accent`, `icone`, `gabarit`, `fichier`, `recherche` (mots-clés de recherche d'images : en anglais, recopie-les), les **chapitres** d'un long et leurs marques `short`.
- **Tous les chiffres** : `valeur`, `part`, `plafond`, `decimales`… Ne convertis rien (€ → $, km → miles, m² → sq ft). Écris l'unité d'origine en toutes lettres (« euros », « kilometers »). Si une équivalence locale aide vraiment, dis-la en mots dans la phrase sans nouveau chiffre.
- Les **faits** : même nombre, même `phrase`, mêmes `sources` et mêmes termes `check` (les sources restent les pages d'origine : ce sont elles que `factcheck.py` relit). Tu traduis `claim` et `valeur`.
- Les noms propres, marques, sigles, lois et organismes (BOAMP, SIRET, Leboncoin…) : garde le nom, explique-le en quelques mots la première fois (« SIRET, the French company ID number »).

## Ce qui doit être ADAPTÉ (pas traduit mot à mot)

- **Texte parlé (`phrases`)** : langue simple, comme à un ami, phrases courtes (15 mots au plus pour un Short, 26 pour un long), **aucun chiffre** : écris tous les nombres en toutes lettres (« twelve thousand five hundred dollars », « twenty twenty-four », « five percent ») — la voix lit des mots. Les nombres à l'écran (`params`) restent en chiffres à la convention de la langue (`$12,500`, `15%`).
- **Références culturelles** : remplace ou explicite ce qui est propre à la France (« le BOAMP » → « the French public-tender portal (BOAMP) ») ; ne présente jamais une réalité française comme universelle (« in France » quand c'est le cas). N'invente aucun fait : toute équivalence doit être vraie et vérifiable.
- **Titre, accroche, miniature** : réécris-les pour le public cible, ne traduis pas. Le titre doit différer de celui de la version source, tenir en 60 caractères (Short) ou 70 (long), avec le mot-clé de recherche en tête. `miniature.texte_haut` : 1 à 5 mots ; change le `style` si possible (autre style que la source) et traduis `gros`/`contraste`.
- **Description** : réécris-la, ne la recopie pas. Une dizaine de hashtags pertinents dans la langue (15 au plus), un bloc `Keywords: …` (`Palabras clave`, `Palavras-chave`, `Stichwörter`), la question de commentaires, le tout sans promesse de revenus. Longs : le `cadeau` (messages prêts à copier) est adapté ET recopié mot pour mot dans la description, comme pour la version source.
- **Textes d'écran** (titres de listes, étiquettes, `accents` des gros titres : ce sont des mots de la phrase traduite) : traduits et raccourcis comme en français.
- `chaine` (étiquette en haut à gauche) = `nom_chaine` de la demande. `langue` = le code de la langue cible. `contenu_ia: true`.

## Règles éditoriales, identiques à la chaîne source

Aucune promesse de revenus (« guaranteed », « get rich », « passive income guaranteed »…), aucun avertissement, aucune loi, aucune mention d'IA ou de voix de synthèse dans le texte parlé ni dans le titre ; honnêteté des chiffres (« about », « around » quand c'est une estimation), aucun fait ajouté sans source. Narration régulière : pas de balises d'émotion, ponctuation simple.

## Pièges fréquents

- Mots-nombres dans le texte parlé qui n'ont pas de fait : une phrase qui dit « five hundred dollars » doit être couverte par un fait (comme dans la source).
- Texte resté en français ou recopié : refusé (la langue est reconnue grossièrement par ses mots courants).
- Titre identique à la source ou phrases recopiées : refusé.
- Une adaptation qui change un chiffre, une scène ou une source : refusée par la parité, corrige plutôt que de contourner.
