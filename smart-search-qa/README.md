# Smart Search — protocole de mesure de pertinence

Harnais de mesure de la pertinence de la Smart Search eGovHub, calibre pour
`tstkonto.bl.ch` (INT, R2026.3). Stdlib Python 3.9+, aucune dependance.

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

### 2. Capturer le contrat d'API

L'API `AiSearch` n'est pas joignable en direct : son ingress n'autorise que les
adresses sortantes de la Gateway eGovHub et du BackOffice. Il faut donc passer
par le portail.

Sur `tstkonto.bl.ch` : DevTools → Network → poser une question dans la Smart
Search → `Copy as cURL` sur l'appel de recherche. Reporter URL, en-tetes
(cookie de session, tenant, CSRF) et forme du corps dans `config.json`, en
partant de `config.example.json`. Verifier les chemins d'extraction : ce sont
eux qui decident de ce que le scoring lit comme « resultat ».

```bash
cp config.example.json config.json   # puis editer
python3 run_tests.py --dry-run       # affiche le plan, n'appelle rien
python3 run_tests.py --smoke         # un seul cas: valide le cablage
```

### 3. Lancer la campagne

```bash
python3 run_tests.py --repeats 3 --interval 8
```

46 cas x 3 repetitions ≈ 140 appels, ~20 minutes a 8 s d'intervalle.

**Le debit par defaut est volontairement bas.** L'inference tourne sur un noeud
GPU A30 mutualise et l'environnement INT partage la file de priorite. Le harnais
serialise les appels, ajoute un jitter, applique un backoff exponentiel sur
429/5xx et **s'arrete de lui-meme apres 3 echecs serveur consecutifs**. Ne pas
descendre `--interval` sous 5 s, et ne pas paralleliser.

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

- La campagne mesure **INT**, avec l'integration des prestations communales
  installee recemment et des problemes d'horodatage encore ouverts. Les ecarts
  avec la PROD ne sont pas imputables au moteur.
- La Smart Search **n'est pas activee en PROD** (decision de la release 2026.3) :
  aucune donnee d'usage reel ne peut servir de contre-mesure a ces resultats.
- Aucune boucle de retour citoyen n'existe encore (« Burger Feedback Losung » est
  un point ouvert). Ce harnais est donc, aujourd'hui, la seule mesure disponible.
