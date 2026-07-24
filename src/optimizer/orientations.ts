import type { Dimensions3D, OrientationCode } from "@/domain/types";
import type { OrientedBox } from "./types";

/**
 * Calcule les orientations autorisées pour un carton.
 *
 * Le code d'orientation indique quel axe d'origine (L=longueur, W=largeur, H=hauteur)
 * est projeté sur chaque axe placé (x, y, z) : ex. "WLH" = largeur->x, longueur->y, hauteur->z.
 *
 * - Si la rotation est interdite (globalement ou pour la ligne) : seule l'orientation d'origine (LWH).
 * - Si le sens vertical est obligatoire : la hauteur d'origine doit rester verticale (LWH ou WLH).
 * - Sinon : les 6 permutations sont autorisées.
 */
export function getAllowedOrientations(
  dims: Dimensions3D,
  allowRotation: boolean,
  uprightOnly: boolean,
  globalRotationsEnabled: boolean
): OrientedBox[] {
  const { length: l, width: w, height: h } = dims;
  const effectiveRotation = allowRotation && globalRotationsEnabled;

  const all: Record<OrientationCode, Dimensions3D> = {
    LWH: { length: l, width: w, height: h },
    WLH: { length: w, width: l, height: h },
    LHW: { length: l, width: h, height: w },
    HLW: { length: h, width: l, height: w },
    WHL: { length: w, width: h, height: l },
    HWL: { length: h, width: w, height: l },
  };

  if (!effectiveRotation) {
    return [{ code: "LWH", dims: all.LWH }];
  }

  if (uprightOnly) {
    return [
      { code: "LWH", dims: all.LWH },
      { code: "WLH", dims: all.WLH },
    ];
  }

  return (Object.keys(all) as OrientationCode[]).map((code) => ({ code, dims: all[code] }));
}
