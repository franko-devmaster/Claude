---
name: cff-horaire-outlook
description: Recherche d'horaires de train CFF/SBB (réseau suisse de transports publics), présentation des alternatives, choix par l'utilisateur, puis création du rendez-vous correspondant dans le calendrier Outlook de François Charrière. Utiliser dès que l'utilisateur mentionne « horaire CFF », « train pour … », « SBB Fahrplan », « je dois être à Berne à 9h », « trouve-moi un train », « bloque le trajet dans mon agenda », « réserve le trajet dans Outlook », ou toute demande combinant un déplacement en train en Suisse et le calendrier. S'applique aussi au trajet retour et aux allers-retours.
---

# Horaire CFF → rendez-vous Outlook

Workflow en 4 étapes : **comprendre la demande → chercher les connexions → faire choisir → créer le rdv Outlook**.
Ne jamais créer l'événement sans choix explicite de l'utilisateur.

## Outils requis

| Besoin | Outil |
|---|---|
| Horaires | `WebFetch` sur l'API officielle open data `transport.opendata.ch` (données CFF / opentransportdata.swiss). Voir `references/api-transport-opendata.md`. |
| Conflits agenda (optionnel) | `mcp__Microsoft_365__outlook_calendar_search` |
| Création du rdv | `mcp__Microsoft_365__outlook_create_event` |

Les outils Microsoft 365 sont souvent « différés » : les charger via `ToolSearch` (`select:mcp__Microsoft_365__outlook_create_event,mcp__Microsoft_365__outlook_calendar_search`) avant le premier appel.

**Pourquoi pas sbb.ch directement ?** Le site est une application JavaScript : un fetch HTML ne renvoie pas les horaires. L'API `transport.opendata.ch` expose les mêmes données horaires officielles en JSON, sans clé. Ne recourir au navigateur (Claude in Chrome) sur sbb.ch qu'en dernier recours.

## Étape 1 — Comprendre la demande

Extraire :
- **Départ** et **arrivée** (gare, arrêt ou adresse). Défaut départ si non précisé : demander (ne pas deviner le domicile).
- **Date** : interpréter les dates relatives (« demain », « jeudi ») par rapport à la date du jour ; fuseau `Europe/Zurich`.
- **Heure** et **sens** :
  - « partir vers 8h » → heure de départ (`isArrivalTime=0`)
  - « être à Berne à 9h », « pour une séance à 9h » → heure d'arrivée (`isArrivalTime=1`). Si c'est une séance, prévoir une marge : viser une arrivée ≥ 10 min avant l'heure annoncée et le dire.
- **Via** (optionnel), **retour** (optionnel).

Si départ, arrivée ou date manquent → poser **une seule** question regroupant tout ce qui manque. Le reste a des valeurs par défaut.

## Étape 2 — Chercher les connexions

Appeler `WebFetch` sur :

```
https://transport.opendata.ch/v1/connections?from=<DEPART>&to=<ARRIVEE>&date=<YYYY-MM-DD>&time=<HH:MM>&isArrivalTime=<0|1>&limit=5
```

(URL-encoder les noms : `Lausanne`, `Bern`, `Fribourg%2FFreiburg`, `Gen%C3%A8ve-A%C3%A9roport`…)

Prompt WebFetch à utiliser (le modèle de résumé doit rendre les données brutes, pas une synthèse) :

> Pour chaque élément de `connections`, liste sans rien omettre ni arrondir : heure de départ (from.departure), voie de départ (from.platform), heure d'arrivée (to.arrival), voie d'arrivée (to.platform), durée (duration), nombre de correspondances (transfers), produits (products), et pour chaque section avec `journey` : catégorie + numéro (journey.category, journey.number), gare et heure de départ, gare et heure d'arrivée, voie. Indique aussi from.station.name et to.station.name. Si `connections` est vide ou s'il y a une erreur, dis-le exactement.

Gestion des cas :
- **Gare ambiguë / introuvable** : appeler `https://transport.opendata.ch/v1/locations?query=<texte>&type=station` et proposer les 3 premières correspondances.
- **Moins de 3 résultats utiles** (ex. arrivée trop tardive) : relancer une fois en décalant l'heure de ±30 min.
- **API indisponible** (erreur réseau, domaine bloqué) : le dire clairement, donner le lien de recherche
  `https://www.sbb.ch/fr?von=<DEPART>&nach=<ARRIVEE>&date=<YYYY-MM-DD>&time=<HH:MM>` et proposer de saisir manuellement la connexion choisie (heures + train) pour créer quand même le rdv. Ne jamais inventer d'horaire.

## Étape 3 — Présenter les alternatives

Tableau compact, numéroté, max 5 lignes, trié par heure de départ :

| # | Départ | Arrivée | Durée | Corresp. | Trains | Voie |
|---|---|---|---|---|---|---|
| 1 | 07:42 Lausanne | 08:48 Bern | 1h06 | 0 | IC 1 712 | 7 |
| 2 | 08:12 Lausanne | 09:18 Bern | 1h06 | 0 | IC 1 716 | 5 |

Puis en une ou deux lignes :
- recommander l'option la plus adaptée (marge avant séance, direct vs correspondance) et pourquoi ;
- signaler les correspondances < 5 min (risque) ;
- si `outlook_calendar_search` est disponible, vérifier la plage du trajet et signaler un conflit éventuel.

Terminer par : « Laquelle je bloque dans ton agenda ? (numéro) ». **Attendre la réponse.**

## Étape 4 — Créer le rendez-vous Outlook

Appeler `mcp__Microsoft_365__outlook_create_event` avec :

| Champ | Valeur |
|---|---|
| `subject` | `🚆 <Départ> → <Arrivée> (<train principal>)` — ex. `🚆 Lausanne → Bern (IC 1 712)` |
| `start` | `{ "dateTime": "<YYYY-MM-DDTHH:MM:00>", "timeZone": "Europe/Zurich" }` = heure de départ |
| `end` | idem = heure d'arrivée |
| `location` | `<Gare de départ>, voie <X>` |
| `showAs` | `busy` |
| `sensitivity` | `normal` |
| `body` (text) | détail de chaque section : `07:42 Lausanne (voie 7) → 08:48 Bern (voie 3) · IC 1 712`, correspondances avec temps de transfert, puis `Durée : 1h06 · Correspondances : 0` et `Source : horaire CFF (transport.opendata.ch), état au <date du jour>. Vérifier les perturbations sur sbb.ch.` |

Règles :
- **Jamais d'`attendees`** (sinon Outlook envoie des invitations).
- Ne pas mettre `isOnlineMeeting`.
- Les heures de l'API sont au format `2026-10-20T07:42:00+0200` : reprendre l'heure locale telle quelle, supprimer l'offset, fuseau `Europe/Zurich`.
- Trajet de nuit franchissant minuit : la date de fin est celle de l'arrivée.

Après création : confirmer en une ligne (titre, date, heures) avec le `webLink` renvoyé.
Puis proposer **une seule fois** : « Je cherche aussi le retour ? »  → si oui, reprendre à l'étape 2 en inversant départ/arrivée (demander l'heure).

## Limites à rappeler si pertinent

- L'horaire est théorique (planifié) ; retards et suppressions ne sont pas reflétés dans le rdv.
- Pas d'achat de billet : la skill ne fait que bloquer le temps de trajet.
