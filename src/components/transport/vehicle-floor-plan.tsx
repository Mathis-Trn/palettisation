import type { VehicleConfig, VehicleLoadResult } from "@/transport-loader/types";

const COLORS = ["#3a5488", "#17a6a0", "#f2823a", "#1f9d63", "#d64545", "#6b7688", "#128581", "#db6a22"];

export function VehicleFloorPlan({ vehicle, result }: { vehicle: VehicleConfig; result: VehicleLoadResult }) {
  const padding = 20;
  const scale = 500 / Math.max(vehicle.innerLengthMm, 1);
  const width = vehicle.innerLengthMm * scale + padding * 2;
  const height = vehicle.innerWidthMm * scale + padding * 2;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-2xl rounded-md border border-slate-200 bg-white">
      <rect x={padding} y={padding} width={vehicle.innerLengthMm * scale} height={vehicle.innerWidthMm * scale} fill="#f6f7f9" stroke="#98a3b3" />
      {result.placements
        .filter((p) => p.stackLevel === 0)
        .map((placement, i) => (
          <g key={`${placement.palletResultIndex}-${placement.stackLevel}`}>
            <rect
              x={padding + placement.x * scale}
              y={padding + placement.y * scale}
              width={placement.lengthMm * scale}
              height={placement.widthMm * scale}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.75}
              stroke="#0f1b33"
            />
            <text
              x={padding + placement.x * scale + (placement.lengthMm * scale) / 2}
              y={padding + placement.y * scale + (placement.widthMm * scale) / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={11}
              fill="white"
            >
              P{placement.palletResultIndex + 1}
            </text>
          </g>
        ))}
    </svg>
  );
}
