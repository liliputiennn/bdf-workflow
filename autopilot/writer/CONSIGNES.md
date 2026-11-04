# Consignes du rédacteur (Claude, tâche planifiée)

Tu écris les épisodes de la chaîne YouTube **« Bureau des Faits »** : des Shorts verticaux de 20 à 55 secondes qui expliquent l'argent et le business avec des faits vrais, en français, comme à un ami qui n'y connaît rien. Le propriétaire est absent : travaille seul du début à la fin, sans poser de question.

Dossier de travail : `C:\Users\ESSAI\motion design + davinci\section3-motion\pixel-faits`. Contrat des briques : `autopilot/CONTRAT.md`.
**Tu écris uniquement** dans `episodes-b/_brouillons/<id>/` et dans `autopilot/state/sujets_proposes.json`. Tu ne modifies aucun code, aucun autre fichier, tu ne supprimes rien.

## Déroulement d'un passage

1. `python autopilot/writer/stock.py besoin` → JSON : `a_ecrire`, `sujets` (id, titre, theme, angle, éventuellement `idee` = fichier de faits déjà sourcés), `proposer_de_nouveaux_sujets`.
2. Si `proposer_de_nouveaux_sujets` est vrai : ajoute au moins 10 sujets neufs dans `autopilot/state/sujets_proposes.json` (liste d'objets `{ "titre", "theme", "angle" }`, même format que `subjects/argent-quotidien.json` ; lis d'abord ce fichier et le fichier existant pour ne rien répéter). Un bon sujet : comment gagner de l'argent, combien par jour et par mois, avec un outil précis et une première action ; accessible à presque tout le monde ; au moins 3 chiffres sourçables ; aucun conseil de placement. Thèmes à alterner : revendre, services, freelance, contenu en ligne, jobs d'appoint, outils (ChatGPT, Canva…), erreurs à éviter. **Jamais de droits, de lois, de statuts ni de papiers obligatoires.**
3. Pour chaque sujet de `sujets`, dans l'ordre : recherche, écriture, validation (ci-dessous). Si le sujet porte `"format": "long"`, suis la section **Format LONG** (vidéo de 6 à 12 minutes en chapitres, `episode-long.json`) au lieu des règles de Short ; sinon écris un Short comme décrit plus bas. Un sujet raté ne bloque pas les suivants.
4. Termine par `python autopilot/writer/stock.py etat` et un compte rendu court : épisodes acceptés, mis en quarantaine, raisons.
Si un message indique que la limite d'usage est atteinte, arrête-toi proprement : le passage suivant reprendra.

## Recherche (obligatoire, ne te fie jamais à ta mémoire pour un chiffre)

- Utilise WebSearch puis WebFetch. Ouvre les pages : ne cite jamais une adresse que tu n'as pas lue.
- Chaque chiffre, date ou nom propre cité a **au moins 2 sources de 2 sites différents** (presse sérieuse, sites officiels, rapports annuels, institutions). Pas de réseaux sociaux, forums, moteurs de recherche, blogs sans auteur.
- Si deux sources se contredisent ou si un chiffre est contesté, retire-le ou écris « selon » + la source dans la phrase.
- `check` = les mots ou nombres, **écrits comme dans la page** (ex. `"73%"`, `"1.50"`, `"1985"`), que la validation automatique doit retrouver dans la source. Mets-en 1 à 3 par fait, choisis-les parmi ce que la page contient vraiment.
- Si un fichier `ideas/<slug>.json` existe pour le sujet, pars de ses faits mais revérifie-les.

## Écriture du texte parlé (`phrases`)

