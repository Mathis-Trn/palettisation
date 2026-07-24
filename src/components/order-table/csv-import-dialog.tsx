"use client";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { parseCartonsCsv } from "@/lib/import-export/csv";

export function CsvImportDialog({
  preview,
  onCancel,
  onConfirm,
}: {
  preview: ReturnType<typeof parseCartonsCsv>;
  onCancel: () => void;
  onConfirm: (mode: "append" | "replace") => void;
}) {
  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="max-w-lg">
        <DialogTitle>Aperçu de l&apos;import CSV</DialogTitle>
        <DialogDescription>
          Séparateur détecté : <code>{preview.detectedDelimiter === ";" ? "point-virgule" : preview.detectedDelimiter === "," ? "virgule" : preview.detectedDelimiter}</code>
        </DialogDescription>

        <div className="mt-4 flex gap-3">
          <Badge variant="success">{preview.validLines.length} ligne(s) valide(s)</Badge>
          {preview.errors.length > 0 && <Badge variant="danger">{preview.errors.length} erreur(s)</Badge>}
        </div>

        {preview.validLines.length > 0 && (
          <div className="mt-3 max-h-40 overflow-y-auto rounded-md border border-slate-200 text-xs">
            <table className="w-full">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-2 py-1">SKU</th>
                  <th className="px-2 py-1">L×l×H (mm)</th>
                  <th className="px-2 py-1">Qté</th>
                </tr>
              </thead>
              <tbody>
                {preview.validLines.slice(0, 20).map((line, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-2 py-1">{line.sku}</td>
                    <td className="px-2 py-1">
                      {line.dimensions.length}×{line.dimensions.width}×{line.dimensions.height}
                    </td>
                    <td className="px-2 py-1">{line.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.validLines.length > 20 && (
              <p className="px-2 py-1 text-slate-400">… et {preview.validLines.length - 20} ligne(s) supplémentaire(s).</p>
            )}
          </div>
        )}

        {preview.errors.length > 0 && (
          <div className="mt-3 max-h-32 overflow-y-auto rounded-md bg-danger-50 p-2 text-xs text-danger-500">
            {preview.errors.map((error, i) => (
              <p key={i}>
                Ligne {error.rowNumber || "?"} : {error.message}
              </p>
            ))}
          </div>
        )}

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>
            Annuler
          </Button>
          <Button variant="secondary" disabled={preview.validLines.length === 0} onClick={() => onConfirm("append")}>
            Ajouter à la commande
          </Button>
          <Button disabled={preview.validLines.length === 0} onClick={() => onConfirm("replace")}>
            Remplacer la commande
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
