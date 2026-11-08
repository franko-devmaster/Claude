# Ma Cave — Project Instructions

## Overview

Ma Cave est une application mobile personnelle de gestion de cave à vin, augmentée par Claude. Un seul utilisateur, un iPhone 16 Pro, français. Elle stocke les vins de la cave, les dégustations et un profil de goûts ; Claude lit les étiquettes, juge un vin inconnu en magasin, propose l'accord avec un plat et synthétise les goûts.

Pas de backend. L'application est une PWA Angular installée sur l'écran d'accueil ; les données vivent sur le téléphone (IndexedDB) avec export et import JSON ; l'API Claude est appelée directement depuis l'application avec la clé de l'utilisateur.

Documents de référence :

- `docs/01-description-fonctionnelle.md` — périmètre, exigences, modèle de données, stack, plan d'itérations
- Maquette (7 écrans) : https://claude.ai/artifact/Q2iFq9qLcrrZuZPZXdjcY2

## Domaines fonctionnels

- Cave — liste groupée par couleur, filtres, recherche, fiche vin, stock (+1 acheté, −1 ouvert), à boire
- Ajouter — photo d'étiquette lue par Claude ou description libre, confirmation manuelle, référentiels pays / régions / cépages
- Dégustations — note 1 à 5, descripteurs aimés et gênants, commentaire, à racheter
- Profil de goûts — synthèse par Claude, cinq axes, cépages favoris, à éviter, corrections utilisateur
- Magasin — verdict d'affinité pour un vin inconnu, raisons + / − / i
- Accords — plat → choix principal dans la cave, alternatives, écartés
- Réglages — clé API Claude, export / import JSON, langue

## Tech Stack

- Frontend : Angular 22 (standalone + signals + OnPush), TypeScript strict, SCSS, PWA (`@angular/pwa`, service worker)
- UI : CSS maison à partir des tokens de la maquette. Pas d'Angular Material, pas de Bootstrap
- Forms : Reactive Forms typés. Pas de ngx-formly
- Stockage : IndexedDB via Dexie 4, une base `macave`, export / import JSON complet (vins, mouvements, dégustations, profil, verdicts, accords, photos en base64)
- IA : `@anthropic-ai/sdk` appelé depuis le navigateur (`dangerouslyAllowBrowser: true`), modèle `claude-opus-5-5`, sorties structurées (`output_config.format` + schéma JSON strict), vision pour les étiquettes et les plats
- i18n : `@ngx-translate`, français complet en v1, clés prêtes pour de / en, locale fr-CH
- Tests : Vitest pour la logique (datastore, calculs de stock, construction des prompts, parsing des réponses) ; Playwright pour les parcours critiques sur le viewport iPhone 16 Pro (402 × 874, deviceScaleFactor 3)
- Build / déploiement : GitHub Actions → GitHub Pages (site statique). Aucun conteneur, aucune base serveur

## Solution Structure

```
app/                         Projet Angular (racine du workspace Angular)
  src/app/
    pages/                   Un dossier par écran : cave/, fiche/, ajouter/, noter/, accords/, magasin/, gouts/, reglages/
    components/              Composants partagés : tab-bar, wine-row, color-dot, score-picker, chip-group, ai-hint
    datastore/               Classes signal-based : WineDatastore, TastingDatastore, ProfileDatastore, SettingsDatastore
    services/                ClaudeService (appels IA), BackupService (export/import), PhotoService (capture + redimensionnement)
    db/                      Dexie : schema.ts (tables, versions), repositories
    models/                  Types et enums du domaine
    ai/                      Prompts, schémas JSON de sortie, parseurs
    pipes/ directives/ utils/ constants/
  src/styles/                tokens.scss (couleurs, typographie, espacements), base.scss
  e2e/                       Tests Playwright
docs/                        Description fonctionnelle et décisions
.github/workflows/           ci.yml (lint + tests + build + déploiement Pages)
```

## Conventions Angular

### Pour tout le code