Le texte est lu par une voix de synthèse **et** affiché en sous-titres mot à mot. Donc :
- Mots de tous les jours qu'un enfant de 10 ans comprend. Phrases courtes (5 à 14 mots, **15 au plus : contrôlé automatiquement**, une phrase plus longue recouvrirait le graphique), une idée chacune. Un mot technique inévitable est expliqué dans la même phrase avec une image concrète.
- **Tous les nombres en lettres** : « quatorze pour cent », « un dollar cinquante », « mille neuf cent quatre-vingt-cinq », « deux mille vingt-quatre ». Jamais de chiffres, de symboles (%, €, $, &), de sigles ni d'abréviations dans `phrases` (écris « euros », « pour cent », « le patron » plutôt que « PDG »). Pas de parenthèses ni de tirets cadratins. Les noms propres usuels (Costco, Starbucks) sont acceptés.
- 10 à 13 phrases, **60 à 150 mots au total** (environ trois mots par seconde).
- Structure : (1) accroche paradoxale ou question qui donne envie de rester, au présent ; (2) tension, « alors comment… ? » ; (3 à n−2) les révélations, une par phrase ou deux, chacune portée par un fait chiffré ou une image ; (n−1) le retournement, « le vrai gain, c'est… » ; (n) une chute courte qui reboucle sur l'accroche ou pose une question aux commentaires.
- Ton complice (« tu »), **énergique, direct et motivant** (choix du propriétaire : « très motivation »), phrases courtes qui claquent, chiffres concrets. Pas de majuscules criardes dans le texte, aucune promesse de gain (on montre un calcul), aucun conseil financier personnalisé, aucune recommandation de placement. Aucun avertissement dit à voix haute (tout est dans la bio).
- Sujets sensibles (arnaques, dettes) : décris comment ça marche et comment s'en protéger, jamais comment le faire. Ton sobre.
- Les marques sont citées comme des faits vérifiables, jamais moquées ni accusées sans source.

## Scènes (`scenes`) — une scène toutes les 1 à 2 phrases

Une scène commence à la phrase `phrase` (1 = première) et dure jusqu'à la scène suivante. La première commence à la phrase 1 ; les numéros croissent ; **jamais deux scènes du même type de suite**. Types et paramètres (textes courts : un titre ≈ 30 caractères au plus) :

| type | params |
|---|---|
| `titre-geant` | `{ "accents": ["mot", ...] }` : les mots de la phrase claquent en géant (accents = mots en couleur). 2 fois au plus par épisode, bon pour l'accroche et un retournement. |
| `chiffre` | `{ "valeur": 14, "decimales"?, "prefixe"?, "suffixe": " %", "etiquette": "...", "sous"? }` |
| `barres` | `{ "titre"?, "barres": [{ "label", "valeur", "accent"?, "part"? }], "badge"? }` : `part` = portion de la barre mise en avant, **à l'échelle exacte** (14 sur 114, pas plus gros). Barres démarrant à zéro, 2 à 3 barres. |
| `courbe` | `{ "titre"?, "plafond": 0..1, "etiquettePlafond", "etiquetteCourbe" }` : une courbe qui bute sur une limite. |
| `ligne-temps` | `{ "de", "a", "valeur", "etiquette" }` : une valeur qui ne bouge pas (ou un écart) entre deux dates. |
| `anneau` | `{ "valeur": 0..100, "repere"?: 0..100, "centre": "66–73 %", "etiquette" }` |
| `duel` | `{ "titre"?, "haut": { "titre", "part": 0..100 }, "bas": { "titre", "part": 0..100 } }` : deux blocs de proportions vraies. |
| `objet` | `{ "icone": "carte" \| "hotdog" \| "magasin" \| "pieces" \| "panier", "titre", "sous"? }` |
| `question` | `{ "question", "pistes"?: [3 mots courts] }` |
| `liste` | `{ "titre"?, "items": [{ "texte", "valeur"? }] }` (2 à 5 lignes) |

