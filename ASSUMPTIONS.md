# Hypothèses métier

Ce document liste les hypothèses prises pour combler les zones non précisées du cahier des
charges. Chacune est reflétée dans le code par un paramètre configurable (jamais une valeur figée
« en dur » sans réglage associé, sauf mention explicite), et peut donc être ajustée via l'API/CLI
(`palletizer.contracts`) ou l'écran **Configuration** du front.

Le moteur de placement (points extrêmes, scoring, support, groupes) a été **porté fidèlement**
depuis l'ancien moteur TypeScript vers `backend/src/palletizer/packing` et
`backend/src/palletizer/application/services.py` : les hypothèses ci-dessous concernant
l'algorithme restent identiques à celles de la version TypeScript d'origine. Les nouvelles
hypothèses spécifiques au backend Python, à l'adaptateur py3dbp et à l'import CSV réel sont
regroupées en fin de document.

## Palette et hauteur

- **Hauteur de palette vide par défaut : 144 mm.** Valeur usuelle pour une palette EUR/EPAL en
  bois, modifiable (`emptyPalletHeightMm`).
- **`maxHeightIncludesPallet`** détermine si la hauteur maximale totale saisie inclut la palette
  vide ou non. Par défaut : oui.
- **Débordement (`overhangMm`)** : étend la limite utile uniquement au-delà du bord « loin » de
  l'origine (x ∈ [0, longueur + débordement], y ∈ [0, largeur + débordement]), et non
  symétriquement des deux côtés.
- **Charge maximale de palette** : valeur par défaut de 800 kg fournie à titre purement indicatif
  et modifiable (`maxWeightKg`) ; jamais présentée comme une vérité universelle. Si absente,
  aucune limite de poids n'est appliquée.

## Poids et fragilité

- **Poids manquant** : si `weightKg` n'est pas renseigné, le carton est ignoré des contrôles de
  poids (poids cumulé de palette, règle de fragilité). Aucune valeur par défaut fictive.
- **Règle de fragilité** : pilotée par `fragileMaxWeightOnTopKg` (0 kg par défaut). À 0 kg, un
  carton fragile se comporte comme un carton non gerbable.
- **Poids maximal supporté par carton (`maxSupportedWeightKg`)** : vérifié contre le poids du
  carton posé directement au-dessus, uniquement si ce poids est lui-même renseigné.

## Support et stabilité

- **Ratio de support minimal** : 0.8 (80 %) par défaut (`minimumSupportRatio`). Approximation
  logicielle 2D : surface de contact entre la face supérieure des cartons support et l'empreinte
  du carton posé, comparée à ce seuil.
- **Centre de gravité** : simplifié en un contrôle du centre géométrique de l'empreinte, qui doit
  se trouver dans la zone couverte par au moins un carton support directement dessous.
- **Ce contrôle ne constitue pas une certification physique du chargement** (voir avertissement du
  README).

## Rotations

- `globalRotationsEnabled` (réglage global) et `allowRotation` (par ligne) sont combinés par un
  **ET logique**.
- **Sens vertical obligatoire (`uprightOnly`)** : restreint aux deux rotations qui gardent la
  hauteur d'origine verticale (`LWH`/`WLH`). Confirmé empiriquement contre py3gdbp — voir
  `backend/tests/integration/test_py3dbp_probe.py` et `packing/py3dbp_adapter.py`.

## Espacement, groupes, remplissage, déterminisme

- **Espace de sécurité (`safetyGapMm`)** : appliqué uniquement sur les axes X et Y. Les cartons
  empilés verticalement doivent pouvoir se toucher exactement.
- **Groupes incompatibles** : deux cartons de groupes mutuellement incompatibles ne partagent
  jamais une palette ; si un carton est incompatible avec toutes les palettes déjà ouvertes, une
  **nouvelle palette est ouverte** plutôt que de le rejeter — l'incompatibilité de groupe n'est
  jamais, à elle seule, une cause de rejet définitif (garanti par construction : une instance seule
  tient toujours sur une palette vide, voir `can_instance_ever_fit`).
- **Occupation volumique/surface au sol** : mêmes définitions que l'ancien moteur.
- **Déterminisme** : identifiants d'instance générés par un compteur global suivant l'ordre
  d'entrée. Mode rapide = 1 stratégie de tri (volume décroissant) ; mode approfondi = 4 stratégies,
  la meilleure étant choisie par (moins de palettes, puis plus de cartons placés, puis meilleure
  occupation volumique, puis hauteur utilisée la plus faible, puis nom de stratégie pour un
  tie-break stable).
- **Seuil pratique de 500 instances** : au-delà, un avertissement est renvoyé par l'API
  (`warnings`), mais le calcul n'est jamais bloqué strictement. Pour des quantités de plusieurs
  milliers d'instances (le CSV réel joint contient des lignes allant jusqu'à 44 250 unités), le
  temps de calcul peut devenir significatif (algorithme Python pur, non parallélisé) — limite
  pratique documentée, pas un correctif produit à ce stade.

## Module de chargement transport

- Placement **2D uniquement** des empreintes de palettes déjà chargées, heuristique « étagères »
  (Next-Fit Decreasing Height), portée en Python dans `packing/transport_packer.py`.
- **Empilage de palettes** (si activé) : une palette restante par palette déjà posée au sol, si
  l'empreinte rentre et si hauteur/poids cumulés respectent le véhicule. Un seul niveau d'empilage.
- **Dimensions de véhicules et conteneurs** : préréglages indicatifs, « à vérifier selon le
  transporteur », gérés côté front (`domain/constants.ts`) — non fournis par l'API (le contrat
  `/api/v1/transport/load` attend un véhicule explicite).

