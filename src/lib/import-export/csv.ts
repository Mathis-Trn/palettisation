import Papa from "papaparse";
import type { CartonLine } from "@/domain/types";
import { csvRowSchema } from "@/domain/schemas";

export type CsvImportError = {
  rowNumber: number;
  message: string;
};

export type CsvImportPreview = {
  validLines: CartonLine[];
  errors: CsvImportError[];
  detectedDelimiter: string;
  totalRows: number;
};

const TRUE_VALUES = new Set(["true", "vrai", "1", "oui", "yes", "y", "x"]);

/**
 * Convertit une valeur texte de CSV en booléen. Toute valeur absente ou non reconnue vaut `false`,
 * sauf si `defaultValue` est fourni pour les colonnes facultatives (ex. gerbable = true par défaut).
 */
export function parseCsvBoolean(value: string | undefined, defaultValue = false): boolean {
  if (value === undefined || value.trim() === "") return defaultValue;
  return TRUE_VALUES.has(value.trim().toLowerCase());
}

const REQUIRED_HEADERS = ["sku", "longueur_mm", "largeur_mm", "hauteur_mm", "quantite"];

/**
 * Analyse un fichier CSV de commande. Détecte automatiquement le séparateur (virgule ou
 * point-virgule, entre autres) via Papa Parse. Les lignes invalides sont rapportées avec leur
 * numéro et un message clair, sans bloquer l'import des lignes valides.
 */
export function parseCartonsCsv(csvText: string): CsvImportPreview {
  const parsed = Papa.parse<Record<string, string>>(csvText, {
    header: true,
    skipEmptyLines: true,
    delimitersToGuess: [",", ";", "\t", "|"],
    transformHeader: (header) => header.trim().toLowerCase(),
  });

  const errors: CsvImportError[] = [];
  const headers = parsed.meta.fields ?? [];
  const missingHeaders = REQUIRED_HEADERS.filter((h) => !headers.includes(h));
  if (missingHeaders.length > 0) {
    errors.push({
      rowNumber: 0,
      message: `Colonnes obligatoires manquantes : ${missingHeaders.join(", ")}. Utilisez le modèle CSV fourni.`,
    });
  }

  const validLines: CartonLine[] = [];

  parsed.data.forEach((rawRow, index) => {
    const rowNumber = index + 2; // +1 pour l'en-tête, +1 pour un index base 1
    const parsedRow = csvRowSchema.safeParse(rawRow);
    if (!parsedRow.success) {
      errors.push({
        rowNumber,
        message: parsedRow.error.issues.map((issue) => `${String(issue.path[0] ?? "")}: ${issue.message}`).join(" "),
      });
      return;
    }

    const row = parsedRow.data;
    validLines.push({
      sku: row.sku,
      dimensions: { length: row.longueur_mm, width: row.largeur_mm, height: row.hauteur_mm },
      quantity: row.quantite,
      weightKg: row.poids_kg,
      allowRotation: parseCsvBoolean(row.rotation_autorisee, true),
      uprightOnly: parseCsvBoolean(row.sens_vertical, false),
      fragile: parseCsvBoolean(row.fragile, false),
      stackable: parseCsvBoolean(row.gerbable, true),
      productGroup: row.groupe && row.groupe.length > 0 ? row.groupe : undefined,
    });
  });

  for (const error of parsed.errors) {
    errors.push({ rowNumber: (error.row ?? 0) + 2, message: error.message });
  }

  return {
    validLines,
    errors,
    detectedDelimiter: parsed.meta.delimiter,
    totalRows: parsed.data.length,
  };
}

export const CSV_TEMPLATE = `sku,longueur_mm,largeur_mm,hauteur_mm,quantite,poids_kg,rotation_autorisee,sens_vertical,fragile,gerbable
BOX-A,400,300,250,12,8.5,true,false,false,true
BOX-B,600,400,300,8,12,true,true,false,true
BOX-C,250,200,150,20,3,true,false,true,true
`;

export function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
