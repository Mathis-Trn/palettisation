# `palletizer` — moteur headless de palettisation 3D

Package Python autonome (aucune dépendance à FastAPI, Next.js, React ou Three.js dans son cœur)
qui expose :

- un **domaine** métier pur (`palletizer.domain`) — dataclasses gelées, mm/kg, zéro dépendance
  framework ;
- un **contrat JSON versionné** (`palletizer.contracts`, Pydantic v2), indépendant du CSV
  historique ;
- un **adaptateur** de bin-packing 3D (`palletizer.packing`) autour de la bibliothèque
  [`py3dbp`](https://pypi.org/project/py3dbp/) (version épinglée `1.1.2`) ;
- un **importeur CSV** du format métier réel (`palletizer.imports.legacy_csv`), avec reconstruction
  des dimensions/poids dont les décimales ont été éclatées par le séparateur ;
- un **service applicatif** headless (`palletizer.application.services`), utilisable comme simple
  bibliothèque Python, sans serveur ni navigateur ;
- une **CLI** (`palletizer`, Typer) ;
- une **API FastAPI** versionnée (`palletizer.api`), qui n'est qu'une couche d'adaptation HTTP
  au-dessus du service applicatif.

## Installation

```bash
cd backend
uv sync --dev
```

(`uv` installé sur cette machine via `pip install --user uv` ; utilisable via `uv` si présent dans
le PATH de votre shell, sinon `python -m uv`.)

## Utilisation en bibliothèque pure (sans FastAPI, sans front)

```python
from palletizer.application.services import PalletizationService
from palletizer.contracts import PalletizeRequest, PalletizeResponse

request = PalletizeRequest.model_validate_json(
    open("../contracts/examples/palletize_request.json", encoding="utf-8").read()
)
order = request.order.to_domain()
pallet_spec = request.pallet.to_domain(request.options.minimum_support_ratio)
options = request.options.to_domain()

result = PalletizationService().optimize(order, pallet_spec, options)
print(result.pallets_count, result.placed_cartons_count, result.unplaced_cartons_count)

# Sérialisation au format du contrat, identique à ce que renvoie l'API :
response_json = PalletizeResponse.from_domain(result).model_dump_json(by_alias=True, indent=2)
```

## CLI

Aucun serveur ni navigateur requis. stdin/stdout via `-`, logs sur stderr, codes de sortie non nuls
en cas d'erreur.

```bash
uv run palletizer capabilities
uv run palletizer validate-csv tests/fixtures/csv/commande_reelle.csv
uv run palletizer parse-csv tests/fixtures/csv/commande_reelle.csv --output -
uv run palletizer optimize-csv tests/fixtures/csv/commande_reelle.csv --order SO265669-X82921 --output -
uv run palletizer optimize normalized.json --output result.json
uv run palletizer transport-load transport_request.json --output -
```

## API

```bash
uv run uvicorn palletizer.api.main:app --reload --port 8000
```

Routes (`GET /health`, préfixe `/api/v1` pour le reste) :

| Route | Méthode | Description |
|---|---|---|
| `/health` | GET | État du service, version du package et du moteur |
| `/api/v1/capabilities` | GET | Formats supportés, contraintes, limites, adaptateur de packing |
| `/api/v1/orders/parse-csv` | POST | Upload CSV → commandes détectées, lignes normalisées, erreurs |
| `/api/v1/palletize` | POST | Contrat JSON normalisé → résultat complet (synchrone, requête maintenue ouverte pendant tout le calcul — voir avertissement ci-dessous) |
| `/api/v1/palletize/csv` | POST | Upload CSV + `orderId` optionnel → résultat complet (idem, synchrone) |
| `/api/v1/palletization-jobs` | POST | Démarre un calcul en tâche de fond, répond immédiatement (202) |
| `/api/v1/palletization-jobs/{id}` | GET | Statut/résultat d'un job (`queued/running/succeeded/failed/cancelled/expired`) |
| `/api/v1/palletization-jobs/{id}` | DELETE | Annule un job (voir sémantique honnête ci-dessous) |
| `/api/v1/transport/load` | POST | Palettes déjà calculées + véhicule → plan de chargement |

Documentation interactive sur `/docs` une fois le serveur lancé. Contrat figé exporté dans
`../contracts/openapi.json` (régénérable via `make backend-openapi` depuis la racine du dépôt).

CORS piloté par la variable d'environnement `ALLOWED_ORIGINS` (liste séparée par des virgules) ;
jamais `*` si `APP_ENV=production` (l'application refuse alors de démarrer).

**`/api/v1/palletize` et `/api/v1/palletize/csv` restent synchrones** (utiles en CLI/script, ou pour
un petit ordre) : la requête HTTP reste ouverte pendant tout le calcul, qui peut durer plusieurs
minutes sur un ordre volumineux. **Le frontend n'utilise plus ces routes pour son parcours normal**
— il passe systématiquement par `/api/v1/palletization-jobs`, précisément pour éviter qu'un calcul
long ne se heurte au timeout d'un client HTTP (c'est exactement le bug historique que l'architecture
de jobs corrige, voir section suivante).

## Jobs asynchrones

Le calcul est potentiellement long (plusieurs minutes sur un ordre volumineux) et **ne doit jamais
tourner à l'intérieur d'une requête HTTP maintenue ouverte** : un client (navigateur, proxy,
load-balancer) qui abandonne au bout de 30s ne dit rien sur l'état réel du calcul côté serveur, qui
continue de consommer du CPU sans que personne ne puisse plus récupérer le résultat.

```
POST /api/v1/palletization-jobs   →  202 {jobId, status: "queued", createdAt}   (répond en < 1s)
GET  /api/v1/palletization-jobs/{id}  →  {status, result?, error?}              (polling léger)
DELETE /api/v1/palletization-jobs/{id}  →  annulation best-effort
```

- **Exécution** : `palletizer.jobs.manager.JobManager`, injecté avec un `ProcessPoolExecutor` (vrai
  parallélisme CPU, contourne le GIL) — jamais dans la boucle asyncio de FastAPI. Un thread démon
  (`_watch_loop`) détecte les transitions `queued → running`, finalise les jobs terminés, expire les
  jobs qui dépassent `PALLETIZATION_JOB_TIMEOUT_SECONDS`, et purge les jobs terminés plus vieux que
  `PALLETIZATION_JOB_RETENTION_SECONDS`.
- **Stockage** : `palletizer.jobs.store.JobStore` est un `Protocol` ; `InMemoryJobStore` est la seule
  implémentation fournie et **ne convient qu'à une seule instance de backend** (pas de partage entre
  plusieurs réplicas). Remplacer par une implémentation Redis (ou équivalente) sans changer
  `JobManager` ni les routes.