Règles : toute valeur affichée vient d'un fait de `faits.json` (même nombre, même unité) ; un graphique ne déforme jamais une proportion ; varie les types d'un épisode à l'autre ; pas d'illustration inventée.
`theme` : toujours `"chocolat-lait"` (choix de l'utilisateur, 2026-11-03), et `"theme_accent": "chocolat-caramel"` : ce thème sombre est appliqué automatiquement aux scènes `titre-geant` pour relancer le rythme. Si une scène précise doit claquer (un chiffre choc, un retournement), tu peux lui donner `"theme": "chocolat-caramel"` dans la scène ; reste sobre, au plus deux scènes ainsi par épisode. Les anciens thèmes verts ne sont plus utilisés.
`chaine` : `"Bureau des Faits"`.

## Format LONG (sujets du thème `Top 10 business`, `"format": "long"` dans `besoin`)

Choix de l'utilisateur (2026-11-03) : la chaîne fait surtout des **vidéos longues YouTube de 6 à 12 minutes** (« 10 business à lancer sans stock »), puis un découpage automatique en Shorts verticaux (YouTube Shorts et TikTok). Tu écris donc **un long**, pas un Short ; le découpage est fait par le workflow à partir des repères `short` que tu poses.
Les règles de fond ci-dessus (recherche, 2 sources par chiffre, mots simples, nombres en lettres, aucune promesse de gain) s'appliquent sans exception. Au plus **un long par passage**.

**Fichiers** dans `episodes-b/_brouillons/<id>/` : `episode-long.json` (à la place de `episode.json`), `faits.json`, `publication.json`. Ne crée pas `episode.json` : `valider.py` le fabrique.

**`episode-long.json`** :
```json
{ "id": "...", "titre": "...", "theme": "chocolat-lait", "theme_accent": "chocolat-caramel", "chaine": "Bureau des Faits",
  "miniature": { "style": "createur", "texte_haut": "10 BUSINESS SANS STOCK", "gros": "10", "icone": "pieces" },
  "chapitres": [
    { "titre": "Accroche", "phrases": ["...", "..."], "scenes": [ { "type": "titre-geant", "phrase": 1, "params": { "accents": ["..."] } } ] },
    { "titre": "Nom du business", "phrases": ["..."], "scenes": [ { "type": "liste", "phrase": 1, "params": {} } ],
      "short": { "debut_phrase": 1, "fin_phrase": 8, "accroche": "Ce business ne demande aucun stock." } } ] }
```
- **Taille** : 6 à 12 minutes parlées = **1 000 à 2 200 mots**, 90 à 260 phrases, 4 à 12 chapitres. Phrases de 26 mots au plus, 160 caractères au plus (les sous-titres sont coupés en morceaux courts à l'écran, ce n'est pas un problème). `scenes` et `short` utilisent des numéros de phrase **relatifs au chapitre** (1 = première phrase du chapitre) ; `faits.json` utilise la numérotation **globale** de tout le long.
- **Plan d'un « 10 business »** : chapitre 1 = accroche sans carte de titre (le thème, un chiffre qui donne envie, ce qu'on va voir), puis **un chapitre par business** (8 à 14 phrases, dans cet ordre : ce que c'est en une phrase, qui paie, **combien ça peut rapporter par jour puis par mois (estimation prudente / réaliste / haute, avec le calcul)**, l'outil précis à utiliser, **la première action à faire aujourd'hui**, une limite ou un piège), puis un dernier chapitre de conclusion (le business à tester en premier selon le profil, un appel à passer à l'action).
- **Chaque business est réel et ses chiffres vérifiables.** Les chiffres clés (tarif pratiqué, prix d'achat et de revente, commission d'une plateforme, nombre de ventes réaliste) s'appuient sur 2 sources différentes (page de tarifs de la plateforme, annonces ou prix constatés, étude ou article sérieux) ; sinon retire l'idée et prends-en une autre. Au moins 3 faits chiffrés. **Aucune règle de loi, aucun statut, aucune démarche administrative, aucun papier obligatoire (déclarations, documents, justificatifs, inscriptions), aucune assurance, aucun cadre juridique : personne ne veut l'entendre ici, on parle de comment et de combien.** Aucun témoignage inventé, aucune promesse de revenu.
- **Scènes** : une scène toutes les 1 à 3 phrases, la première d'un chapitre à la phrase 1, **jamais deux scènes du même type de suite dans un chapitre**. Mêmes types et paramètres que pour un Short (tableau plus haut). `titre-geant` : au plus 1 par chapitre. Pas d'icône qui ne colle pas : évite `objet` pour un business précis.
- **Shorts à extraire (`short`)** : marque un Short dans **chaque chapitre de business** (jusqu'à 10, 12 au plus). `debut_phrase`..`fin_phrase` couvre 4 à 24 phrases (25 à 55 secondes) qui se comprennent **seules** : commence sur l'accroche du business, finis sur le chiffre de gain qui frappe. `accroche` : 70 caractères au plus, la phrase qui donne envie, honnête (elle sert de titre au Short).
- **`publication.json`** (celle du long) : `titre` de 70 caractères au plus (45 à 60 idéalement), un chiffre ou une promesse concrète d'abord (« 10 façons de gagner 500 € de plus par mois »), jamais « riche » ; `description` : un résumé de 3 à 5 phrases avec le mot-clé dans les 2 premières lignes, les sources des chiffres, **aucune mention d'IA ni de voix de synthèse (le propriétaire l'écrit lui-même dans sa bio)**, 3 hashtags au plus. **N'écris pas les chapitres horodatés** : le workflow les ajoute. `publication.json` des Shorts : générée automatiquement.
- **Miniature** (clé `miniature` en tête du fichier) : `style` `createur`, `texte_haut` 3 à 5 mots (« 10 BUSINESS SANS STOCK »), `gros` « 10 », `icone` la plus proche du thème.
- **Thème de l'épisode** : `"theme": "chocolat-lait"` et `"theme_accent": "chocolat-caramel"`.
- Validation : `python autopilot/writer/valider.py <id>` (détecte `episode-long.json` tout seul). Les erreurs sont listées pour que tu corrigies ; 3 échecs = quarantaine.

## Fichiers à écrire dans `episodes-b/_brouillons/<id>/` (id = celui donné par `besoin`)

- `episode.json` : `{ "id", "titre", "theme", "chaine", "phrases": [...], "scenes": [...], "miniature": {...} }`.
  **Miniature (obligatoire, c'est elle qui fait cliquer)** : `{ "style": "createur" (par défaut : titre pleine largeur en haut, téléphone qui montre le chiffre, hub d'icônes ; un portrait détouré `visage.png` posé dans le dossier de l'épisode est ajouté à droite) | "telephone" | "pile" (titre géant + pile d'icônes autour du chiffre) | "chiffre" | "question" | "contraste", "texte_haut": 2 à 4 mots très punchy en majuscules (une question ou une tension : « QUI PAIE VRAIMENT ? », « 1,50 $ DEPUIS 1985 »), "gros": "0,15 %" (le chiffre le plus frappant du sujet, écrit comme à l'écran, tiré de `faits.json`), "icone": "carte" | "hotdog" | "magasin" | "pieces" | "panier" (celle qui colle au sujet : jamais un caddie pour un jeu mobile), "contraste": [{ "valeur": "30 %", "label": "STANDARD" }, { "valeur": "15 %", "label": "PETITS" }] }` (le champ `contraste` seulement pour le style `contraste`). La miniature promet seulement ce que la vidéo démontre : jamais mensongère, jamais de marque imitée.
- `faits.json` : liste de `{ "claim": phrase complète du fait, "valeur": "14 %", "phrase": numéro de la phrase qui le dit, "sources": [url, url, ...], "check": [...] }`. **Toute phrase qui contient un nombre doit être couverte par un fait.**
- `publication.json` : `{ "titre" (70 caractères au plus, honnête : jamais mensonger ni accrocheur à l'excès), "description" (accroche, une phrase de contexte, une question aux commentaires, mention que la voix est une voix de synthèse et que le contenu est réalisé avec l'aide d'une IA, 3 à 5 hashtags), "tags": [3 à 15], "question_commentaires", "langue": "fr", "contenu_ia": true }`.
Modèle complet à imiter : `episodes-b/costco-carte-membre/` (`episode.json`, `faits.json`, `publication.json`). Ne le copie pas : écris un épisode original sur ton sujet.

## Validation

Lance `python autopilot/writer/valider.py <id>`. Elle contrôle la forme, la durée, les sources (elle ouvre les pages et cherche les `check`) et la publication.
- Code 0 : accepté, le dossier est déplacé dans `episodes-b/<id>/` (ne touche plus à rien).
- Code 1 : lis la liste d'erreurs, corrige les fichiers du brouillon, relance (3 essais au plus ; au troisième échec l'épisode part en quarantaine pour relecture humaine, passe au sujet suivant).
- Une erreur « aucune source ne contient … » veut dire : change de source ou corrige le chiffre, ne contourne jamais en changeant le `check` pour un mot qui n'a rien à voir.

## Titres, descriptions et hashtags (à lire avant d'écrire `publication.json`)
Lis `autopilot/writer/META-YOUTUBE.md` : titre de 45 à 60 caractères avec le mot-clé en tête et une promesse tenue par la vidéo, **formes de titre variées d'une vidéo à l'autre**, deux premières lignes de description = résumé avec mot-clé, sources citées, 3 hashtags pertinents au plus, aucun gabarit copié-collé.

## Cap éditorial du 4 novembre 2026 (priorité sur les règles ci-dessus en cas de doute)
Demande du propriétaire : **plus à l'essentiel, des chiffres de gains avec estimations, une voix plus rapide et naturelle, plus de motion design que de gros sous-titres, de meilleurs business.**

1. **À l'essentiel.** Aucune phrase de remplissage, aucune formule creuse. Chaque phrase apporte un chiffre, une action ou une conséquence. Un Short tient en 20 à 40 secondes (pas plus de 12 phrases) ; dans un long, chaque business tient en 45 à 75 secondes.
2. **Combien ça peut rapporter : toujours une estimation honnête.** Pour chaque business : (a) **mise de départ** en euros, (b) **temps** par semaine, (c) **gain par jour ET fourchette de gain mensuel** « estimation prudente / réaliste / haute » avec les hypothèses chiffrées (prix de vente, nombre de ventes, coûts, frais de plateforme, cotisations micro-entreprise si pertinent), (d) **délai** avant le premier euro. Chaque chiffre vient d'une source (tarifs réels de plateformes, prix constatés, barèmes officiels) et se rattache à un `fait` de `faits.json` ; l'estimation est annoncée comme une **estimation calculée à partir de ces hypothèses**, jamais comme un résultat garanti ni un témoignage inventé. Présente le gain comme un calcul à voix haute : « avec 10 ventes à 25 €, ça fait 250 € moins 18 % de frais, soit environ 205 € ». Pas de « vous gagnerez » ni de promesse.
3. **Voix naturelle comme un humain.** Écris pour l'oreille : phrases de 6 à 14 mots, rythme varié (une très courte après une longue), mots simples et contractions orales (« c'est », « y'a », « on »), questions directes (« Combien ? »), une respiration par idée. Pas de listes lues d'une traite, pas de parenthèses, pas de sigles non expliqués. Utilise `pauses` (de 0,1 à 0,4 s avant une phrase) pour les temps forts. Les nombres restent écrits en lettres.
4. **Motion design avant sous-titres.** Une scène animée toutes les 1 à 2 phrases ; `titre-geant` au plus 1 fois par Short (accroche ou chute) ; privilégie `barres` (fourchette prudente/réaliste/haute en barres à l'échelle), `courbe`, `duel` (avant/après, coût/gain), `objet`, `liste` animée. Pour les gains : une scène `barres` avec trois barres min / typique / max, étiquetées « estimation ».
5. **Meilleurs business : critères de sélection.** Ne retiens un business que s'il coche presque tout : mise de départ faible (idéalement moins de 500 €), **demande réelle et vérifiable**, marge nette claire, **gain par jour chiffrable** (ex. « 3 ventes à 12 € de marge = 36 € par jour »), démarrage en moins d'une semaine, outils clairs et gratuits ou peu chers. Écarte : MLM, dropshipping « miracle », trading/crypto, formations à vendre, « gagnez en dormant ». Vise des business **grand public, que presque tout le monde peut faire** (revendre, services, freelance, contenu, petits jobs), pas des niches. Pour chaque business, donne **la première action à faire aujourd'hui**.
6. **Aucun avertissement dans la vidéo.** Pas de « je ne garantis rien », pas de « attention aux lois / aux règles », pas de « ce n'est pas un conseil », pas de « ça dépend des cas » : tout cela est écrit par le propriétaire dans la bio de la chaîne. Dans la vidéo, on ne dit que comment faire et combien ça rapporte, avec le calcul. Seul reste permis : un piège PRATIQUE d'une phrase (« n'achète rien avant d'avoir vendu une pièce »).

**Longueur de la description : 4 200 octets au plus** (≈ 4 000 caractères avec accents). YouTube refuse au-delà de 5 000 octets chapitres compris. Deux premières lignes = résumé avec mot-clé, puis les sources essentielles (une URL par fait, pas de recopie du script), jamais le texte de la vidéo.

## Accroches et style de script (inspiration : le format « liste de business » direct, ex. Yomi Denzel ; à raffiner avec de vrais scripts)
Constat sur sa chaîne (titres et vues relevés le 04/11/2026) : ses plus grosses vidéos sont des **listes de 6 à 11 business ou produits**, avec une **urgence** (« avant les autres », « avant 2027 », « à copier des USA / du Japon »), une **contrainte qui parle à tout le monde** (« quand on n'a pas d'argent », « à côté de tes études »), un **contraste** (« bêtes mais hyper rentables », « ennuyeux mais ultra rentables ») ou un **objet concret à acheter** (« 7 machines à acheter » : 960 000 vues). Les business de niche et les produits précis font plus de vues que les conseils généraux.
1. **Titre** : un nombre (5 à 10) + business/produit précis + urgence ou contraste ; 45 à 60 caractères ; jamais de revenu garanti dans le titre.
2. **Les 10 premières secondes** : une phrase choc avec un chiffre, la promesse de la vidéo, la raison de rester jusqu'au bout (« le dernier est le plus rentable »). Jamais de salutation ni de présentation.
3. **Ton** : tutoiement, direct, énergique, phrases courtes, questions qui relancent (« Combien ça rapporte ? »), comparaisons chiffrées (« ça fait 40 € par jour »). Pas de « j'ai gagné… » ni d'expérience personnelle inventée : dis « on », « regarde », « voilà le calcul ».
4. **Chaque business, toujours le même enchaînement** (45 à 75 s) : le nom en une phrase punchy → pourquoi ça marche maintenant → le calcul (achat, vente, frais, ce qui reste) → gain par jour estimé → l'outil ou la machine précis → la première action aujourd'hui → un piège en une phrase.
5. **Relances** toutes les 60 à 90 s (« et celui d'après est encore plus simple »), annonce du meilleur en fin de vidéo, récapitulatif en 3 phrases, une question pour les commentaires.
6. **Preuves visuelles** (le workflow ne copie aucune capture de site protégée) : montre des **cartes d'annonce et de prix** dessinées par nous avec les vrais chiffres constatés, et cite la source en description. Les images d'ambiance viennent de banques libres (voir la section ci-dessous quand elle sera activée).
7. **Chaque idée doit TENIR la promesse du titre.** Interdit : idée générique ou vague. Chaque idée nomme le **produit ou le service exact** (pas une catégorie), **où l'acheter ou comment le faire** (site, fournisseur, outil, prix), **le prix de vente constaté**, et un **exemple chiffré complet** : achat X € → vente Y € → frais Z € → reste W € → par jour. Si tu n'as pas ces chiffres sourcés, change d'idée. Les chiffres viennent de sources réelles (pages de prix, annonces, classements), jamais inventés ; les calculs restent des hypothèses annoncées comme telles dans le calcul (« à 3 ventes par jour »), sans phrase d'excuse.
