import type { CartonLine } from "@/domain/types";

/** Jeu de données de démonstration, chargeable en un clic pour tester l'application immédiatement.
 *
 * N'utilise QUE des champs modifiables dans le tableau de commande (SKU, dimensions, quantité,
 * poids, rotation, sens vertical, fragile, gerbable) : `maxSupportedWeightKg`, `productGroup` et
 * `incompatibleGroups` existent dans le modèle de domaine et influencent réellement le calcul
 * (ex. un carton fragile plafonné à 2kg de charge au-dessus rejette silencieusement tout ce qui
 * dépasse), mais ne sont exposés nulle part dans l'interface (ni le tableau, ni la Configuration)
 * — un jeu de démonstration qui s'appuyait dessus produisait donc un résultat que personne ne
 * pouvait comprendre ni reproduire en modifiant les champs visibles. Voir aussi
 * `DEMO_CARTON_LINES_LARGE` ci-dessous. */
export const DEMO_CARTON_LINES: CartonLine[] = [
  {
    sku: "ELEC-CARTON-A",
    dimensions: { length: 400, width: 300, height: 250 },
    quantity: 24,
    weightKg: 8.5,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
  },
  {
    sku: "ELEC-CARTON-B",
    dimensions: { length: 600, width: 400, height: 300 },
    quantity: 12,
    weightKg: 14,
    allowRotation: true,
    uprightOnly: true,
    fragile: false,
    stackable: true,
  },
  {
    sku: "VERRE-FRAGILE",
    dimensions: { length: 300, width: 250, height: 200 },
    quantity: 18,
    weightKg: 4,
    allowRotation: true,
    uprightOnly: true,
    fragile: true,
    stackable: true,
  },
  {
    sku: "PALETTE-SOCLE",
    dimensions: { length: 1200, width: 800, height: 150 },
    quantity: 2,
    weightKg: 60,
    allowRotation: false,
    uprightOnly: true,
    fragile: false,
    stackable: false,
  },
  {
    sku: "PIECES-DETACHEES",
    dimensions: { length: 250, width: 200, height: 150 },
    quantity: 40,
    weightKg: 3,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
  },
  {
    sku: "BIDONS-CHIMIE",
    dimensions: { length: 350, width: 350, height: 400 },
    quantity: 10,
    weightKg: 18,
    allowRotation: false,
    uprightOnly: true,
    fragile: false,
    stackable: true,
  },
  {
    sku: "HORS-GABARIT",
    dimensions: { length: 1400, width: 900, height: 500 },
    quantity: 1,
    weightKg: 45,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: false,
  },
];

export const DEMO_SIMULATION_NAME = "Démonstration — commande mixte";

/** Deuxième jeu de démonstration, beaucoup plus volumineux : de quoi générer suffisamment de
 * palettes pour que l'onglet Transport doive répartir le chargement sur PLUSIEURS véhicules —
 * le petit jeu ci-dessus tient toujours dans un seul véhicule, donc ne montre jamais ce cas.
 * Reste sous le seuil de parallélisation du moteur (~3000 instances) pour rester rapide au clic.
 * Mêmes règles que `DEMO_CARTON_LINES` : uniquement des champs modifiables dans le tableau. */
export const DEMO_CARTON_LINES_LARGE: CartonLine[] = [
  {
    sku: "MOBILIER-CARTON",
    dimensions: { length: 700, width: 500, height: 400 },
    quantity: 80,
    weightKg: 22,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
  },
  {
    sku: "ELECTROMENAGER-XL",
    dimensions: { length: 650, width: 600, height: 850 },
    quantity: 40,
    weightKg: 35,
    allowRotation: true,
    uprightOnly: true,
    fragile: false,
    stackable: true,
  },
  {
    sku: "PACK-CONSOMMABLES",
    dimensions: { length: 400, width: 300, height: 250 },
    quantity: 300,
    weightKg: 6,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
  },
  {
    sku: "BOITES-STANDARD",
    dimensions: { length: 350, width: 350, height: 300 },
    quantity: 350,
    weightKg: 8,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
  },
  {
    sku: "PIECES-LOURDES",
    dimensions: { length: 300, width: 250, height: 200 },
    quantity: 200,
    weightKg: 15,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
  },
  {
    sku: "ACCESSOIRES-LEGERS",
    dimensions: { length: 250, width: 200, height: 150 },
    quantity: 400,
    weightKg: 2,
    allowRotation: true,
    uprightOnly: false,
    fragile: true,
    stackable: true,
  },
  {
    sku: "COLIS-XXL",
    dimensions: { length: 1150, width: 750, height: 300 },
    quantity: 10,
    weightKg: 90,
    allowRotation: false,
    uprightOnly: true,
    fragile: false,
    stackable: false,
  },
];

export const DEMO_SIMULATION_NAME_LARGE = "Démonstration — grande commande (multi-véhicules)";
