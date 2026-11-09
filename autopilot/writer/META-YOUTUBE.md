# Titres, descriptions et mots-clés YouTube : règles pour le rédacteur

Recherche du 03/11/2026. Trois niveaux de fiabilité : **[officiel]** lu sur l'aide YouTube, **[pratique]** observé par des créateurs et outils tiers (utile, non garanti), **[à vérifier]**. Personne ne peut garantir une vidéo « en tendance » : on maximise les chances, on mesure, on corrige.

## Titre
- **[pratique] 45 à 60 caractères**, mot-clé principal au début : au-delà d'environ 60, YouTube coupe le titre sur mobile (le validateur accepte jusqu'à 70, ne dépasse pas 60 sauf nécessité).
- **[officiel] Un ou deux mots-clés** qui décrivent la vidéo, répétés dans le titre ET la description (l'aide YouTube conseille de les chercher dans l'onglet « Recherche » d'Analytics et le « How viewers find your » report).
- **[pratique] Une promesse concrète et vérifiable** : un chiffre réel (« 12 € par jour pendant 20 ans, ça fait combien ? »), une question que se pose quelqu'un de normal, un résultat surprenant. La vidéo doit **tenir** la promesse du titre ET de la miniature : c'est ce qui fait regarder jusqu'au bout, donc ce que YouTube récompense.
- **Pas de gabarit répété** : varier la forme d'un titre à l'autre (question, chiffre, « ce que dit la loi », comparaison). Voir « Contenu inauthentique » plus bas.
- Jamais de revenu promis, jamais « riche » ni « rentable » (règle de la chaîne), pas de MAJUSCULES intégrales.

## Description
- **[officiel] Les 2 premières lignes décident** : elles s'affichent avant le « …plus ». Elles résument la vidéo et contiennent le mot-clé principal. Maximum 5 000 caractères. **Une description unique par vidéo.**
- **[officiel]** Ajouter les chapitres horodatés (longs), les liens de playlists, les crédits.
- **Sources citées** (liste d'URL des faits vérifiés) : signal de sérieux pour les spectateurs, utile pour une chaîne de faits.
- Une question pour les commentaires (déjà dans `question_commentaires`). **Aucune mention d'IA, de voix de synthèse, de loi ni d'avertissement dans le titre, la description ou le texte parlé** (cap éditorial du 4 novembre 2026 : le propriétaire l'écrit dans la bio de la chaîne ; le champ technique `contenu_ia: true` reste, pour le workflow). Le validateur refuse ces mentions.
- **Longueur : 4 200 octets au plus** pour le texte écrit (YouTube coupe à 5 000 octets, chapitres, mots-clés et hashtags ajoutés compris).
- **[officiel] Hashtags : une dizaine, 15 au plus** (règle du propriétaire, 8 nov. 2026 : le maximum de hashtags pertinents). D'après l'aide YouTube, au-delà de 15 hashtags dans la description, YouTube les ignore TOUS ; il en affiche 3 au-dessus du titre (les premiers de la description) ; des hashtags sans rapport peuvent faire **retirer** la vidéo. L'ancienne règle « 3 au plus » est abandonnée : 3 était le nombre affiché, pas le maximum utile. Pas d'espaces dans un hashtag. Les 3 premiers sont les plus utiles ; `#Shorts` compte dans les 15. Le publieur complète à une dizaine à partir des `tags` quand le rédacteur en met moins, et retire ceux qui dépassent 15.
- **[pratique] Mots-clés** : une ligne « Mots-clés : expression, expression… » (8 à 15 expressions que les gens tapent), après le résumé et les sources ; le publieur l'ajoute à partir des `tags` si elle manque. À redire aussi dans le titre et les deux premières lignes.
- **[pratique] Chapitres d'un long** : des titres faits de mots que les gens tapent (« Vendre des bougies sur Vinted »), jamais « Business n°3 » ; ils apparaissent dans la recherche. Le premier à 00:00, au moins 3, chacun d'au moins 10 secondes sinon YouTube les ignore tous.
- Tags (3 à 15 exigés par le validateur) : peu d'effet connu, ils servent surtout aux fautes d'orthographe fréquentes ; mots simples, sans répétition.

## Shorts (et Shorts extraits d'un long)
- **[pratique]** Le critère clé est « vu ou ignoré » (*viewed vs swiped away*) : la part des gens qui regardent au lieu de glisser. Il se joue dans **les 2 premières secondes** : première phrase = la question ou le chiffre choc, jamais « Bonjour » ni présentation de la chaîne. Les repères chiffrés circulant (plus de 70 % de « vus » = bonne accroche) sont des ordres de grandeur d'outils tiers, **[à vérifier]**.
- Titre de Short court (50 caractères idéalement, 60 au plus : le validateur refuse au-delà), explicite, **mot-clé en tête** ; la description reprend la question, le lien vers le long, un bloc de mots-clés et une dizaine de hashtags (`#Shorts` en fait partie, ajouté par le publieur).
- Un Short extrait d'un long hérite des hashtags et des mots-clés du long (les écrire avec soin) et renvoie vers lui : « ▶ Vidéo complète : … » ; l'adresse remplace le titre dès que le long est envoyé.
- **Cadence (8 nov. 2026)** : 8 Shorts par jour sur 4 créneaux (08:00, 12:00, 18:00, 21:00 ; deux Shorts par créneau, à 15 minutes d'écart) + un long les lundi, mercredi, vendredi à 17:00. Les Shorts tirés d'un long passent d'abord, en alternant les longs d'origine ; la file n'enchaîne jamais deux titres de même forme ni deux gabarits identiques.
- Chaque Short doit se comprendre seul (c'est déjà la règle des Shorts extraits).

## Tester et apprendre (le plus efficace)
- **[pratique, à vérifier sur l'aide YouTube]** YouTube Studio propose un test A/B de titres et de miniatures (jusqu'à 3 variantes) ; le gagnant est choisi sur le **temps de visionnage**, pas sur les clics. Des variantes trop proches ne donnent pas de gagnant : tester des formulations vraiment différentes.
- Lire chaque semaine dans Studio : taux de clic des impressions, durée moyenne regardée, courbe de rétention, « vus vs ignorés » pour les Shorts. Garder les formes de titre qui gagnent.

## Attention : monétisation et « contenu inauthentique » (15/07/2025)
- **[pratique, sources secondaires, désaccords]** YouTube a renommé sa règle « contenu répétitif » en **« contenu inauthentique »** : les vidéos produites en masse, répétitives ou à gabarit identique peuvent perdre la monétisation, parfois **pour toute la chaîne**. Une voix de synthèse ou l'absence de visage n'est **pas** interdite en soi ; ce qui compte est la valeur ajoutée réelle et la variété.
- **Variété appliquée par le code (8 nov. 2026)** : cinq gabarits visuels qui tournent (fiche, cartes d'annonce, clips plein écran, compteur de gain, avant/après), une forme de titre et un style de miniature attribués à chaque sujet par `stock.py besoin`, un style de miniature différent pour les Shorts d'un même long, et un ordre de publication qui n'enchaîne jamais deux titres de même forme ni deux gabarits identiques. À 8 Shorts par jour, c'est ce qui sépare une chaîne éditoriale d'une production en série ; **surveille dans YouTube Studio** la monétisation et les avertissements « contenu inauthentique ».
- Ce qui protège cette chaîne : recherche réelle avec sources vérifiées par vidéo (déjà le cas), scripts différents à chaque fois, titres et descriptions non copiés d'un gabarit, miniatures variées, mention de l'IA, et **relecture humaine de temps en temps** (le tableau de bord signale les quarantaines).
- À relire sur la page officielle du Programme Partenaire YouTube avant de demander la monétisation.
