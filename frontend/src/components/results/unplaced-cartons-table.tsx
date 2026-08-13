import type { UnplacedCarton } from "@/domain/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export function UnplacedCartonsTable({ cartons }: { cartons: UnplacedCarton[] }) {
  if (cartons.length === 0) {
    return <p className="rounded-md bg-success-50 px-3 py-2 text-sm text-success-500">Tous les cartons ont pu être placés.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>SKU</TableHead>
          <TableHead>Dimensions (mm)</TableHead>
          <TableHead>Poids</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>Raison du rejet</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cartons.map((carton) => (
          <TableRow key={carton.instanceId}>
            <TableCell>{carton.sku}</TableCell>
            <TableCell>
              {carton.dimensions.length}×{carton.dimensions.width}×{carton.dimensions.height}
            </TableCell>
            <TableCell>{carton.weightKg !== undefined ? `${carton.weightKg} kg` : "—"}</TableCell>
            <TableCell>
              <Badge variant="danger">{carton.code}</Badge>
            </TableCell>
            <TableCell className="max-w-xs whitespace-normal text-slate-600">{carton.message}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
