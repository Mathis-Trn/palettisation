"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { ParseCsvResponseContract } from "@/lib/api/contract-types";
import { parsedCsvOrderToDetectedOrder, type DetectedCsvOrder } from "@/lib/api/to-domain";

export function CsvImportDialog({
  preview,
  onCancel,
  onConfirm,
}: {
  preview: ParseCsvResponseContract;
  onCancel: () => void;
  onConfirm: (order: DetectedCsvOrder, mode: "append" | "replace") => void;
}) {
  const detectedOrders = preview.orders.map(parsedCsvOrderToDetectedOrder);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(detectedOrders[0]?.orderId ?? null);
  const selectedOrder = detectedOrders.find((o) => o.orderId === selectedOrderId) ?? null;

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="max-w-lg">
        <DialogTitle>Aperçu de l&apos;import CSV</DialogTitle>
        <DialogDescription>
          {preview.totalRows} ligne(s) lues, {preview.acceptedRows} acceptée(s), {preview.rejectedRows} rejetée(s).
        </DialogDescription>

        {detectedOrders.length > 1 && (
          <div className="mt-3">
            <p className="mb-2 text-xs font-medium text-slate-600">
              Plusieurs commandes détectées — choisissez celle à importer :
            </p>
            <div className="flex flex-col gap-1.5">
              {detectedOrders.map((order) => (
                <label
                  key={order.orderId}
                  className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 text-sm has-[:checked]:border-turquoise-500 has-[:checked]:bg-turquoise-50"
                >
                  <input
                    type="radio"
                    name="csv-order"
                    checked={order.orderId === selectedOrderId}
                    onChange={() => setSelectedOrderId(order.orderId)}
                  />
                  <span className="font-medium">{order.orderId}</span>
                  <span className="text-xs text-slate-500">
                    {order.lineCount} référence(s), format {order.palletCode || "?"}
                    {order.legacyPalletCount !== null && `, historique ${order.legacyPalletCount} palette(s)`}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {selectedOrder && (
          <div className="mt-3 flex gap-3">
            <Badge variant="success">{selectedOrder.lineCount} référence(s)</Badge>
            {preview.errors.length > 0 && <Badge variant="danger">{preview.errors.length} erreur(s)</Badge>}
            {preview.warnings.length > 0 && <Badge variant="warning">{preview.warnings.length} avertissement(s)</Badge>}
          </div>
        )}

        {selectedOrder && selectedOrder.lines.length > 0 && (
          <div className="mt-3 max-h-40 overflow-y-auto rounded-md border border-slate-200 text-xs">
            <table className="w-full">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-2 py-1">SKU</th>
                  <th className="px-2 py-1">L×l×H (mm)</th>
                  <th className="px-2 py-1">Poids (kg)</th>
                  <th className="px-2 py-1">Qté</th>
                </tr>
              </thead>
              <tbody>
                {selectedOrder.lines.slice(0, 20).map((line, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-2 py-1">{line.sku}</td>
                    <td className="px-2 py-1">
                      {line.dimensions.length}×{line.dimensions.width}×{line.dimensions.height}
                    </td>
                    <td className="px-2 py-1">{line.weightKg ?? "—"}</td>
                    <td className="px-2 py-1">{line.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {selectedOrder.lines.length > 20 && (
              <p className="px-2 py-1 text-slate-400">… et {selectedOrder.lines.length - 20} ligne(s) supplémentaire(s).</p>
            )}
          </div>
        )}

        {preview.errors.length > 0 && (
          <div className="mt-3 max-h-32 overflow-y-auto rounded-md bg-danger-50 p-2 text-xs text-danger-500">
            {preview.errors.map((error, i) => (
              <p key={i}>
                Ligne {error.lineNumber ?? "?"} [{error.code}] : {error.message}
              </p>
            ))}
          </div>
        )}

        {preview.warnings.length > 0 && (
          <div className="mt-3 max-h-24 overflow-y-auto rounded-md bg-warning-50 p-2 text-xs text-warning-500">
            {preview.warnings.map((warning, i) => (
              <p key={i}>{warning.message}</p>
            ))}
          </div>
        )}

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>
            Annuler
          </Button>
          <Button
            variant="secondary"
            disabled={!selectedOrder || selectedOrder.lines.length === 0}
            onClick={() => selectedOrder && onConfirm(selectedOrder, "append")}
          >
            Ajouter à la commande
          </Button>
          <Button
            disabled={!selectedOrder || selectedOrder.lines.length === 0}
            onClick={() => selectedOrder && onConfirm(selectedOrder, "replace")}
          >
            Remplacer la commande
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
