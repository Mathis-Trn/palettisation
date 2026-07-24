import type { PlacedCarton } from "@/domain/types";
import { formatKg, formatMm } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { colorForSku } from "./sku-colors";

export function CartonInfoPanel({ carton }: { carton: PlacedCarton | null }) {
  if (!carton) {
    return (
      <div className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-500">
        Cliquez sur un carton dans la vue 3D pour afficher ses informations.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 text-sm">
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 rounded-full" style={{ backgroundColor: colorForSku(carton.sku) }} />
        <h4 className="font-semibold text-navy-900">{carton.sku}</h4>
        {carton.fragile && <Badge variant="orange">Fragile</Badge>}
        {!carton.stackable && <Badge variant="neutral">Non gerbable</Badge>}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
        <dt className="text-slate-500">Identifiant</dt>
        <dd className="text-navy-900">{carton.instanceId}</dd>
        <dt className="text-slate-500">Dimensions d&apos;origine</dt>
        <dd className="text-navy-900">
          {formatMm(carton.originalDimensions.length)} × {formatMm(carton.originalDimensions.width)} × {formatMm(carton.originalDimensions.height)}
        </dd>
        <dt className="text-slate-500">Orientation</dt>
        <dd className="text-navy-900">{carton.orientation}</dd>
        <dt className="text-slate-500">Position (x, y, z)</dt>
        <dd className="text-navy-900">
          {formatMm(carton.position.x)}, {formatMm(carton.position.y)}, {formatMm(carton.position.z)}
        </dd>
        <dt className="text-slate-500">Poids</dt>
        <dd className="text-navy-900">{carton.weightKg !== undefined ? formatKg(carton.weightKg) : "non renseigné"}</dd>
        <dt className="text-slate-500">Score de placement</dt>
        <dd className="text-navy-900">{carton.placementScore.toFixed(1)}</dd>
      </dl>
    </div>
  );
}
