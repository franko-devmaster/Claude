# API transport.opendata.ch — mémo

API publique, gratuite, sans clé, basée sur les données horaires officielles suisses (CFF/SBB et autres entreprises de transport). Doc : https://transport.opendata.ch/docs.html

## `GET /v1/connections`

| Paramètre | Obligatoire | Exemple | Remarque |
|---|---|---|---|
| `from` | oui | `Lausanne` | nom, id de gare ou coordonnées |
| `to` | oui | `Bern` | |
| `via[]` | non | `via[]=Fribourg` | jusqu'à 5 |
| `date` | non | `2026-10-20` | défaut : aujourd'hui |
| `time` | non | `07:30` | défaut : maintenant |
| `isArrivalTime` | non | `1` | `0` = heure de départ (défaut), `1` = heure d'arrivée |
| `limit` | non | `5` | 1 à 16 |
| `direct` | non | `1` | uniquement les directs |
| `transportations[]` | non | `train` | `train`, `tram`, `ship`, `bus`, `cableway` |

Réponse (extrait utile) :

```json
{
  "connections": [{
    "from": { "station": {"name": "Lausanne"}, "departure": "2026-10-20T07:42:00+0200", "platform": "7" },
    "to":   { "station": {"name": "Bern"},     "arrival":   "2026-10-20T08:48:00+0200", "platform": "3" },
    "duration": "00d01:06:00",
    "transfers": 0,
    "products": ["IC 1"],
    "sections": [{
      "journey": { "category": "IC", "number": "1712", "name": "IC 1 712", "to": "St. Gallen" },
      "walk": null,
      "departure": { "station": {"name": "Lausanne"}, "departure": "...", "platform": "7" },
      "arrival":   { "station": {"name": "Bern"},     "arrival":   "...", "platform": "3" }
    }]
  }]
}
```

- Une section avec `walk` non nul (et `journey` nul) = trajet à pied entre deux arrêts.
- `duration` : format `00dHH:MM:SS`.
- Les champs peuvent être filtrés avec `fields[]=connections/from/departure` etc. (allège la réponse).

## `GET /v1/locations`

`/v1/locations?query=Fribourg&type=station` → liste `stations[]` avec `name`, `id`. Utile pour lever l'ambiguïté (Fribourg/Freiburg, Genève vs Genève-Aéroport, Biel/Bienne…).

## Prérequis réseau

Le domaine `transport.opendata.ch` doit être autorisé dans l'environnement où tourne Claude (WebFetch / accès réseau). S'il est bloqué, la skill bascule sur le lien sbb.ch + saisie manuelle.