- Standalone components, pas de NgModules
- Signals partout : `signal()`, `computed()`, `input()`, `output()`, `linkedSignal()` si besoin
- Contrôle de flux `@if` / `@for` / `@switch` uniquement
- `inject()` au lieu de l'injection par constructeur
- `ChangeDetectionStrategy.OnPush` obligatoire
- Jamais `any` — `unknown` + type guards, ou types propres
- `takeUntilDestroyed`, `viewChild`, `resource()` ou `forkJoin` pour l'asynchrone
- Datastore pattern : une classe par agrégat dans `datastore/`, état en signals, persistance via les repositories Dexie, aucun appel Dexie depuis un composant
- Composants de page sans logique métier : ils lisent les datastores et appellent leurs méthodes
- Nommage : `XxxPage`, `XxxComponent`, `XxxDatastore`, `XxxService`, `XxxRepository` ; fichiers en kebab-case
- Couleurs et tailles uniquement via les tokens de `src/styles/tokens.scss` — pas de hex dans les composants

### Design system « Étiquette »

- Fond blanc `#FFFFFF`, surface secondaire `#F3F1EC`, encre `#17120F`, texte atténué `#6B625B`, filet `#ECE8E1`, bordure `#E3DED6`
- Un seul accent : bordeaux `#7A1F2E`, pour l'action principale, les notes et le signal IA
- Couleurs de vin : rouge `#7A1F2E`, blanc `#D4A72C`, rosé `#E08A9B`, bulles `#4F7F96`. Toujours accompagnées du libellé
- Typographie : Barlow Condensed 600 / 700 pour titres et millésimes ; Inter 400 / 500 / 600 pour le texte ; IBM Plex Mono 400 / 500 en capitales espacées pour les étiquettes de champ
- Cibles tactiles 44 px au minimum, contrastes 4.5:1, pas de barre d'état simulée, pas d'emoji, icônes SVG en trait
- L'IA est signalée par l'icône étincelle et le libellé « Conseil » ou « Verdict », jamais par un chat

### PWA / iOS

- Installable sur l'écran d'accueil (manifest, icônes, `apple-mobile-web-app-capable`, `viewport-fit=cover`, safe areas via `env(safe-area-inset-*)`)
- Photo via `<input type="file" accept="image/*" capture="environment">`, redimensionnée côté client à 1 280 px de grand côté en JPEG avant stockage et envoi
- Service worker activé, y compris sur Safari iOS : vérifier à chaque itération que l'installation et la mise à jour fonctionnent ; en cas de problème, désactiver par userAgent comme sur AquaPlan et le documenter ici
- IndexedDB est la source de vérité. Demander `navigator.storage.persist()` au premier lancement. Rappeler l'export si le dernier remonte à plus de 30 jours
- Consultation de la cave hors ligne ; les fonctions IA affichent un état explicite sans réseau

## Intégration Claude

- Un seul `ClaudeService` ; les prompts et schémas de sortie vivent dans `src/app/ai/`, un fichier par cas d'usage : `label-reading`, `store-verdict`, `pairing`, `taste-profile`
- Toujours `output_config.format` avec un schéma JSON strict ; jamais de parsing de texte libre
- Contexte envoyé : inventaire résumé + profil, placés en tête comme préfixe stable ; la requête variable en fin
- Images : JPEG base64 redimensionné, jamais l'original
- Gérer `stop_reason`, les erreurs réseau, les erreurs 401 (clé invalide → renvoi vers Réglages) et 429
- Le profil de goûts n'est recalculé qu'après une nouvelle dégustation ou une correction, jamais à l'ouverture
- Tester la logique autour des appels (construction des prompts, parsing, erreurs) avec des réponses fixtures ; aucun appel réel dans les tests

## Sécurité

Application personnelle, un seul utilisateur, mais la clé API a une valeur monétaire.

