# Hypothèses métier

Ce document liste les hypothèses prises pour combler les zones non précisées du cahier des
charges. Chacune est reflétée dans le code par un paramètre configurable (jamais une valeur figée
« en dur » sans réglage associé), et peut donc être ajustée dans l'écran **Configuration**.

## Palette et hauteur

- **Hauteur de palette vide par défaut : 144 mm.** Valeur usuelle pour une palette EUR/EPAL en
  bois, modifiable dans la configuration (`emptyPalletHeightMm`).
- **`maxHeightIncludesPallet`** détermine si la hauteur maximale totale saisie inclut la palette
  vide ou non. Par défaut : oui (les préréglages routier/maritime expriment une hauteur totale au
  sol, palette comprise).
- **Débordement (`overhangMm`)** : étend la limite utile uniquement au-delà du bord « loin » de
  l'origine (x ∈ [0, longueur + débordement], y ∈ [0, largeur + débordement]), et non
  symétriquement des deux côtés. Simplification qui conserve un repère simple et cohérent avec
  l'origine au coin de la palette.
- **Charge maximale de palette** : valeur par défaut de 800 kg fournie à titre purement indicatif
  et modifiable ; elle n'est jamais présentée comme une vérité universelle. Si laissée à 0 dans
  l'interface, aucune limite de poids n'est appliquée.

## Poids et fragilité

- **Poids manquant** : si `weightKg` n'est pas renseigné sur une ligne, le carton est ignoré des
  contrôles de poids (poids cumulé de palette, règle de fragilité). Aucune valeur par défaut
  fictive n'est inventée.
- **Règle de fragilité** : simple et explicite, pilotée par `fragileMaxWeightOnTopKg` (0 kg par
  défaut). Un carton fragile ne peut recevoir au-dessus de lui qu'un carton dont le poids ne
  dépasse pas ce seuil. À 0 kg (valeur par défaut), un carton fragile se comporte comme un carton
  non gerbable : rien ne peut être posé dessus.
- **Poids maximal supporté par carton (`maxSupportedWeightKg`)** : si renseigné, vérifié contre le
  poids du carton posé directement au-dessus, uniquement si ce poids est lui-même renseigné.

## Support et stabilité

- **Ratio de support minimal** : 0.8 (80 %) par défaut, configurable. Il s'agit d'une
  **approximation logicielle 2D** : la surface de contact entre la face supérieure des cartons
  support et l'empreinte du carton posé est comparée à ce seuil.
- **Centre de gravité** : simplifié en un contrôle du centre géométrique de l'empreinte, qui doit
  se trouver dans la zone couverte par au moins un carton support directement dessous.
- **Ce contrôle ne constitue pas une certification physique du chargement.** Il ne simule ni les
  forces dynamiques du transport, ni le comportement réel des matériaux d'emballage. Voir aussi
  l'avertissement dans le README.

## Rotations

- Le réglage global « Autoriser les rotations » (écran Configuration) et le réglage
  `allowRotation` par ligne de commande sont combinés par un **ET logique** : les deux doivent
  être vrais pour qu'une rotation soit testée sur un carton donné.
- **Sens vertical obligatoire (`uprightOnly`)** : restreint les orientations testées aux deux
  rotations qui gardent la hauteur d'origine verticale (rotation à plat autour de l'axe Z
  uniquement). Aucune bascule sur la tranche n'est jamais testée pour ces cartons.

## Espacement

- **Espace de sécurité (`safetyGapMm`)** : appliqué uniquement sur les axes X et Y (au sol). Les
  cartons empilés verticalement (axe Z) doivent pouvoir se toucher exactement, l'espace de
  sécurité ne s'applique pas à l'empilage.

## Groupes de produits et incompatibilités

- Deux cartons appartenant à des groupes mutuellement incompatibles (`incompatibleGroups`) ne sont
  jamais placés sur la même palette.
- Si un carton est incompatible avec toutes les palettes déjà ouvertes, une **nouvelle palette est
  ouverte** plutôt que de rejeter le carton : l'incompatibilité de groupe n'est jamais, à elle
  seule, une cause de rejet définitif.

## Taux de remplissage

- **Occupation volumique** (`volumeUsageRatio`) : volume cumulé des cartons placés divisé par le
  volume utile de la palette (empreinte débordement inclus × hauteur utile). Ne modélise pas les
  vides internes complexes autrement que par ce ratio global simple.
- **Occupation de la surface au sol** (`footprintUsageRatio`) : calculée uniquement sur les
  cartons du premier niveau (z = 0), somme de leurs aires divisée par l'aire de l'empreinte utile.

## Déterminisme et performance

- Les identifiants d'instance sont générés par un **compteur global déterministe** suivant l'ordre
  d'entrée des lignes de commande, jamais par une valeur aléatoire : à données et réglages
  identiques, deux exécutions produisent un résultat rigoureusement identique (mêmes
  identifiants, mêmes positions).
- **Mode rapide** : une seule stratégie de tri (volume décroissant).
- **Mode approfondi** : quatre stratégies de tri essayées (volume décroissant, plus grande
  dimension décroissante, poids décroissant, surface au sol décroissante) ; la solution retenue
  minimise d'abord le nombre de palettes, puis maximise le taux de remplissage global, puis la
  stabilité moyenne des placements.
- **Seuil pratique de 500 instances** : au-delà, un avertissement est affiché et le mode rapide
  est recommandé, mais le calcul n'est jamais bloqué strictement.

## Module de chargement transport

- Placement **2D uniquement** des empreintes de palettes déjà chargées (issues du moteur de
  palettisation), par une heuristique simple de type « étagères » (shelf packing / Next-Fit
  Decreasing Height). Ce n'est pas un solveur combinatoire complet.
- **Empilage de palettes** (si activé) : implémenté comme une passe simplifiée qui superpose une
  palette restante sur une palette déjà posée au sol, si l'empreinte rentre et si la hauteur et le
  poids cumulés respectent le véhicule. Un seul niveau d'empilage est géré dans ce MVP.
- **Dimensions de véhicules et conteneurs** : les préréglages fournis sont indicatifs et
  explicitement étiquetés « à vérifier selon le transporteur » — aucune dimension réglementaire
  n'est présentée comme une vérité figée.

## Import CSV

- Séparateur auto-détecté parmi virgule, point-virgule, tabulation et barre verticale.
- Valeurs booléennes reconnues (insensible à la casse) : `true`, `vrai`, `1`, `oui`, `yes`, `y`,
  `x`. Toute autre valeur, y compris la chaîne `false`, vaut faux — un piège classique évité
  explicitement dans le code (`parseCsvBoolean`).
- Colonnes optionnelles absentes : `rotation_autorisee` par défaut vrai, `sens_vertical` par défaut
  faux, `fragile` par défaut faux, `gerbable` par défaut vrai.
- Une ligne invalide est signalée avec son numéro et un message, sans bloquer l'import des autres
  lignes valides.
