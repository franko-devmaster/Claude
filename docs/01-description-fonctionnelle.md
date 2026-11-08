# Ma Cave — description fonctionnelle v0.1

Application mobile personnelle de gestion de cave à vin, augmentée par Claude.
Document de cadrage à valider avant développement.

Maquette interactive (7 écrans) : https://claude.ai/artifact/Q2iFq9qLcrrZuZPZXdjcY2

## 1. Vision

Une seule personne, une cave, un téléphone. Trois moments d'usage :

| Moment | Besoin | Écran |
|---|---|---|
| À la cave | Savoir ce que j'ai, ajouter ou retirer une bouteille en quelques secondes | Ma cave, Fiche vin, Ajouter |
| À table | Noter ce que je bois pour que l'app apprenne mes goûts ; choisir le vin qui va avec le plat | Noter, Accords |
| En magasin | Savoir si ce vin inconnu me plaira avant de l'acheter | Vérifier en magasin |

Principe directeur : chaque action courante tient en trois gestes au plus. L'IA ne se présente jamais comme un chat ; elle est un conseil contextuel, signalé par une icône unique, à quatre endroits précis.

## 2. Périmètre v1

Dans le périmètre :

- Inventaire des vins avec quantités, emplacement, prix payé, fenêtre de garde.
- Ajout par photo d'étiquette (lecture IA) ou par description libre, puis confirmation manuelle.
- Mouvements de stock : +1 acheté, −1 ouvert.
- Notation après ouverture : note 1 à 5, descripteurs aimés et gênants, commentaire, « à racheter ».
- Profil de goûts déduit et corrigeable par l'utilisateur.
- Verdict d'affinité pour un vin inconnu (photo ou description).
- Accord plat → vins de la cave, avec alternatives et vins écartés.
- Recherche et filtres (couleur, pays, région, cépage, à boire).

Hors périmètre v1 : multi-utilisateurs, partage, prix du marché, scan de code-barres, suivi de température, import depuis Vivino ou autre.

## 3. Exigences fonctionnelles

### E1 — Cave

- F1.1 Afficher la liste des vins groupés par couleur, avec millésime, nom, domaine, région et nombre de bouteilles.
- F1.2 Filtrer par couleur ; rechercher sur nom, domaine, cépage, région.
- F1.3 Signaler les vins « à boire maintenant » quand l'année courante atteint la fenêtre de garde.
- F1.4 Fiche vin : photo d'étiquette, données descriptives, stock, emplacement, prix, conseil IA de service et d'accord, historique des dégustations.
- F1.5 Actions de stock depuis la fiche : « J'en ouvre une » (−1 et ouverture de l'écran Noter) et « +1 achetée ».
- F1.6 Édition manuelle de tout champ.

### E2 — Ajouter un vin

- F2.1 Prendre une photo de l'étiquette ; l'IA extrait nom, domaine, millésime, couleur, pays, région, cépage(s), degré, mentions utiles.
- F2.2 Afficher les champs pré-remplis pour vérification ; aucun ajout sans confirmation explicite.
- F2.3 Sans photo : saisir une phrase (« Cornalin Germanier 2019 ») et obtenir la même pré-saisie.
- F2.4 Si le vin existe déjà en cave, proposer d'augmenter la quantité plutôt que de créer un doublon.
- F2.5 Référentiels alimentés automatiquement : couleurs (fixe), pays, régions, cépages. L'utilisateur peut corriger une entrée.

### E3 — Noter une dégustation

