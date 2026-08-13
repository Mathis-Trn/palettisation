# ADR 0001 — Backend Python headless avec adaptateur py3dbp anticorruption

## Statut

Acceptée (migration réalisée).

## Contexte

Le moteur de palettisation 3D était initialement écrit en TypeScript, exécuté dans un Web Worker
du frontend Next.js. Le besoin est de rendre ce moteur réutilisable par d'autres clients (une CLI,
un batch, une autre API, un autre front), sans dépendre du navigateur ni de React/Three.js, tout en
s'appuyant sur une bibliothèque de bin packing 3D existante plutôt que de maintenir un algorithme
maison isolé.

## Décision

1. **Le moteur devient un package Python headless** (`palletizer`), sans aucune dépendance à
   FastAPI, Next.js, React ou Three.js dans son cœur (`domain/`, `application/`, `packing/`,
   `imports/`). FastAPI (`api/`) et Typer (`cli.py`) sont des couches d'adaptation fines
   au-dessus du service applicatif (`application/services.py`), jamais l'inverse.
2. **py3dbp est intégré via un adaptateur anticorruption** (`packing/py3dbp_adapter.py`) : aucun
   objet de la bibliothèque ne sort de ce module. Seule sa primitive de rotation géométrique (les 6
   permutations d'axes d'un pavé droit) est utilisée ; la recherche de placement, le scoring, les
   contraintes métier (support, fragilité, gerbage, groupes incompatibles, espace de sécurité)
   restent implémentés en Python, portés fidèlement depuis l'ancien moteur TypeScript pour
   préserver le comportement et le déterminisme exacts.
3. **Le point d'extension pour remplacer py3dbp plus tard** est le protocole
   `application/ports.py::OrientationProvider` : une nouvelle bibliothèque n'implique de changer
   qu'un seul module, sans toucher au domaine, à l'API ni à la CLI.
4. **Le frontend devient un client HTTP pur** : toute la logique de packing/collision/rotation/
   support/scoring/chargement transport a été supprimée du TypeScript. Un point de conversion
   unique (`frontend/src/lib/api/to-domain.ts`) traduit le contrat JSON du backend vers le modèle
   de rendu consommé par la visualisation Three.js, qui reste elle-même inchangée.
5. **Un contrat JSON versionné** (`contractVersion`, `backend/src/palletizer/contracts.py`,
   exporté en OpenAPI dans `contracts/openapi.json`) découple le format d'échange du format CSV
   historique de l'entreprise.

## Conséquences

- Le moteur est testable et utilisable sans navigateur ni serveur (`PalletizationService` importé
  directement en Python), ce qui satisfait le besoin de réutilisation par CLI/batch/autre API.
- Le portage fidèle de l'algorithme (scoring, points extrêmes, tie-breaks) depuis TypeScript vers
  Python demande plus d'effort qu'une réécriture naïve autour de py3dbp seul, mais préserve le
  comportement observable (déterminisme, codes de rejet, invariants) déjà validé par l'ancienne
  suite de tests.
- py3dbp étant peu maintenu et purement heuristique, l'architecture explicite ce point (heuristique
  ≠ optimum garanti) plutôt que de le masquer, et prévoit son remplacement sans réécriture du reste
  du système.
- Le frontend perd son autonomie de calcul hors-ligne (il dépend désormais d'un backend
  joignable) ; en contrepartie, il gagne en simplicité (plus de Web Worker, plus de duplication de
  règles métier) et en cohérence avec un seul moteur faisant autorité.