- La clé API est saisie dans Réglages et stockée dans IndexedDB sur l'appareil. Elle ne figure jamais dans le code, le dépôt, les logs ou l'export JSON
- Utiliser une clé dédiée à l'application avec une limite de dépense dans la Console Anthropic ; la révoquer si le téléphone est perdu
- Pas de `bypassSecurityTrust*`
- Les photos ne quittent l'appareil que vers l'API Anthropic, pour la durée de la requête
- Jamais commiter de secrets ; `.env` et fichiers locaux ignorés par Git

## Principes

- KISS — le plus simple qui marche
- YAGNI — uniquement ce qui est demandé maintenant
- DRY — extraire la duplication quand elle est prouvée (règle de trois)
- Changements minimaux — ne toucher que ce qui est strictement nécessaire
- Une itération = une tranche verticale testable sur le téléphone. Voir le plan dans `docs/01-description-fonctionnelle.md` § 10

## Tests

- Vitest obligatoire sur datastores, repositories, services, utilitaires et toute la couche `ai/`. Pas de logique sans test
- Nommage : `<méthode> should <attendu>` ou `<méthode> when <condition> should <attendu>`
- Sujet sous test : `sut`
- Playwright : un parcours par itération au minimum, sur le device `iPhone 16 Pro` de Playwright, `--trace off` sauf pour déboguer
- Vérification manuelle de l'UI sur le vrai téléphone via l'URL GitHub Pages à la fin de chaque itération

## Déploiements

| Cible | URL | Build | Data |
|---|---|---|---|
| localhost | http://localhost:4200 | `cd app && npm start` | IndexedDB du navigateur |
| Téléphone en local | http://<ip-du-mac>:4200 (même Wi-Fi), ou tunnel HTTPS pour tester la PWA | `npm start -- --host 0.0.0.0` | IndexedDB de Safari |
| GitHub Pages | https://franko-devmaster.github.io/Claude/ | push sur `main` → `.github/workflows/ci.yml` | IndexedDB du téléphone |

Angular doit être construit avec `--base-href /Claude/` pour Pages. Si l'application déménage dans un dépôt dédié, adapter `base-href` et l'URL ici.

### Workflow typique

```bash
# 1. Dev local
cd app && npm start
# 2. Tests
npm test && npx playwright test --trace off
# 3. Commit + push
git add ...
git commit -m "feat(cave): ..."
git push -u origin <branche>
# 4. Pull request vers main → CI → GitHub Pages
# 5. Ouvrir l'URL Pages sur l'iPhone, forcer la mise à jour de la PWA si besoin
```

## GitHub

- Repo : https://github.com/franko-devmaster/Claude
- Branche par défaut : `main`. Développement sur branches `claude/*`, fusion par pull request
- CI : `.github/workflows/ci.yml` (lint, tests, build, déploiement Pages)
- Pas de force-push sur `main`, pas de `--no-verify`

### Message de commit

- Format : `type(scope): description courte`
- Types : feat, fix, refactor, docs, test, chore
- Scopes : cave, ajouter, noter, gouts, accords, magasin, reglages, ai, db, pwa, ci, docs
- Terminer par la ligne Co-Authored-By demandée par le harness

### Avant de commit

- `git status` pour voir ce qui est staged
- Vérifier qu'aucune clé API ni photo personnelle ne part dans le dépôt

## Workflow Claude

Pas de suivi Jira ni de tests Xray. Tout reste dans Claude Code + GitHub.

Pour une itération :

1. Relire la tranche dans `docs/01-description-fonctionnelle.md` § 10 et la maquette
2. Écrire le code Angular et les tests Vitest ; un parcours Playwright
3. Lancer `npm test`, `npx playwright test --trace off`, `npm run build`
4. Commit + push, pull request vers `main`
5. Test manuel sur l'iPhone, retours dans la conversation, corrections

Si bloqué :

- Service worker iOS : vider le site dans Réglages Safari, réinstaller la PWA
- Données : exporter le JSON avant toute migration de schéma Dexie ; les migrations sont versionnées dans `db/schema.ts`
- API Claude : vérifier la clé, la limite de dépense et le message d'erreur exact avant de toucher au code
