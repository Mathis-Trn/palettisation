import { z } from "zod";

/** Schémas Zod pour la validation des données métier saisies par l'utilisateur ou importées. */

export const dimensions3DSchema = z.object({
  length: z.number().positive({ message: "La longueur doit être supérieure à 0." }),
  width: z.number().positive({ message: "La largeur doit être supérieure à 0." }),
  height: z.number().positive({ message: "La hauteur doit être supérieure à 0." }),
});

export const cartonLineSchema = z.object({
  sku: z.string().trim().min(1, { message: "La référence (SKU) est obligatoire." }),
  dimensions: dimensions3DSchema,
  quantity: z
    .number()
    .int({ message: "La quantité doit être un nombre entier." })
    .positive({ message: "La quantité doit être supérieure à 0." }),
  weightKg: z.number().nonnegative({ message: "Le poids ne peut pas être négatif." }).optional(),
  allowRotation: z.boolean(),
  uprightOnly: z.boolean(),
  fragile: z.boolean(),
  stackable: z.boolean(),
  maxSupportedWeightKg: z
    .number()
    .nonnegative({ message: "Le poids maximal supporté ne peut pas être négatif." })
    .optional(),
  productGroup: z.string().trim().min(1).optional(),
  incompatibleGroups: z.array(z.string().trim().min(1)).optional(),
});

export const cartonLineRowSchema = cartonLineSchema.extend({
  id: z.string(),
});

export const palletConfigSchema = z.object({
  name: z.string().trim().min(1, { message: "Le nom du format de palette est obligatoire." }),
  dimensions: dimensions3DSchema,
  emptyPalletHeightMm: z.number().nonnegative(),
  maxWeightKg: z.number().positive().optional(),
  maxHeightIncludesPallet: z.boolean(),
  overhangMm: z.number().nonnegative(),
  safetyGapMm: z.number().nonnegative(),
  minimumSupportRatio: z.number().min(0).max(1),
});

export const simulationSettingsSchema = z.object({
  transportMode: z.enum(["routier", "maritime", "aerien"]),
  palletConfig: palletConfigSchema,
  globalRotationsEnabled: z.boolean(),
  optimizationLevel: z.enum(["rapide", "approfondi"]),
  fragileMaxWeightOnTopKg: z.number().nonnegative(),
});

/**
 * Ligne brute telle qu'importée depuis un fichier CSV, avant coercition de type.
 * Les colonnes booléennes restent des chaînes ici : `z.coerce.boolean()` transformerait
 * la chaîne "false" en `true` (chaîne non vide = vérité JS). La conversion texte -> booléen
 * est effectuée explicitement dans lib/import-export/csv.ts (voir `parseCsvBoolean`).
 */
export const csvRowSchema = z.object({
  sku: z.string().trim().min(1),
  longueur_mm: z.coerce.number().positive(),
  largeur_mm: z.coerce.number().positive(),
  hauteur_mm: z.coerce.number().positive(),
  quantite: z.coerce.number().int().positive(),
  poids_kg: z.coerce.number().nonnegative().optional(),
  rotation_autorisee: z.string().optional(),
  sens_vertical: z.string().optional(),
  fragile: z.string().optional(),
  gerbable: z.string().optional(),
  groupe: z.string().trim().optional(),
});

export type CsvRow = z.infer<typeof csvRowSchema>;
