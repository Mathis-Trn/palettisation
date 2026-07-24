"use client";

import { useRef, useState } from "react";
import type { CartonLineRow, Simulation } from "@/domain/types";
import { cartonLineSchema } from "@/domain/schemas";
import { useSimulationStore } from "@/store/simulation-store";
import { ApiError, parseCsv } from "@/lib/api/client";
import type { ParseCsvResponseContract } from "@/lib/api/contract-types";
import type { DetectedCsvOrder } from "@/lib/api/to-domain";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import { Copy, Trash2, Upload, PlusCircle, AlertTriangle, Loader2 } from "lucide-react";
import { CsvImportDialog } from "./csv-import-dialog";
import { v4 as uuid } from "uuid";

export function OrderTable({ simulation }: { simulation: Simulation }) {
  const addCartonLine = useSimulationStore((s) => s.addCartonLine);
  const updateCartonLine = useSimulationStore((s) => s.updateCartonLine);
  const removeCartonLine = useSimulationStore((s) => s.removeCartonLine);
  const duplicateCartonLine = useSimulationStore((s) => s.duplicateCartonLine);
  const replaceCartonLines = useSimulationStore((s) => s.replaceCartonLines);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importPreview, setImportPreview] = useState<ParseCsvResponseContract | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  function handleAddLine() {
    addCartonLine(simulation.id, {
      sku: `NOUVELLE-REF-${simulation.cartonLines.length + 1}`,
      dimensions: { length: 300, width: 200, height: 200 },
      quantity: 1,
      weightKg: undefined,
      allowRotation: true,
      uprightOnly: false,
      fragile: false,
      stackable: true,
    });
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setIsUploading(true);
    setUploadError(null);
    try {
      const preview = await parseCsv(file);
      setImportPreview(preview);
    } catch (error) {
      setUploadError(
        error instanceof ApiError
          ? error.message
          : "Erreur inattendue lors de l'envoi du CSV au serveur."
      );
    } finally {
      setIsUploading(false);
    }
  }

  function confirmImport(order: DetectedCsvOrder, mode: "append" | "replace") {
    const newRows: CartonLineRow[] = order.lines.map((line) => ({ ...line, id: uuid() }));
    if (mode === "replace") {
      replaceCartonLines(simulation.id, newRows);
    } else {
      replaceCartonLines(simulation.id, [...simulation.cartonLines, ...newRows]);
    }
    setImportPreview(null);
  }

  const totalQuantity = simulation.cartonLines.reduce((sum, l) => sum + (Number.isFinite(l.quantity) ? l.quantity : 0), 0);

  return (
    <Card>
      <CardHeader className="flex-wrap gap-2">
        <div>
          <CardTitle>Commande — cartons à palettiser</CardTitle>
          <p className="mt-1 text-xs text-slate-500">
            {simulation.cartonLines.length} référence(s), {totalQuantity} carton(s) au total.
          </p>
          {uploadError && <p className="mt-1 text-xs text-danger-500">{uploadError}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
            {isUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
            {isUploading ? "Analyse en cours…" : "Importer un CSV"}
          </Button>
          <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFileSelected} />
          <Button size="sm" onClick={handleAddLine}>
            <PlusCircle className="h-3.5 w-3.5" />
            Ajouter une ligne
          </Button>
        </div>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {simulation.cartonLines.length === 0 ? (
          <div className="rounded-md border border-dashed border-slate-300 py-10 text-center text-sm text-slate-500">
            Aucun carton dans cette commande. Ajoutez une ligne manuellement ou importez un fichier CSV.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>L (mm)</TableHead>
                <TableHead>l (mm)</TableHead>
                <TableHead>H (mm)</TableHead>
                <TableHead>Qté</TableHead>
                <TableHead>Poids (kg)</TableHead>
                <TableHead>Rotation</TableHead>
                <TableHead>Sens vertical</TableHead>
                <TableHead>Fragile</TableHead>
                <TableHead>Gerbable</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {simulation.cartonLines.map((line) => (
                <OrderRow
                  key={line.id}
                  line={line}
                  onChange={(patch) => updateCartonLine(simulation.id, line.id, patch)}
                  onDuplicate={() => duplicateCartonLine(simulation.id, line.id)}
                  onDelete={() => removeCartonLine(simulation.id, line.id)}
                />
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {importPreview && (
        <CsvImportDialog preview={importPreview} onCancel={() => setImportPreview(null)} onConfirm={confirmImport} />
      )}
    </Card>
  );
}

function OrderRow({
  line,
  onChange,
  onDuplicate,
  onDelete,
}: {
  line: CartonLineRow;
  onChange: (patch: Partial<CartonLineRow>) => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const validation = cartonLineSchema.safeParse(line);
  const errorMessage = validation.success ? null : validation.error.issues.map((i) => i.message).join(" ");

  return (
    <TableRow className={errorMessage ? "bg-danger-50/40" : undefined}>
      <TableCell>
        <Input value={line.sku} onChange={(e) => onChange({ sku: e.target.value })} className="w-36" />
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-20"
          value={line.dimensions.length}
          onChange={(e) => onChange({ dimensions: { ...line.dimensions, length: Number(e.target.value) } })}
        />
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-20"
          value={line.dimensions.width}
          onChange={(e) => onChange({ dimensions: { ...line.dimensions, width: Number(e.target.value) } })}
        />
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-20"
          value={line.dimensions.height}
          onChange={(e) => onChange({ dimensions: { ...line.dimensions, height: Number(e.target.value) } })}
        />
      </TableCell>
      <TableCell>
        <Input type="number" className="w-16" value={line.quantity} onChange={(e) => onChange({ quantity: Number(e.target.value) })} />
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-20"
          value={line.weightKg ?? ""}
          onChange={(e) => onChange({ weightKg: e.target.value === "" ? undefined : Number(e.target.value) })}
        />
      </TableCell>
      <TableCell>
        <Checkbox checked={line.allowRotation} onCheckedChange={(v) => onChange({ allowRotation: v === true })} />
      </TableCell>
      <TableCell>
        <Checkbox checked={line.uprightOnly} onCheckedChange={(v) => onChange({ uprightOnly: v === true })} />
      </TableCell>
      <TableCell>
        <Checkbox checked={line.fragile} onCheckedChange={(v) => onChange({ fragile: v === true })} />
      </TableCell>
      <TableCell>
        <Checkbox checked={line.stackable} onCheckedChange={(v) => onChange({ stackable: v === true })} />
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1">
          {errorMessage && (
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Badge variant="danger">
                    <AlertTriangle className="h-3 w-3" />
                  </Badge>
                </span>
              </TooltipTrigger>
              <TooltipContent>{errorMessage}</TooltipContent>
            </Tooltip>
          )}
          <Button size="icon" variant="ghost" aria-label={`Dupliquer ${line.sku}`} onClick={onDuplicate}>
            <Copy className="h-3.5 w-3.5 text-slate-500" />
          </Button>
          <Button size="icon" variant="ghost" aria-label={`Supprimer ${line.sku}`} onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5 text-danger-500" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}