- **Concurrence** : `PALLETIZATION_MAX_CONCURRENT_JOBS` limite le nombre de calculs simultanés ; un
  job supplémentaire reste `queued`.
- **Idempotence** : une soumission identique (même empreinte SHA-256 du corps de requête canonique)
  pendant qu'un job équivalent est encore actif renvoie le **même** `jobId` plutôt que d'en créer un
  second — protège contre les doubles clics ou les relances automatiques accidentelles côté client.
- **Annulation honnête** : `DELETE` réussit à interrompre un job encore `queued` (jamais démarré).
  Un job déjà `running` est marqué `cancelled` côté serveur (son résultat est ignoré), **mais le
  worker Python sous-jacent peut continuer de tourner jusqu'à sa fin naturelle** — ce n'est pas
  menti côté frontend : le bouton d'annulation n'y est affiché que pendant l'état `queued`.
- **Couche métier inchangée** : `palletizer.jobs` ne dépend que de `application`/`domain` — jamais
  l'inverse, et `application.services.PalletizationService` n'a toujours aucune dépendance à
  FastAPI ni au gestionnaire de jobs (voir `jobs/runner.py::run_optimize_job`, le seul point de
  contact, qui se contente d'appeler le service).
- **Tests** : le délai artificiel utilisé en test (`X-Palletizer-Test-Delay-Seconds`, gated par
  `PALLETIZER_ENABLE_TEST_HOOKS=1`) est un argument explicite de `run_optimize_job`, jamais lu depuis
  une variable d'environnement à l'intérieur du worker — les workers d'un `ProcessPoolExecutor` sont
  réutilisés entre tâches, donc leur `os.environ` est figé au démarrage et ne refléterait pas une
  variable modifiée après coup.

Variables d'environnement (voir `.env.example`) : `PALLETIZATION_JOB_TIMEOUT_SECONDS` (défaut 1800),
`PALLETIZATION_JOB_RETENTION_SECONDS` (défaut 3600), `PALLETIZATION_MAX_CONCURRENT_JOBS` (défaut 1).

## Performance sur les grandes commandes

Trois optimisations de vitesse pure, toutes vérifiées par la suite de tests existante (Hypothesis
inclus) **sans changer aucun résultat** :

1. **Index spatial 3D** (`WorkingPallet.grid`, voir `_nearby_boxes`) : remplace un scan linéaire de
   TOUS les cartons déjà posés sur la palette par une recherche dans une grille de cellules
   (`GRID_CELL_MM`), pour chaque test de collision/support. Réduction de candidats uniquement — le
   test géométrique exact (`boxes_overlap`, `check_support`) reste inchangé et décide seul.
2. **Déduplication des orientations** (`_dedupe_orientations`) : un carton dont deux arêtes sont
   égales (base carrée, fréquent) n'a souvent que 3, voire 1, dimensions orientées distinctes parmi
   les 6 codes testés — prouvé sans effet sur le résultat (voir docstring).
3. **Mémoïsation des échecs par palette** (`WorkingPallet.no_fit_cache`) : un ordre réel répète
   souvent la même référence des centaines de fois ; sans ce cache, la boucle multi-palettes
   relance une recherche complète contre CHAQUE palette déjà ouverte pour CHAQUE instance, même
   identique à la précédente. Invalidé automatiquement à chaque modification de la palette
   (`add_placed_box`) : ne peut donc jamais renvoyer un résultat périmé.

Une quatrième correction, cette fois de **qualité de rangement** (pas seulement de vitesse) :

4. **Priorité de troncature des points de placement** (`_register_placement`) : au-delà de
   `MAX_EXTREME_POINTS` (400) positions candidates par palette, les points excédentaires sont
   éliminés. Le tri de troncature favorisait auparavant les points les plus BAS — une large première
   couche de petits cartons identiques génère des centaines de points bas (interstices non encore
   comblés), qui évinçaient les quelques points hauts nécessaires pour démarrer une nouvelle couche.
   Résultat observé sur un ordre réel (`SO266346-X83375`, 65 → 12 références, 10 881 cartons) : la
   palette se bloquait après 1-2 couches alors que la hauteur et le poids disponibles permettaient
   d'en empiler bien plus, produisant **17-18 palettes au lieu de 9** attendues historiquement
   (`PALXENT`). Corrigé en inversant la priorité (garder les points les plus HAUTS en cas de
   dépassement) : **8 palettes** sur ce même ordre, avec 76-97 % d'occupation volumique sur les
   palettes principales (contre 13-40 % avant correction). Voir le test de régression
   `test_extreme_point_truncation_keeps_high_points_over_low_ones`.

Cette correction de qualité a un coût en vitesse (un rangement plus dense signifie plus de cartons,
donc plus de comparaisons, par palette). Mesuré sur le cas le plus volumineux du fichier fourni
(`SO266633-X83698`, 29 138 cartons) :

| Étape | Durée | Palettes |
|---|---|---|
| Avant toute optimisation | n'aboutit pas en temps raisonnable (extrapolé à plusieurs heures) | — |
| Après optimisations de vitesse seules (points 1-3), troncature encore buggée | ~1260 s (~21 min) | 35 |
| Après correction de la troncature (point 4) | **~2567 s (~43 min)** | **15** |

`PALLETIZATION_JOB_TIMEOUT_SECONDS` a été relevé à 3600s (1h) par défaut en conséquence — le job
continue de toute façon en tâche de fond sans jamais bloquer l'utilisateur, quelle que soit la
durée réelle du calcul.

Une cinquième optimisation, cette fois avec un **compromis explicite et assumé** (contrairement aux
points 1-4, qui ne changent jamais le résultat) :

5. **Empaquetage parallèle par lots** (`packing/adapter.py::pack_with_strategy_parallel`) : réservé
   aux commandes dépassant `PARALLEL_BATCH_THRESHOLD` (3000 instances), au-delà duquel même le
   séquentiel optimisé (points 1-4) devient impraticable pour les cas les plus extrêmes (une
   référence minuscule répétée des dizaines de milliers de fois — ex. `SO265838-X83118`, 48 762
   cartons, 44 250 unités d'une même référence 55×85×15 mm). Principe : diviser les instances
   (déjà triées par stratégie) en `PALLETIZATION_PACKING_WORKERS` lots (défaut : nombre de coeurs
   CPU), empaqueter chaque lot **indépendamment et en parallèle** (un `ProcessPoolExecutor` par
   lot, véritable parallélisme CPU qui contourne le GIL), puis **consolider** : la dernière palette
   de chaque lot à plusieurs palettes (la seule susceptible d'être incomplète) est mise de côté et
   repassée séquentiellement avec celles des autres lots, pour être recombinée sur moins de
   palettes que si chaque reliquat restait séparé. Un lot qui ne produit qu'**une seule** palette
   est conservé tel quel (jamais envoyé en reliquat — voir
   `test_combine_batch_results_keeps_single_pallet_batches_without_consolidation`, régression sur
   un bug réel où confondre ce cas annulait tout le gain de parallélisme). Contrairement aux points
   1-4, **le résultat n'est pas garanti identique** au séquentiel : traiter des lots indépendamment
   est nécessairement un peu moins compact (chaque lot laisse sa propre queue incomplète), la
   consolidation ne fait que limiter cette perte. En dessous du seuil, le comportement séquentiel
   (résultat identique, garanti) reste inchangé. Configurable via `PALLETIZATION_PACKING_WORKERS`
   (voir `.env.example`).

Une sixième correction, de **qualité de rangement** comme le point 4 (toujours appliquée, pas une
option) :

6. **Poids de la distance à l'origine dans le score** (`scoring.py::_ORIGIN_DISTANCE_WEIGHT`,
   historiquement -0.05, porté tel quel depuis l'ancien moteur TypeScript) : correct pour des
   cartons de hauteur "normale", où le coût d'une couche supplémentaire (-1.0 par mm de hauteur)
   domine largement ce terme secondaire — mais bug réel sur un carton PLAT (55×85×15mm) posé sur
   une grande palette (1200×800mm) : à -0.05/mm, rejoindre le coin opposé du plancher coûte jusqu'à
   -0,05×(1200+800)=-100 points, largement plus que le coût d'empiler PLUSIEURS couches
   supplémentaires de ce carton (-1.0×15=-15 par couche). Le moteur préférait donc construire une
   pyramide décroissante près du coin d'origine plutôt que de terminer la couche courante en cours,
   laissant de larges zones du plancher inutilisées à chaque couche (mesuré sur un ordre réel : la
   couche 0 s'arrêtait à 146/189 cartons avant bascule sur la couche suivante, puis 40, 12, 1, 1 —
   une pyramide sur 5 couches au lieu d'un pavage plat). Corrigé en réduisant ce poids à -0,0005 :
   le pire écart de distance possible ne pèse plus qu'1 point, négligeable face à toute différence
   de hauteur réaliste, ce qui restaure son rôle de simple départage entre positions par ailleurs
   équivalentes. Résultat mesuré sur le même cas : couche 0 remplie à 189/189, et sur une commande
   réaliste multi-références, l'occupation volumique globale passe de 65 % à 87 % (3 palettes au
   lieu de 4). Voir le test de régression `test_flat_carton_fills_current_layer_before_stacking`.

## Correspondance des axes (domaine ↔ py3dbp ↔ Three.js)

Le domaine utilise `x = longueur`, `y = largeur`, `z = hauteur` (vertical), origine au coin de la
palette, position = coin inférieur du carton (pas son centre). py3dbp modélise ses objets avec des
attributs `width`/`height`/`depth` dont l'indice de position (`[p0, p1, p2]`) correspond à
`width→axe 0`, `height→axe 1`, `depth→axe 2` — vérifié empiriquement dans
`tests/integration/test_py3dbp_probe.py` en lisant le code source de `py3dbp.main.Bin.put_item`
(la bibliothèque ne documente pas cette convention). L'adaptateur (`packing/py3dbp_adapter.py`)
mappe `py3dbp.width = domaine.length_mm`, `py3dbp.height = domaine.height_mm`,
`py3dbp.depth = domaine.width_mm`, ce qui fait coïncider `py3dbp.height` avec la verticale du
domaine. Le composant Three.js du front (`coordinate-utils.ts`) ne voit jamais ce détail : il ne
consomme que `Position3D`/`Dimensions3D` du domaine (mm, coin de la palette), inchangés depuis la
version TypeScript d'origine.

**py3dbp ne gère nativement aucune des contraintes suivantes** — implémentées en Python autour de
la primitive de rotation qu'elle fournit :

| Contrainte | Géré par |
|---|---|
| Rotation/orientation autorisée par carton | `packing/constraints.py::allowed_orientations` (pré-filtre) |
| Sens vertical obligatoire (`uprightOnly`) | idem |
| Espace de sécurité (`safetyGapMm`) | `packing/validation.py::boxes_overlap` (recherche + post-check) |
| Ratio de support / centre de gravité | `packing/validation.py::check_support` |
| Fragilité / poids max supporté | idem |
| Groupes incompatibles | `packing/constraints.py::is_compatible_with_pallet` |
| Boucle multi-palettes, garde-fou anti-boucle infinie | `packing/adapter.py::pack_with_strategy` |

Toute solution est re-vérifiée indépendamment (`packing/validation.py::
validate_optimization_result`) avant d'être renvoyée : collision, débordement, hauteur, poids,
unicité des instances placées+rejetées = total. Une anomalie lève `SolutionValidationError` plutôt
que d'être renvoyée silencieusement.

**py3dbp fournit une heuristique, pas une preuve d'optimalité** : le nombre de palettes est
toujours présenté comme « la meilleure solution trouvée », jamais comme un minimum garanti.
Remplacer py3dbp par une autre bibliothèque ne nécessite de modifier que
`packing/py3dbp_adapter.py::oriented_dimensions` (voir `application/ports.py::OrientationProvider`)
— ni le domaine, ni l'API, ni la CLI n'ont besoin de changer.

## Import CSV réel et comparaison historique

Voir `CSV_ANALYSIS_REPORT.md` pour l'analyse complète du fichier réel fourni (mapping des colonnes,
décodage des dimensions dont les décimales sont éclatées, formats de palette, 6 commandes
détectées). `PALXENT` (nombre de palettes historique) est conservé dans
`legacyExpectedResult.pallet_count` de chaque résultat, uniquement pour comparaison — jamais
utilisé comme entrée du solveur ni comme cible à reproduire.

## Limites connues

- Algorithme Python pur (points extrêmes), non parallélisé au sein d'un job : au-delà de ~500
  instances, un avertissement est renvoyé. Voir "Performance sur les grandes commandes" ci-dessus
  pour les temps mesurés sur le cas le plus volumineux du fichier réel fourni (44 250 unités sur une
  seule ligne dans un autre ordre) — le calcul reste plus lent qu'un ordre courant, mais s'exécute
  désormais en tâche de fond (voir "Jobs asynchrones") et se termine dans un temps raisonnable.
- Le contrôle de support/stabilité est une approximation logicielle 2D, pas une simulation
  physique.
- Le décodeur `CARTON_DETAIL_*` rejette explicitement (`AMBIGUOUS_CARTON_DETAILS`) toute ligne
  dont les fragments ne permettent pas de reconstruire un candidat unique et physiquement
  plausible — il ne devine jamais silencieusement.
- `PALETTE_DETAIL_2..10` (au-delà du premier champ, toujours le littéral `PALETTE`) ne sont pas
  décodés finement : conservés bruts pour audit uniquement.
- Le stockage des jobs asynchrones est en mémoire (`InMemoryJobStore`) : ne fonctionne que pour une
  seule instance de backend, et tous les jobs sont perdus au redémarrage du processus. Un
  déploiement multi-réplicas nécessite une implémentation `JobStore` partagée (Redis ou équivalent).
- L'annulation d'un job déjà `running` ne tue pas le worker Python sous-jacent (limite du
  `ProcessPoolExecutor` standard, qui n'expose pas d'interruption coopérative) : le résultat est
  ignoré côté serveur, mais le calcul continue jusqu'à sa fin naturelle avant que la ressource ne
  soit libérée.

Voir `../ASSUMPTIONS.md` pour le détail complet des hypothèses métier.

## Tests

```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov=src/palletizer
```

101 tests (unitaires + intégration + Hypothesis), ~91 % de couverture de lignes — dont 17 tests
dédiés aux jobs asynchrones (`tests/unit/test_job_manager.py` : transitions d'état, timeout,
rétention, déduplication, limitation de concurrence, annulation ; `tests/integration/
test_jobs_api.py` : contrat HTTP réel, non-blocage de la boucle asyncio). La fixture
`tests/fixtures/csv/commande_reelle.csv` est le fichier réel fourni, utilisée comme test
d'intégration complet du décodeur CSV.
