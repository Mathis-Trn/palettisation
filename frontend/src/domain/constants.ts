/**
 * Constantes métier par défaut. Toutes sont configurables dans l'interface :
 * elles ne représentent que des valeurs de départ raisonnables, pas des vérités universelles.
 * Voir ASSUMPTIONS.md pour la justification de chaque valeur.
 */

export const DEFAULT_EMPTY_PALLET_HEIGHT_MM = 144;

export const DEFAULT_MINIMUM_SUPPORT_RATIO = 0.8;

export const DEFAULT_OVERHANG_MM = 0;

export const DEFAULT_SAFETY_GAP_MM = 0;

/** Poids maximal par défaut, purement indicatif — à ajuster selon le transporteur réel. */
export const DEFAULT_MAX_WEIGHT_KG = 800;

/** Règle de fragilité par défaut : aucun poids toléré au-dessus d'un carton fragile. */
export const DEFAULT_FRAGILE_MAX_WEIGHT_ON_TOP_KG = 0;

/** Base standard EUR/EPAL, partagée par les préréglages routier / maritime-aérien. */
export const STANDARD_PALLET_BASE_MM = { length: 1200, width: 800 };

export const PALLET_PRESETS = {
  routier: {
    name: "Palette transport routier",
    dimensions: {
      length: STANDARD_PALLET_BASE_MM.length,
      width: STANDARD_PALLET_BASE_MM.width,
      height: 1100,
    },
    emptyPalletHeightMm: DEFAULT_EMPTY_PALLET_HEIGHT_MM,
    maxWeightKg: DEFAULT_MAX_WEIGHT_KG,
    maxHeightIncludesPallet: true,
    overhangMm: DEFAULT_OVERHANG_MM,
    safetyGapMm: DEFAULT_SAFETY_GAP_MM,
    minimumSupportRatio: DEFAULT_MINIMUM_SUPPORT_RATIO,
  },
  maritime: {
    name: "Palette transport maritime / aérien",
    dimensions: {
      length: STANDARD_PALLET_BASE_MM.length,
      width: STANDARD_PALLET_BASE_MM.width,
      height: 1600,
    },
    emptyPalletHeightMm: DEFAULT_EMPTY_PALLET_HEIGHT_MM,
    maxWeightKg: DEFAULT_MAX_WEIGHT_KG,
    maxHeightIncludesPallet: true,
    overhangMm: DEFAULT_OVERHANG_MM,
    safetyGapMm: DEFAULT_SAFETY_GAP_MM,
    minimumSupportRatio: DEFAULT_MINIMUM_SUPPORT_RATIO,
  },
} as const;

/**
 * Préréglages de véhicules / conteneurs pour le module de chargement transport.
 * Dimensions fournies à titre indicatif uniquement — étiquetées "à vérifier selon le transporteur".
 */
export const TRANSPORT_VEHICLE_PRESETS = [
  {
    name: "Semi-remorque tautliner (à vérifier selon le transporteur)",
    innerLengthMm: 13600,
    innerWidthMm: 2470,
    innerHeightMm: 2700,
    maxPayloadKg: 24000,
  },
  {
    name: "Camion porteur 19T (à vérifier selon le transporteur)",
    innerLengthMm: 7200,
    innerWidthMm: 2450,
    innerHeightMm: 2500,
    maxPayloadKg: 11000,
  },
  {
    name: "Conteneur maritime 20 pieds (à vérifier selon le transporteur)",
    innerLengthMm: 5900,
    innerWidthMm: 2350,
    innerHeightMm: 2390,
    maxPayloadKg: 21700,
  },
  {
    name: "Conteneur maritime 40 pieds (à vérifier selon le transporteur)",
    innerLengthMm: 12030,
    innerWidthMm: 2350,
    innerHeightMm: 2390,
    maxPayloadKg: 26500,
  },
] as const;

export const ENGINE_VERSION = "1.0.0-mvp";

/** Nombre approximatif d'instances de cartons pour lesquelles l'expérience reste fluide. */
export const PRACTICAL_INSTANCE_LIMIT = 500;

export const STORAGE_SCHEMA_VERSION = 1;
