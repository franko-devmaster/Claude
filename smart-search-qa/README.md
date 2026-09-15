# Smart Search — protocole de mesure de pertinence

Harnais de mesure de la pertinence de la Smart Search eGovHub, calibre pour
`tstkonto.bl.ch` (INT, R2026.3). Stdlib Python 3.9+, aucune dependance.

## Reference de ce qui est « pertinent »

La definition contractuelle n'est pas une opinion d'equipe : elle est dans
`EC/AI Search User Stories`. Ce protocole en derive trois contraintes qui changent
la lecture des chiffres, et deux ecarts a documenter.

| Critere d'acceptation | Consequence sur la mesure |
| --- | --- |
| Maximum 5 resultats affiches | Hit@5 est le plafond utile, pas un choix de metrique. |
| Les resultats sous 0.6 de confiance ne sont pas affiches | Un silence peut etre un effet de seuil, pas un echec de rappel. Sans acces aux scores bruts, on ne peut pas trancher — et on risque d'enrichir un catalogue pour un probleme de seuil. |
| Temps de reponse inferieur a 2 secondes | Mesure par la colonne `< 2 s`. Voir l'ecart ci-dessous. |
| DE, FR, EN **et variations dialectales** | Le corpus porte des cas FR, EN et trois cas en suisse-allemand (`lang: gsw`). |
| Commune de domicile pre-remplie pour un usager AGOV | Le comportement des slots change selon l'etat de session : la campagne se joue **deux fois**, deconnecte puis connecte. |

**Ecart de latence, a poser avant la campagne.** Le critere d'acceptation fixe
2 secondes. Le benchmark de concurrence mesure **~4.1-4.8 s pour un seul appel
LLM**, hors surcout Gateway et API, et une recherche complete compte environ trois
allers-retours. L'ecart est structurel, pas conjoncturel : la colonne `< 2 s` va
sortir a zero, et ce n'est pas une panne. Soit le critere est revu, soit la cible
d'infrastructure change — c'est une decision produit, pas un resultat de test.

**Ecart d'instrumentation.** L'AC « tableau de bord analytique » prevoit
explicitement la liste des requetes sans resultat, pour enrichir le catalogue.
Elle porte la mention *ne pas creer pour le moment*. C'est exactement la donnee
que cette campagne fabrique a la main.

## Ce que ce protocole mesure — et ce qu'il ne mesure pas

Il mesure **la chaine complete** : extraction LLM (theme / mots-cles / evenement
de vie) → retrieval (fusion RRF sur les listes K / V / L) → resolution des slots →
reformulation. Un mauvais score ne dit pas, seul, ou est le defaut.

Deux confusions a tenir a l'oeil, parce qu'elles rendent les chiffres
ininterpretables si on les ignore :

1. **Catalogue vs moteur.** La documentation d'architecture le dit : la qualite
   de recherche croit avec le catalogue de mots-cles. Une categorie entiere qui
   s'effondre mesure l'enrichissement du catalogue BL, pas le ranker. A verifier
   avant de conclure : exporter les prestations avec leurs `keywords` et
   `life events` depuis le back-office et compter le taux de couverture.
2. **Variance du LLM.** La sortie du modele d'extraction est probabiliste (c'est
   ecrit dans la page d'architecture : X memes questions peuvent donner Y
   reponses). Une passe unique ne distingue pas un mauvais classement d'un tirage
   defavorable. D'ou `--repeats 3` par defaut, et les colonnes de stabilite.
3. **Seuil de confiance.** A 0.6, le moteur masque. Un taux de silence eleve sur
   une categorie ne dit pas si la bonne prestation etait absente du classement ou
   presente sous le seuil. Demander a Michel l'acces aux scores bruts avant la
   campagne evite de conclure a l'envers.

## Etapes

### 1. Figer la verite terrain (prealable, non negociable)

`queries.json` porte `"gold_status": "TO_CONFIRM"`. Les champs `expect` sont des
motifs plausibles, pas une reference validee. Tant qu'ils ne sont pas confrontes
au catalogue reel de l'environnement teste, les scores mesurent l'accord avec
une hypothese, pas la pertinence.

Pour chaque cas : ouvrir le catalogue, identifier la ou les prestations qu'un
agent du guichet designerait comme la bonne reponse, et remplacer `expect` par
leurs intitules (ou leurs ids via `result_ids`). Les cas sans bonne reponse dans
le catalogue passent a `"expect_no_result": true` — ils testent alors l'honnetete
du systeme, ce qui est une mesure a part entiere.

Profiter du meme passage pour sortir le **denominateur** : les keywords et life
events sont geres comme des tags par tenant (`Id`, `Name`, `TenantId`) et
importables en masse par CSV depuis le back-office. Un export equivalent donne le
taux de prestations effectivement taguees — sans ce chiffre, un score bas sur
l'axe B n'est pas interpretable.

### 2. Capturer le contrat d'API

L'API `AiSearch` n'est pas joignable en direct : son ingress n'autorise que les
adresses sortantes de la Gateway eGovHub et du BackOffice. Il faut donc passer
par le portail.

Sur `tstkonto.bl.ch` : DevTools → Network → poser une question dans la Smart
Search → clic droit sur l'appel de recherche → **Copy as cURL**, coller dans un
fichier. Le reste est automatique :

```bash
python3 from_curl.py --curl-file appel.txt --query "Betreibungsregisterauszug"
```

