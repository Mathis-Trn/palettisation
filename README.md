# Palettisation 3D

Portail web de simulation de palettisation 3D : import ou saisie d'une commande de cartons,
calcul automatique de la répartition sur des palettes (transport routier, maritime ou aérien),
visualisation 3D interactive, export des résultats et estimation du chargement dans un véhicule
ou un conteneur.

## Architecture

Le moteur de palettisation est un **backend Python headless**, entièrement découplé du front :
utilisable comme bibliothèque, en CLI, ou via une API HTTP versionnée. Le frontend Next.js ne
contient **aucune** logique de packing, de collision, de rotation, de support, de scoring ou de
chargement transport — il envoie les données brutes au backend et affiche exactement ce qu'il
reçoit.

```
frontend/  (Next.js 16 / React 19 / React Three Fiber)
     │ HTTP/JSON (fetch, voir frontend/src/lib/api/)
     │  POST /api/v1/palletization-jobs   → 202, jobId (répond en < 1s)
     │  GET  /api/v1/palletization-jobs/{id}  → statut, résultat une fois "succeeded" (polling)
     ▼
backend/   (FastAPI, /api/v1/*)
     │ JobManager (ProcessPoolExecutor, hors boucle asyncio)
     ▼
palletizer.application.services  (service headless, aucune dépendance FastAPI ni au gestionnaire de jobs)
     │ port PackingEngine
     ▼
palletizer.packing  (adaptateur py3dbp + règles métier Python)
```

Le calcul (potentiellement long sur un ordre volumineux) s'exécute en tâche de fond côté backend,
jamais dans une requête HTTP maintenue ouverte : le frontend crée un job, puis interroge
périodiquement son statut (`usePalletizationJob`) et affiche un loader accessible (spinner + temps
écoulé, sans pourcentage inventé) pendant l'attente. Voir `backend/README.md`, section "Jobs
asynchrones", pour l'architecture complète (annulation, expiration, déduplication, limites).

- **`frontend/`** — application Next.js existante (tableau de bord, configuration, commande,
  résultats, visualisation 3D, transport), adaptée pour consommer l'API au lieu de calculer
  localement. Voir `frontend/` (README embarqué dans ce fichier, section Frontend ci-dessous).
