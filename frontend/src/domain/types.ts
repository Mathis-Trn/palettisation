/**
 * Types du domaine métier de la palettisation.
 * Toutes les dimensions sont en millimètres (mm), tous les poids en kilogrammes (kg).
 * Ce module ne dépend ni de React ni de Three.js : il est le socle testable indépendamment.
 */

/** Dimensions d'un objet dans son repère d'origine, avant toute rotation. */
export type Dimensions3D = {
  length: number;
  width: number;
  height: number;
};

/** Position 3D dans le repère métier de la palette (origine = coin inférieur de la palette). */
export type Position3D = {
  x: number;
  y: number;
  z: number;
};

export type TransportMode = "routier" | "maritime" | "aerien";

/** Les 6 orientations possibles d'un pavé droit (permutations des 3 axes). */
export type OrientationCode =
  | "LWH" // longueur-largeur-hauteur (orientation d'origine)
  | "WLH" // largeur-longueur-hauteur (rotation 90° à plat)
  | "LHW" // longueur-hauteur-largeur (bascule sur le côté)
  | "HWL" // hauteur-longueur-largeur (bascule sur le côté)
  | "WHL" // largeur-hauteur-longueur (bascule debout->couché)
  | "HLW"; // hauteur-largeur-longueur (bascule debout->couché)

/** Une ligne de commande : une référence produit avec sa quantité et ses contraintes. */
export type CartonLine = {
  sku: string;
  dimensions: Dimensions3D;
  quantity: number;
  /** Poids unitaire en kg. Facultatif : si absent, le carton est ignoré du contrôle de poids. */
  weightKg?: number;
  /** Autorise la rotation à plat (échange longueur/largeur) et sur la tranche si `uprightOnly` est faux. */
  allowRotation: boolean;
  /** Si vrai, le carton doit rester "debout" : sa hauteur d'origine reste verticale, aucune bascule. */
  uprightOnly: boolean;
  /** Carton fragile : soumis à la règle de charge maximale au-dessus. */
  fragile: boolean;
  /** Si faux, aucun carton ne peut être empilé au-dessus de celui-ci. */
  stackable: boolean;
  /** Poids maximal (kg) que ce carton peut supporter au-dessus de lui. Facultatif. */
  maxSupportedWeightKg?: number;
  /** Groupe de produits, utilisé pour le regroupement visuel et les règles d'incompatibilité. */
  productGroup?: string;
  /** Liste des groupes de produits avec lesquels ce carton ne doit jamais partager une palette. */
  incompatibleGroups?: string[];
};

/** Configuration d'un format de palette. */
export type PalletConfig = {
  name: string;
  /** length/width = empreinte au sol utile ; height = hauteur maximale totale configurée. */
  dimensions: Dimensions3D;
  /** Hauteur de la palette vide (bois/plastique), en mm. Valeur par défaut : 144 mm. */
  emptyPalletHeightMm: number;
  /** Charge maximale de la palette en kg. Valeur configurable, pas une vérité universelle. */
  maxWeightKg?: number;
  /** Si vrai, `dimensions.height` inclut la hauteur de la palette vide. */
  maxHeightIncludesPallet: boolean;
  /** Débordement autorisé au-delà de l'empreinte au sol, en mm. 0 par défaut. */
  overhangMm: number;
  /** Espace de sécurité minimal entre deux cartons, en mm. 0 par défaut. */
  safetyGapMm: number;
  /** Ratio minimal de surface de contact requis pour qu'un carton soit considéré stable (0 à 1). Défaut : 0.8. */
  minimumSupportRatio: number;
};

export type OptimizationLevel = "rapide" | "approfondi";

/** Réglages globaux de la simulation, distincts du format de palette lui-même. */
export type SimulationSettings = {
  transportMode: TransportMode;
  palletConfig: PalletConfig;
  /** Interrupteur global : si faux, aucune rotation n'est autorisée quelle que soit la ligne de commande. */
  globalRotationsEnabled: boolean;
  optimizationLevel: OptimizationLevel;
  /**
   * Règle simple de fragilité : poids maximal (kg) autorisé au-dessus d'un carton fragile.
   * 0 par défaut = un carton fragile ne supporte jamais rien au-dessus (comme non gerbable).
   */
  fragileMaxWeightOnTopKg: number;
};

/** Un carton placé sur une palette, résultat du moteur d'optimisation. */
export type PlacedCarton = {
  instanceId: string;
  sku: string;
  originalDimensions: Dimensions3D;
  placedDimensions: Dimensions3D;
  position: Position3D;
  orientation: OrientationCode;
  weightKg?: number;
  palletIndex: number;
  /** Score interne ayant conduit à retenir ce placement (plus haut = meilleur). */
  placementScore: number;
  fragile: boolean;
  stackable: boolean;
  productGroup?: string;
};

export type RejectionCode =
  | "DIMENSIONS_EXCEED_PALLET"
  | "HEIGHT_EXCEEDED"
  | "WEIGHT_EXCEEDED"
  | "ROTATION_FORBIDDEN"
  | "STACKING_CONSTRAINT"
  | "NO_STABLE_POSITION"
  | "INVALID_DATA";

