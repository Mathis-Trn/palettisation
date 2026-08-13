import type { PalletResult } from "@/domain/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatInt, formatKg } from "@/lib/format";

export function PlacedCartonsTable({ pallet }: { pallet: PalletResult }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>SKU</TableHead>
          <TableHead>Position (x, y, z mm)</TableHead>
          <TableHead>Dimensions placées (mm)</TableHead>
          <TableHead>Orientation</TableHead>
          <TableHead>Poids</TableHead>
          <TableHead>Statut</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {pallet.placedCartons.map((carton) => (
          <TableRow key={carton.instanceId}>
            <TableCell>{carton.sku}</TableCell>
            <TableCell>
              {formatInt(carton.position.x)}, {formatInt(carton.position.y)}, {formatInt(carton.position.z)}
            </TableCell>
            <TableCell>
              {carton.placedDimensions.length}×{carton.placedDimensions.width}×{carton.placedDimensions.height}
            </TableCell>
            <TableCell>{carton.orientation}</TableCell>
            <TableCell>{carton.weightKg !== undefined ? formatKg(carton.weightKg) : "—"}</TableCell>
            <TableCell>
              {carton.fragile && <Badge variant="orange">Fragile</Badge>}
              {!carton.stackable && <Badge variant="neutral">Non gerbable</Badge>}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
