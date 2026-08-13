/** Attribue une couleur stable et déterministe à chaque SKU, par hachage du texte. */
export function colorForSku(sku: string): string {
  let hash = 0;
  for (let i = 0; i < sku.length; i += 1) {
    hash = sku.charCodeAt(i) + ((hash << 5) - hash);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 62%, 54%)`;
}

export const NEUTRAL_CARTON_COLOR = "#8fa3bd";
export const FRAGILE_EDGE_COLOR = "#f2823a";
export const SELECTED_EDGE_COLOR = "#17a6a0";
export const DEFAULT_EDGE_COLOR = "#1e2c4d";