---

## Hypothèses spécifiques au backend Python et à l'import CSV réel

### Bibliothèque de bin packing (py3dbp)

- **py3dbp 1.1.2** (dernière version publiée sur PyPI au moment de la migration) est utilisée
  uniquement pour la primitive géométrique de rotation (les 6 permutations d'axes d'un pavé
  droit), via `packing/py3dbp_adapter.py::oriented_dimensions`. Elle **ne gère nativement ni** la
  restriction des rotations autorisées par carton, **ni** l'espace de sécurité, **ni** le ratio de
  support, **ni** la fragilité, **ni** les groupes incompatibles : ces contraintes restent
  implémentées en Python autour de la primitive (`packing/constraints.py`, `packing/validation.py`,
  `packing/scoring.py`, `packing/adapter.py`).
- **py3dbp est une heuristique** (premier-fit géométrique) — le nombre de palettes retourné est
  présenté comme « la meilleure solution trouvée », jamais comme un minimum mathématique garanti.
- La correspondance exacte entre les axes du domaine (x=longueur, y=largeur, z=hauteur), les axes
  internes de py3dbp (`width`/`height`/`depth`, indices 0/1/2) et la scène Three.js est documentée
  en tête de `packing/py3dbp_adapter.py` et vérifiée par un test qui échouerait si une future
  version de py3dbp changeait cette convention (`tests/integration/test_py3dbp_probe.py`).
- Toute solution produite est re-vérifiée indépendamment (`packing/validation.py::
  validate_optimization_result`) : collision, débordement, hauteur, poids, unicité des instances.
  Une solution invalide lève `SolutionValidationError` plutôt que d'être renvoyée silencieusement.

### Format de palette `P:{longueur_cm}x{largeur_cm}x{hauteur_cm}`

- Confirmé par l'exemple de contrat JSON du cahier des charges (section 7) :
  `"code": "P:80x120x110"` y est associé à `lengthMm: 800, widthMm: 1200` — **le premier nombre du
  format devient directement `lengthMm`, sans permutation.** Ceci diffère volontairement de l'ordre
  length/width (1200×800) des anciens presets front "routier"/"maritime" TypeScript, qui décrivaient
  la même empreinte physique avec les deux axes nommés dans l'autre sens — la forme et la surface
  sont identiques, seul le nom donné à chaque axe diffère. Le contrat JSON normalisé fait foi.

### Décodage des colonnes `CARTON_DETAIL_1..10` (décimales éclatées)

- Algorithme documenté en détail dans `backend/CSV_ANALYSIS_REPORT.md`. Deux seuils numériques
  documentés et testés :
  - **Tolérance de cohérence volumique** : 0,5 % d'écart relatif entre `longueur×largeur×hauteur`
    et le `volume` décodé (les 4 exemples du cahier des charges correspondent à une égalité
    exacte ; la tolérance couvre un éventuel arrondi).
  - **Plausibilité de densité** : `poids_kg / (volume_cm³/1000)` doit rester dans **[0,02 ; 20]
    kg/L**. Cette plage a été calibrée empiriquement sur les 114 lignes réelles pour disqualifier
    les interprétations clairement absurdes (densité 39 à 494 kg/L rencontrée sur certains petits
    coffrets/échantillons) sans jamais introduire de nouvelle ambiguïté.
- Une ligne dont les fragments ne permettent pas de trouver un candidat unique sous ces deux
  critères est rejetée avec le code `AMBIGUOUS_CARTON_DETAILS`, jamais devinée.

### Mapping CSV → contrat normalisé

- `MDTXENT` (mode de transport, M=maritime/sea, A=aérien/air) et `TYPEPALETTE` (format de palette)
  sont des champs **indépendants** : `TYPEPALETTE` est lu directement dans le fichier, jamais
  re-dérivé du mode de transport (le SQL historique `CESI.csv` les corrélait, mais ce n'est qu'une
  coïncidence de ce jeu de données précis, pas une règle métier générale).
- `QTCXLIG` est la quantité principale ; `QTEXARC` est conservé tel quel en métadonnées d'audit
  (`legacyExpectedResult.raw_qtexarc`), jamais utilisé comme quantité — sa valeur observée sur le
  fichier réel est systématiquement le littéral `"PALETTE"` (un marqueur, pas un nombre), ce qui
  confirme a posteriori qu'il n'aurait de toute façon pas pu servir de quantité.
- Le CSV legacy ne renseigne aucune contrainte de rotation/fragilité/gerbage par SKU : les valeurs
  par défaut de l'ancien import CSV simplifié TypeScript sont reprises à l'identique
  (`allowRotation=true`, `uprightOnly=false`, `fragile=false`, `stackable=true`).
- `PALETTE_DETAIL_1..10` : le premier champ est toujours le littéral `PALETTE`, suivi de valeurs
  numériques dont le décodage complet (au-delà du premier champ) **n'est pas garanti** sans
  confirmation métier supplémentaire — conservées brutes pour audit uniquement, jamais utilisées
  comme entrée du solveur. Seul `PALXENT` (nombre de palettes historique par commande) sert de
  comparaison chiffrée fiable (`legacyExpectedResult.pallet_count`).
- Une commande = un `CDEXENT` = une optimisation ; les cartons de commandes différentes ne sont
  jamais mélangés dans une même optimisation.

### Limites de sécurité (CSV)

- Taille maximale : 20 Mo. Nombre maximal de lignes : 200 000. Ces limites sont volontairement
  généreuses par rapport au fichier réel (114 lignes) mais bornent le risque de déni de service par
  upload — configurables dans `imports/legacy_csv.py`.
