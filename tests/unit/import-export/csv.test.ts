import { describe, expect, it } from "vitest";
import { CSV_TEMPLATE, parseCartonsCsv, parseCsvBoolean } from "@/lib/import-export/csv";

describe("parseCartonsCsv", () => {
  it("13. accepte les CSV séparés par des virgules", () => {
    const csv = "sku,longueur_mm,largeur_mm,hauteur_mm,quantite\nBOX-A,400,300,250,12\n";
    const result = parseCartonsCsv(csv);
    expect(result.errors).toHaveLength(0);
    expect(result.validLines).toHaveLength(1);
    expect(result.validLines[0]).toMatchObject({ sku: "BOX-A", quantity: 12 });
  });

  it("13. accepte les CSV séparés par des points-virgules", () => {
    const csv = "sku;longueur_mm;largeur_mm;hauteur_mm;quantite\nBOX-B;600;400;300;8\n";
    const result = parseCartonsCsv(csv);
    expect(result.errors).toHaveLength(0);
    expect(result.validLines).toHaveLength(1);
    expect(result.validLines[0]).toMatchObject({ sku: "BOX-B", quantity: 8 });
  });

  it("importe le modèle CSV fourni sans erreur", () => {
    const result = parseCartonsCsv(CSV_TEMPLATE);
    expect(result.errors).toHaveLength(0);
    expect(result.validLines).toHaveLength(3);
    expect(result.validLines[2]).toMatchObject({ sku: "BOX-C", fragile: true, allowRotation: true });
  });

  it("signale une ligne avec une dimension invalide sans bloquer les autres", () => {
    const csv = "sku,longueur_mm,largeur_mm,hauteur_mm,quantite\nBOX-A,400,300,250,12\nBOX-BAD,-10,300,250,5\n";
    const result = parseCartonsCsv(csv);
    expect(result.validLines).toHaveLength(1);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].rowNumber).toBe(3);
  });

  it("signale les colonnes obligatoires manquantes", () => {
    const csv = "sku,longueur_mm\nBOX-A,400\n";
    const result = parseCartonsCsv(csv);
    expect(result.errors.some((e) => e.message.includes("Colonnes obligatoires manquantes"))).toBe(true);
  });
});

describe("parseCsvBoolean", () => {
  it("reconnaît les valeurs vraies courantes", () => {
    expect(parseCsvBoolean("true")).toBe(true);
    expect(parseCsvBoolean("VRAI")).toBe(true);
    expect(parseCsvBoolean("1")).toBe(true);
    expect(parseCsvBoolean("oui")).toBe(true);
  });

  it("reconnaît 'false' comme faux (et non comme une chaîne vérité)", () => {
    expect(parseCsvBoolean("false")).toBe(false);
    expect(parseCsvBoolean("faux")).toBe(false);
    expect(parseCsvBoolean("0")).toBe(false);
  });

  it("applique la valeur par défaut si la colonne est absente", () => {
    expect(parseCsvBoolean(undefined, true)).toBe(true);
    expect(parseCsvBoolean("", true)).toBe(true);
    expect(parseCsvBoolean(undefined, false)).toBe(false);
  });
});