`--query` est le texte reellement saisi dans le champ de recherche : il permet
de reperer sans ambiguite le champ qui porte la question. Le script isole la
requete, ecarte les en-tetes propres au navigateur (`sec-*`, `content-length`,
`accept-encoding`), conserve ceux qui portent la session et le tenant, remplace
la question par `{{query}}`, puis **envoie une requete de sondage et deduit les
chemins d'extraction** en inspectant la reponse reelle. Il ecrit un `config.json`
complet, template de relance compris.

Si le sondage renvoie 401 ou 403, la session du cURL a expire : recapturer
l'appel. `--no-probe` ecrit la partie requete et laisse `extract` a completer.

```bash
python3 run_tests.py --dry-run       # affiche le plan, n'appelle rien
python3 run_tests.py --smoke         # un seul cas: valide le cablage
```

`config.example.json` reste la reference de la structure attendue, pour une
configuration manuelle.

### 3. Lancer la campagne

```bash
python3 run_tests.py --repeats 3 --interval 8
```

46 cas x 3 repetitions ≈ 140 appels, ~20 minutes a 8 s d'intervalle.

**La serialisation n'est pas une precaution de principe, c'est la capacite reelle
d'INT.** Le controle d'admission fixe `MaxConcurrency` par instance, avec une
repartition decidee **DEV 1 / TEST 1 / PROD 10** sur un plafond GPU mesure a 12.
L'instance de test traite donc **une requete a la fois** ; la file de priorite
(`X-Ai-Search-Priority` : 10 PROD, 50 INT, 90 DEV, le plus bas gagne) sert INT
apres la production. Paralleliser depuis INT n'accelere rien : les appels
s'empilent jusqu'au `WaitTimeout`, puis tombent en 503.

Le harnais serialise, ajoute un jitter, **honore l'en-tete `Retry-After`**,
distingue les deux rejets — 429 debit refuse par le rate limiter, 503 file du
modele saturee — et s'arrete apres 3 erreurs serveur consecutives. Ne pas
descendre `--interval` sous 5 s, et ne pas paralleliser.

**Un appel rejete n'est pas un echec de pertinence.** Les enregistrements 429/503
sont marques `admission_rejected` et exclus du scoring, puis comptes a part dans
l'en-tete du rapport. Sans cela, une rafale de rate limiting se lirait comme un
effondrement de la pertinence.

Ne pas confondre cette campagne avec un test de charge : le benchmark de
concurrence exige d'isoler l'ingress au loopback et de couper l'auto-sync Argo CD.
Rien de tel ici — on mesure la pertinence sur un service en fonctionnement normal.

Pour etaler la charge, la campagne est decoupable par categorie :

```bash
python3 run_tests.py --category A --category B   # puis C, D, E plus tard
```

### 4. Scorer

```bash
python3 score.py --run runs/<timestamp>
```

Produit `report.md` (synthese par categorie + detail par requete) et
`metrics.csv`. Les reponses brutes restent dans `results.jsonl` : tout chiffre
du rapport est re-verifiable.

## Corpus

| Cat. | Intitule | Cas | Ce que la categorie eprouve |
| --- | --- | --- | --- |
| A | Prestation precise | 10 | Chemin nominal : l'usager nomme la prestation. Inclut 2 requetes FR/EN sur catalogue DE. |
| B | Evenement de vie | 10 | Le poids `w_L` de la famille d'evenement de vie, et la couverture du tagging life-event. |
| C | Prestation communale | 8 | La resolution du slot commune : le systeme demande-t-il la commune, et filtre-t-il ensuite ? |
| D | Besoin vague / indirect | 12 | Le cas difficile : le document n'est jamais nomme. Repose sur la recherche vectorielle sur les descriptions. |
| E | Robustesse | 6 | Fautes de frappe, ambiguite (clarification attendue), hors-domaine, injection de prompt, intentions multiples. |

## Metriques

| Metrique | Definition | Ce qu'elle revele |
| --- | --- | --- |
| Hit@1 / @3 / @5 | La prestation attendue est-elle dans le top k | Rappel utile |
| MRR | Inverse du rang du premier resultat pertinent | Qualite du classement |
| nDCG@5 | Gain cumule actualise | Classement, en tenant compte de la position |
| Stab. top-3 | Jaccard moyen des top-3 entre repetitions | Variance de l'ensemble retourne |
| Stab. rang 1 | Part des repetitions donnant le meme 1er resultat | Variance percue par l'usager |
| Sans resultat | Part des appels ne retournant rien | Silences du moteur |
| Comportement | Verdict OK/NOK sur les cas E et D12 | Clarification, refus, non-hallucination |

Grille de lecture :

- **Hit@1 bas + Hit@3 haut** → le bon service remonte mais est mal classe :
  ponderation de la fusion, pas rappel.
- **Hit@3 bas sur toute une categorie** → enrichissement du catalogue.
- **Stabilite basse** → variance d'extraction : reformuler ou contraindre le
  prompt systeme, ou augmenter le nombre de repetitions avant toute comparaison.

## Limites connues

- Le corpus compte 49 cas, dont 3 en suisse-allemand. La tolerance dialectale est
  un critere d'acceptation, pas un bonus : l'echec de ces trois cas est un ecart
  contractuel.
- La campagne mesure **INT**, avec l'integration des prestations communales
  installee recemment et des problemes d'horodatage encore ouverts. Les ecarts
  avec la PROD ne sont pas imputables au moteur.
- La Smart Search **n'est pas activee en PROD** (decision de la release 2026.3) :
  aucune donnee d'usage reel ne peut servir de contre-mesure a ces resultats.
- Aucune boucle de retour citoyen n'existe encore (« Burger Feedback Losung » est
  un point ouvert). Ce harnais est donc, aujourd'hui, la seule mesure disponible.
