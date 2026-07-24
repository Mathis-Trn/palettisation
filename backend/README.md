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
| `/api/v1/palletize` | POST | Contrat JSON normalisé → résultat complet |
| `/api/v1/palletize/csv` | POST | Upload CSV + `orderId` optionnel → résultat complet |
| `/api/v1/transport/load` | POST | Palettes déjà calculées + véhicule → plan de chargement |

Documentation interactive sur `/docs` une fois le serveur lancé. Contrat figé exporté dans
`../contracts/openapi.json` (régénérable via `make backend-openapi` depuis la racine du dépôt).

CORS piloté par la variable d'environnement `ALLOWED_ORIGINS` (liste séparée par des virgules) ;
jamais `*` si `APP_ENV=production` (l'application refuse alors de démarrer).

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

- Algorithme Python pur (points extrêmes), non parallélisé : au-delà de ~500 instances, un
  avertissement est renvoyé ; au-delà de plusieurs milliers (le CSV réel contient des lignes allant
  jusqu'à 44 250 unités), le calcul peut devenir lent.
- Le contrôle de support/stabilité est une approximation logicielle 2D, pas une simulation
  physique.
- Le décodeur `CARTON_DETAIL_*` rejette explicitement (`AMBIGUOUS_CARTON_DETAILS`) toute ligne
  dont les fragments ne permettent pas de reconstruire un candidat unique et physiquement
  plausible — il ne devine jamais silencieusement.
- `PALETTE_DETAIL_2..10` (au-delà du premier champ, toujours le littéral `PALETTE`) ne sont pas
  décodés finement : conservés bruts pour audit uniquement.

Voir `../ASSUMPTIONS.md` pour le détail complet des hypothèses métier.

## Tests

```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov=src/palletizer
```

84 tests (unitaires + intégration + Hypothesis), ~91 % de couverture de lignes. La fixture
`tests/fixtures/csv/commande_reelle.csv` est le fichier réel fourni, utilisée comme test
d'intégration complet du décodeur CSV.
