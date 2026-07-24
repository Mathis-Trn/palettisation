import Papa from "papaparse";
import type { OptimizationResult, Simulation } from "@/domain/types";

/** Exporte le résultat complet (et les réglages de la simulation) en JSON, pour ré-import ou archivage. */
export function exportResultToJson(simulation: Simulation): string {
  return JSON.stringify(simulation, null, 2);
}

/** Exporte le détail des cartons placés (une ligne par carton) en CSV, pour exploitation externe. */
export function exportPlacedCartonsToCsv(result: OptimizationResult): string {
  const rows = result.pallets.flatMap((pallet) =>
    pallet.placedCartons.map((carton) => ({
      palette: pallet.index + 1,
      sku: carton.sku,
      instance_id: carton.instanceId,
      x_mm: Math.round(carton.position.x),
      y_mm: Math.round(carton.position.y),
      z_mm: Math.round(carton.position.z),
      longueur_placee_mm: carton.placedDimensions.length,
      largeur_placee_mm: carton.placedDimensions.width,
      hauteur_placee_mm: carton.placedDimensions.height,
      orientation: carton.orientation,
      poids_kg: carton.weightKg ?? "",
      fragile: carton.fragile ? "oui" : "non",
      gerbable: carton.stackable ? "oui" : "non",
    }))
  );
  return Papa.unparse(rows, { delimiter: ";" });
}

/** Exporte la liste des cartons non placés en CSV, avec le code et le message de rejet. */
export function exportUnplacedCartonsToCsv(result: OptimizationResult): string {
  const rows = result.unplacedCartons.map((carton) => ({
    sku: carton.sku,
    longueur_mm: carton.dimensions.length,
    largeur_mm: carton.dimensions.width,
    hauteur_mm: carton.dimensions.height,
    poids_kg: carton.weightKg ?? "",
    code_rejet: carton.code,
    message: carton.message,
  }));
  return Papa.unparse(rows, { delimiter: ";" });
}