- F3.1 Note de 1 à 5 avec libellés aux extrémités (« Pas pour moi » / « J'en veux encore »).
- F3.2 Descripteurs positifs (fruité, épicé, boisé, tanins souples, minéral, puissant, léger, long) et négatifs (trop acide, trop boisé, finale courte, alcool marqué, bouchonné). Liste extensible.
- F3.3 Commentaire libre court, contexte facultatif (plat, occasion).
- F3.4 Interrupteur « à racheter ».
- F3.5 Chaque enregistrement déclenche la mise à jour du profil de goûts.

### E4 — Profil de goûts

- F4.1 Synthèse en une phrase, produite par l'IA à partir de l'ensemble des dégustations.
- F4.2 Cinq axes notés sur 10 : fruit, fraîcheur, épices, puissance, boisé.
- F4.3 Cépages qui marchent, profils à éviter.
- F4.4 L'utilisateur peut contester une déduction ; la correction est mémorisée et pèse dans les synthèses suivantes.
- F4.5 Indiquer le nombre de dégustations sur lequel repose le profil. En dessous de 5 notes, afficher un profil « provisoire ».

### E5 — Vérifier en magasin

- F5.1 Photo d'étiquette ou description → identification du vin.
- F5.2 Verdict en trois niveaux (« Devrait vous plaire », « Mitigé », « Probablement pas pour vous ») et score d'affinité sur 10.
- F5.3 Trois à quatre raisons, signées + / − / i, qui citent des faits du profil et de la cave (« même domaine que votre Cornalin noté 5 », « 14 rouges déjà en cave »).
- F5.4 Actions : « J'achète, l'ajouter » (enchaîne sur l'écran Ajouter pré-rempli) ou « Je passe ».
- F5.5 Chaque verdict est journalisé ; si l'utilisateur achète puis note le vin, l'écart entre verdict et note sert à calibrer.

### E6 — Accords

- F6.1 Saisir le plat en texte, ou photographier le plat ou la recette.
- F6.2 Résultat : un choix principal dans la cave avec justification en deux phrases et conseil de service, puis deux alternatives, puis les vins écartés avec la raison.
- F6.3 Le choix tient compte du profil de goûts, des stocks et de la fenêtre de garde (privilégier les vins à boire).
- F6.4 Si rien ne convient en cave, le dire clairement et proposer un type de vin à acheter.
- F6.5 Un geste pour passer du choix à la fiche, puis à « J'en ouvre une ».

### E7 — Transverse

- F7.1 Consultation de la cave hors ligne ; les fonctions IA exigent le réseau et l'indiquent.
- F7.2 Sauvegarde des données et export (CSV ou JSON).
- F7.3 Interface en français ; structure prête pour DE/EN sans refonte.

## 4. Exigences non fonctionnelles

- Simplicité : aucun écran ne demande plus de six champs ; aucune action courante au-delà de trois gestes.
- Temps de réponse : lecture d'étiquette et verdict sous 8 s ; accord sous 10 s ; affichage d'un état d'attente explicite.
- Confidentialité : la clé API Claude ne quitte jamais le serveur ; les photos transitent vers l'API pour la requête et ne sont stockées que dans la base de l'utilisateur.
- Coût : cible sous CHF 5 par mois pour un usage de 50 à 80 appels IA (estimation détaillée au § 6).
- Accessibilité : contrastes 4.5:1, cibles tactiles 44 px, code couleur toujours doublé d'un libellé.

## 5. Modèle de données

```
Wine            id, name, producer, vintage, color (rouge|blanc|rosé|bulles),
                country, region, appellation, grapes[], alcohol, sweetness,
                drinkFrom, drinkUntil, labelPhotoUrl, location, notes, createdAt
StockMovement   id, wineId, delta (+1|-1), reason (achat|ouverture|casse|cadeau),
                pricePaid, date
Tasting         id, wineId, score (1-5), likedDescriptors[], dislikedDescriptors[],
                comment, context, rebuy (bool), date
TasteProfile    id, summary, axes {fruit, freshness, spice, power, oak},
                favoriteGrapes[], avoidPatterns[], basedOnTastings, generatedAt
ProfileOverride id, field, userValue, reason, date
Verdict         id, wineIdentified (json), affinity (0-10), level, reasons[],
                outcome (acheté|passé), date
PairingRequest  id, dish, photoUrl, topPickWineId, alternatives[], rejected[], date
Ref*            Country, Region, Grape : tables de référence alimentées à l'ajout
```

Le stock courant d'un vin est la somme de ses mouvements ; on garde l'historique plutôt qu'un compteur.

## 6. Intégration Claude

Quatre appels, tous via un backend qui détient la clé API. Aucun chat libre en v1.

| Cas | Entrée | Sortie structurée | Modèle |
|---|---|---|---|
| Lecture d'étiquette | image + liste des vins déjà en cave | objet Wine partiel + confiance par champ + doublon probable | claude-opus-5-5 (vision) |
| Verdict magasin | image ou texte + profil + inventaire résumé | niveau, score, raisons[] | claude-opus-5-5 |
| Accord | plat (texte ou image) + inventaire + profil | choix, alternatives[], écartés[], service | claude-opus-5-5 |
| Synthèse du profil | toutes les dégustations + corrections utilisateur | TasteProfile | claude-opus-5-5 |

Choix techniques :

- Sorties structurées (`output_config.format`) avec schéma JSON strict : l'app ne parse jamais de texte libre.
- Le profil et l'inventaire résumé sont envoyés comme préfixe stable pour bénéficier du cache de prompt.
- La synthèse du profil n'est recalculée qu'après une nouvelle dégustation, jamais à l'ouverture de l'app.
- Haiku 5.5 reste une option pour la lecture d'étiquette seule si le coût devait compter ; à mesurer sur de vraies étiquettes avant de trancher.

Ordre de grandeur de coût (tarifs API publics, Opus 5.5 : 4 USD / M tokens en entrée, 20 USD / M en sortie) :

| Appel | Tokens entrée | Tokens sortie | Coût |
|---|---|---|---|
| Lecture d'étiquette (photo ≈ 1 500 tokens + contexte) | ≈ 3 000 | ≈ 400 | ≈ 0,02 USD |
| Verdict ou accord | ≈ 4 000 | ≈ 600 | ≈ 0,03 USD |
| Synthèse du profil (50 dégustations) | ≈ 6 000 | ≈ 500 | ≈ 0,03 USD |

À 60 appels par mois : moins de 2 USD. Le coût n'est pas un critère de conception.

## 7. Options techniques et recommandation

Constat préalable : le dépôt est vide. Il ne contient aucun fichier CLAUDE.md ni consigne Angular / .NET. Si de telles consignes existent ailleurs, il faut les ajouter au dépôt avant le développement.

| | A · iOS natif SwiftUI | B · PWA Angular + API .NET | C · Capacitor (Angular empaqueté iOS) |
|---|---|---|---|
| Sensation native, caméra, hors ligne | Excellente | Bonne (caméra via la caméra système, pas de viseur intégré ; hors ligne via service worker) | Très bonne |
| Installation | Xcode + Mac obligatoires. Sans compte développeur payant, l'app expire après 7 jours ; avec le compte (99 USD/an), TestFlight 90 jours renouvelables | Ouvrir une URL, « Ajouter à l'écran d'accueil ». Aucun store | Comme A |
| Réutilisation de votre stack | Nulle | Totale (Angular, .NET) | Forte |
| Ce que je peux faire depuis cet environnement | Écrire le code Swift, mais ni compiler ni tester : chaque itération passe par vous et Xcode | Construire, lancer, tester de bout en bout, y compris le rendu mobile | Code Angular testable ici ; build iOS chez vous |
| Backend | Nécessaire malgré tout (clé API, synchronisation) | Inclus | Nécessaire |

Recommandation : **option B pour la v1**, avec une API .NET pensée comme contrat stable. Si la sensation native manque à l'usage, l'option C réutilise le même code Angular et la même API ; l'option A ne réutilise que l'API.

Le point qui pèse le plus : avec A, je produis du code que je ne peux pas vérifier. Pour une v1 qu'on veut itérer vite, c'est un frein réel.

Pile proposée pour B :

- Front : Angular 20, standalone components, Angular Material allégé ou CSS maison selon la maquette, PWA (service worker, manifest), `<input type="file" capture="environment">` pour la photo.
- API : .NET 9 minimal API, EF Core, PostgreSQL (ou SQLite au départ), SDK Anthropic C#.
- Hébergement : Azure App Service ou Container Apps, un seul environnement, authentification par un seul compte (Entra ID personnel ou lien magique).
- Stockage photos : Azure Blob, redimensionnées côté client avant envoi.

## 8. Décisions à prendre avant le développement

1. Option technique A, B ou C (§ 7).
2. Nom de l'application. « Ma Cave » est un nom de travail.
3. Hébergement : Azure personnel, ou autre ?
4. Faut-il un viseur caméra intégré (impose A ou C) ou la caméra système suffit-elle ?
5. Langue : français seul en v1, confirmé ?
6. Faut-il garder l'historique complet des verdicts magasin pour la calibration (F5.5), ou est-ce de la sur-ingénierie pour un usage personnel ?

## 9. Prochaines étapes

1. Validation de ce document et de la maquette, avec vos corrections.
2. Décisions du § 8.
3. Ajout au dépôt d'un CLAUDE.md avec vos conventions Angular / .NET.
4. Développement par tranches verticales : E1 + E2 (cave et ajout), puis E3 + E4 (notes et profil), puis E6 (accords), puis E5 (magasin).
