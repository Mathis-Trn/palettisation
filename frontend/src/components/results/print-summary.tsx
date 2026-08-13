import type { Simulation } from "@/domain/types";
import { formatDateFr, formatInt, formatKg, formatPercent, TRANSPORT_MODE_LABELS } from "@/lib/format";

/** Fiche récapitulative simple, visible uniquement à l'impression (voir la règle @media print de globals.css). */
export function PrintSummary({ simulation }: { simulation: Simulation }) {
  const result = simulation.lastResult;
  return (
    <div className="hidden print:block">
      <h1 className="text-xl font-bold">Fiche récapitulative — {simulation.name}</h1>
      <p className="text-sm">
        Généré le {formatDateFr(new Date().toISOString())} — Mode de transport : {TRANSPORT_MODE_LABELS[simulation.settings.transportMode]}
      </p>
      {!result ? (
        <p className="mt-4 text-sm">Aucun résultat d&apos;optimisation disponible.</p>
      ) : (
        <>
          <table className="mt-4 w-full border-collapse text-sm">
            <tbody>
              <tr>
                <td className="border px-2 py-1 font-medium">Cartons commandés</td>
                <td className="border px-2 py-1">{formatInt(result.totalCartonsCount)}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Cartons placés</td>
                <td className="border px-2 py-1">{formatInt(result.placedCartonsCount)}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Cartons non placés</td>
                <td className="border px-2 py-1">{formatInt(result.unplacedCartonsCount)}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Palettes générées</td>
                <td className="border px-2 py-1">{formatInt(result.palletsCount)}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Occupation volumique globale</td>
                <td className="border px-2 py-1">{formatPercent(result.globalVolumeUsageRatio)}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Poids total</td>
                <td className="border px-2 py-1">{formatKg(result.totalWeightKg)}</td>
              </tr>
            </tbody>
          </table>

          <table className="mt-4 w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border px-2 py-1 text-left">Palette</th>
                <th className="border px-2 py-1 text-left">Cartons</th>
                <th className="border px-2 py-1 text-left">Poids</th>
                <th className="border px-2 py-1 text-left">Occupation volumique</th>
              </tr>
            </thead>
            <tbody>
              {result.pallets.map((pallet) => (
                <tr key={pallet.index}>
                  <td className="border px-2 py-1">Palette {pallet.index + 1}</td>
                  <td className="border px-2 py-1">{pallet.placedCartons.length}</td>
                  <td className="border px-2 py-1">{formatKg(pallet.totalWeightKg)}</td>
                  <td className="border px-2 py-1">{formatPercent(pallet.volumeUsageRatio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <p className="mt-4 text-xs">
        Le contrôle de stabilité et de support est une approximation logicielle ; il ne constitue pas une certification physique du
        chargement.
      </p>
    </div>
  );
}