- **`backend/`** — package Python `palletizer` : domaine pur, adaptateur
  [py3dbp](https://pypi.org/project/py3dbp/) (bin packing 3D), import CSV métier réel, service
  applicatif, CLI (Typer), API (FastAPI). Voir `backend/README.md`.
- **`contracts/`** — `openapi.json` (généré depuis FastAPI) et des exemples de requête/réponse
  JSON (`contracts/examples/`).
- **`docker-compose.yml`** — orchestration des deux services pour le développement local.

Le moteur (`backend/src/palletizer/packing`, `application`) implémente une heuristique de type
**points extrêmes** (Extreme Points) autour de py3dbp, portée fidèlement depuis l'ancien moteur
TypeScript (même algorithme, mêmes scores, même déterminisme), volontairement **pas** qualifiée
d'intelligence artificielle ni de solveur garantissant l'optimum mathématique — voir
[Limites connues](#limites-connues).

## ⚠️ Avertissement sur la stabilité physique

Le contrôle de support et de stabilité implémenté dans le moteur (ratio de surface de contact,
centre de gravité projeté) est une **approximation logicielle**. Il ne simule ni les forces
dynamiques du transport (freinage, virages, vibrations), ni le comportement réel des matériaux
d'emballage, ni le calage. **Il ne constitue en aucun cas une certification physique du
chargement.** Toute décision de chargement réel doit être validée par un professionnel qualifié
selon les règles et normes applicables (ex. code de la route, consignes du transporteur).

## Démarrage

### A. Développement complet (recommandé)

```bash
docker compose up --build
```

Puis ouvrir [http://localhost:3000](http://localhost:3000). Le backend écoute sur
[http://localhost:8000](http://localhost:8000) (`/health`, `/api/v1/capabilities`, documentation
interactive sur `/docs`).

**Piège classique** : `NEXT_PUBLIC_PALLETIZER_API_URL` doit être une URL joignable depuis le
**navigateur** de l'utilisateur, jamais le nom de service interne docker-compose
(`http://backend:8000` ne fonctionnera pas dans le navigateur — utiliser `http://localhost:8000`,
qui fonctionne car le port est publié sur l'hôte).

Alternative sans Docker, deux terminaux :

```bash
# terminal 1
cd backend && uv sync --dev && uv run uvicorn palletizer.api.main:app --reload --port 8000
# terminal 2
cd frontend && npm install && npm run dev
```

### B. Backend headless seul (sans front, sans serveur si besoin)

```bash
cd backend
uv sync --dev
uv run uvicorn palletizer.api.main:app --host 0.0.0.0 --port 8000   # avec API
# ou, sans aucun serveur :
uv run palletizer capabilities
uv run palletizer optimize-csv commande.csv --order SO265669-X82921 --output -
```

Voir `backend/README.md` pour l'usage en bibliothèque Python pure (sans FastAPI).

### C. Frontend seul, backend distant

```bash
cd frontend
NEXT_PUBLIC_PALLETIZER_API_URL=https://backend.exemple.fr npm run dev
```

## Commandes de test

```bash
# Backend
cd backend
uv run ruff check .
uv run mypy src
uv run pytest --cov=src/palletizer

# Frontend
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e    # démarre automatiquement le backend réel ET le frontend (voir playwright.config.ts)
```

## Frontend — structure

```
frontend/src/
  domain/            Types du modèle de rendu (dimensions, positions, résultats), Zod pour la
                      validation de saisie manuelle. Aucune logique de packing.
  lib/
    api/             Client HTTP typé vers le backend :
                      contract-types.ts     (types "sur le fil", reflet de contracts.py)
                      to-domain.ts          (SEUL point de conversion contrat -> modèle de rendu)
                      client.ts             (fetch, timeout, gestion d'erreurs typée ApiError,
                                             création/consultation/annulation de job)
                      job-polling.ts        (logique de polling PURE, sans React : interprétation
                                             du statut d'un job, backoff réseau borné)
                      use-palletization-job.ts  (hook React : orchestre client.ts + job-polling.ts,
                                             persiste le jobId actif dans le store pour reprendre
                                             le suivi après un rafraîchissement de page)
    import-export/    Export des résultats (JSON/CSV) — pas d'import/parsing métier côté client.
  store/               État (Zustand) et persistance locale des simulations (dont le `jobId` actif).
  components/
    order-table/         Édition manuelle de la commande + upload CSV (délégué au backend).
    configuration/         Écran de configuration (transport, palette, contraintes).
    results/                 Résultats, KPI, export, fiche imprimable, `optimization-loader.tsx`
                              (spinner accessible `role="status"`, sans pourcentage ni barre).
    three/                    Visualisation 3D (React Three Fiber) — consomme le résultat du
                              backend via `to-domain.ts`, aucun recalcul de position/orientation.
    transport/                 Chargement transport — appelle `/api/v1/transport/load`.
tests/
  unit/                Vitest : client API (fetch mocké), conversions contrat -> domaine, logique
                       de polling de job (interprétation de statut, backoff réseau).
  e2e/                 Playwright : démarre le VRAI backend Python + le frontend, teste le
                       parcours complet (démonstration, import CSV réel multi-commandes, panne
                       backend, cycle de vie complet d'un job asynchrone — voir
                       async-job-flow.spec.ts), sans jamais réimplémenter l'algorithme en TypeScript.
```

## Format CSV

Le format CSV **réel** attendu par le backend est documenté en détail dans
`backend/CSV_ANALYSIS_REPORT.md` (mapping complet des colonnes `DEPXENT;CDEXENT;MDTXENT;
TYPEPALETTE;...`, décodage des colonnes `CARTON_DETAIL_1..10` dont les décimales sont éclatées par
le séparateur, conversion des formats de palette `P:LxlxH`). L'import CSV se fait exclusivement
côté backend (`POST /api/v1/orders/parse-csv` ou `POST /api/v1/palletize/csv`) : le front envoie le
fichier brut, jamais de parsing dupliqué côté client.

La saisie manuelle de cartons dans le tableau de commande reste possible et produit le même
contrat JSON normalisé (voir `contracts/examples/palletize_request.json`) que l'import CSV.

## Contrat JSON normalisé

Voir `contracts/openapi.json` (généré automatiquement depuis FastAPI, `make backend-openapi` pour
le régénérer) et `contracts/examples/` pour un exemple de requête/réponse complet. Le contrat est
versionné (`contractVersion: "1.0"`), indépendant du format CSV historique.

## Limites connues

- **py3dbp est une heuristique, pas un solveur garantissant l'optimum mathématique** — le nombre de
  palettes retourné est « la meilleure solution trouvée », jamais présenté comme un minimum
  théorique prouvé. Voir `backend/README.md` pour le détail de l'adaptateur et la correspondance
  des axes domaine ↔ py3dbp ↔ Three.js.
- Le contrôle de support/stabilité est une approximation 2D, pas une simulation physique (voir
  l'avertissement ci-dessus).
- **Performance sur les grandes quantités** : le moteur reste un algorithme Python pur (extreme
  points), optimisé (index spatial, déduplication d'orientations, mémoïsation) sans jamais changer
  de résultat en dessous de `PARALLEL_BATCH_THRESHOLD` (3000 instances) ; au-delà, les commandes les
  plus extrêmes sont réparties sur plusieurs processus (`pack_with_strategy_parallel`) pour un
  parallélisme CPU réel, au prix d'un compromis de compacité limité par une passe de consolidation
  — voir `backend/README.md`, section "Performance sur les grandes commandes", pour le détail des 5
  optimisations et les mesures. Au-delà de ~500 instances de cartons, un avertissement est renvoyé
  par l'API et le mode rapide est recommandé. Sur un ordre réel de 10 881 cartons (65 → 12
  références), le rangement passe de 17-18 palettes à **8** (contre 9 attendues historiquement)
  après correction d'un bug de troncature qui bloquait prématurément l'empilement en hauteur.
  `PALLETIZATION_JOB_TIMEOUT_SECONDS` a été relevé à 3600s (1h) par défaut en conséquence. Ce n'est
  de toute façon jamais un problème d'expérience utilisateur : le job continue en tâche de fond, le
  frontend affiche un loader et reprend le suivi même après un rafraîchissement de page.
- Le module de chargement transport (`packing/transport_packer.py`) reste un heuristique 2D par
  étagères (Next-Fit Decreasing Height), pas un solveur combinatoire complet.
- Les dimensions de véhicules/conteneurs proposées en préréglage sont indicatives.
- Aucun compte utilisateur : les simulations sont sauvegardées uniquement dans le `localStorage`
  du navigateur utilisé.

Voir `ASSUMPTIONS.md` pour le détail complet des hypothèses métier retenues, et
`docs/adr/0001-headless-python-backend.md` pour la justification du choix d'architecture.

## Pistes d'évolution

- Remplacer py3dbp par une autre bibliothèque de bin packing 3D sans changer l'API ni le domaine
  (le point d'extension est `palletizer.packing.py3dbp_adapter.oriented_dimensions`, injecté via
  `application.ports.OrientationProvider`).
- Génération des types TypeScript du client directement depuis `contracts/openapi.json` (via
  `openapi-typescript`) plutôt que la définition manuelle actuelle dans
  `frontend/src/lib/api/contract-types.ts`, pour éliminer tout risque de divergence.
- Apprentissage à partir de plans de palettisation validés par des opérateurs.
- Solveur combinatoire plus avancé en complément (et non en remplacement) de l'heuristique.
- API et base de données pour la persistance multi-utilisateurs et multi-appareils.