export const REJECTION_MESSAGES: Record<RejectionCode, string> = {
  DIMENSIONS_EXCEED_PALLET:
    "Le carton dépasse les dimensions utiles de la palette dans toutes les orientations autorisées.",
  HEIGHT_EXCEEDED: "Aucune position ne respecte la hauteur maximale configurée.",
  WEIGHT_EXCEEDED: "Le poids maximal de la palette serait dépassé.",
  ROTATION_FORBIDDEN: "Aucune orientation autorisée ne permet de placer ce carton.",
  STACKING_CONSTRAINT: "Une contrainte de gerbage (non gerbable ou fragilité) empêche le placement.",
  NO_STABLE_POSITION: "Aucune position stable (support suffisant) n'a été trouvée.",
  INVALID_DATA: "Les données du carton sont invalides (dimensions ou quantité incorrectes).",
};

/** Un carton (ou une instance) qui n'a pas pu être placé, avec la raison du rejet. */
export type UnplacedCarton = {
  instanceId: string;
  sku: string;
  dimensions: Dimensions3D;
  weightKg?: number;
  code: RejectionCode;
  message: string;
};

/** Résultat de l'optimisation pour une palette donnée. */
export type PalletResult = {
  index: number;
  config: PalletConfig;
  placedCartons: PlacedCarton[];
  totalWeightKg: number;
  /** Volume utile de la palette (empreinte × hauteur utile), en mm³. */
  usableVolumeMm3: number;
  /** Volume total occupé par les cartons placés, en mm³. */
  volumeUsedMm3: number;
  /** Taux d'occupation volumique = volumeUsedMm3 / usableVolumeMm3. */
  volumeUsageRatio: number;
  /** Taux d'occupation de la surface au sol (premier niveau). */
  footprintUsageRatio: number;
  /** Hauteur maximale effectivement utilisée par les cartons, en mm. */
  maxHeightUsedMm: number;
};

/** Résultat complet d'une optimisation. */
export type OptimizationResult = {
  pallets: PalletResult[];
  unplacedCartons: UnplacedCarton[];
  totalCartonsCount: number;
  placedCartonsCount: number;
  unplacedCartonsCount: number;
  palletsCount: number;
  globalVolumeUsageRatio: number;
  totalWeightKg: number;
  warnings: string[];
  computedAtIso: string;
  /** Version du moteur ayant produit ce résultat, pour traçabilité. */
  engineVersion: string;
  /** Niveau d'optimisation effectivement utilisé. */
  levelUsed: OptimizationLevel;
  /** Durée du calcul en millisecondes. */
  durationMs: number;
};

export type OptimizerProgress = {
  phase: "expansion" | "tri" | "placement" | "finalisation";
  processedInstances: number;
  totalInstances: number;
  currentPalletIndex: number;
  strategyIndex: number;
  strategiesCount: number;
};

/** Ligne de commande côté interface : ajoute un identifiant stable pour l'édition en tableau. */
export type CartonLineRow = CartonLine & { id: string };

// --- Chargement transport (véhicule / conteneur) ------------------------------------------
// Ces types décrivaient auparavant `src/transport-loader/types.ts` (module supprimé : le calcul
// vit désormais côté backend Python) ; ils restent nécessaires pour typer la réponse de l'API
// `/api/v1/transport/load` et les composants de présentation (`VehicleFloorPlan`).

export type VehicleConfig = {
  name: string;
  innerLengthMm: number;
  innerWidthMm: number;
  innerHeightMm: number;
  maxPayloadKg: number;
  allowPalletRotationFloor: boolean;
  allowPalletStacking: boolean;
};

export type PalletToLoad = {
  palletResultIndex: number;
  footprintLengthMm: number;
  footprintWidthMm: number;
  heightMm: number;
  weightKg: number;
};

export type LoadedPalletPlacement = {
  palletResultIndex: number;
  vehicleIndex: number;
  x: number;
  y: number;
  rotated: boolean;
  stackLevel: 0 | 1;
  lengthMm: number;
  widthMm: number;
  heightMm: number;
  weightKg: number;
};

export type VehicleLoadResult = {
  index: number;
  placements: LoadedPalletPlacement[];
  usedFloorAreaRatio: number;
  usedWeightKg: number;
};

export type TransportLoadResult = {
  vehicles: VehicleLoadResult[];
  unassignedPalletIndexes: number[];
  vehiclesNeeded: number;
  palletsLoadable: number;
};

/** Une simulation sauvegardée localement dans le navigateur. */
export type Simulation = {
  id: string;
  name: string;
  createdAtIso: string;
  updatedAtIso: string;
  settings: SimulationSettings;
  cartonLines: CartonLineRow[];
  lastResult?: OptimizationResult;
  /** Version du schéma de stockage, pour permettre des migrations futures. */
  storageVersion: number;
};
