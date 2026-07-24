"use client";

import { useMemo } from "react";
import { Edges } from "@react-three/drei";
import type { PlacedCarton } from "@/domain/types";
import { domainCenterToScene, domainSizeToScene } from "./coordinate-utils";
import { colorForSku, DEFAULT_EDGE_COLOR, FRAGILE_EDGE_COLOR, NEUTRAL_CARTON_COLOR, SELECTED_EDGE_COLOR } from "./sku-colors";

export function CartonMesh({
  carton,
  colorBySku,
  selected,
  explodeOffsetScene,
  onSelect,
}: {
  carton: PlacedCarton;
  colorBySku: boolean;
  selected: boolean;
  explodeOffsetScene: number;
  onSelect: (instanceId: string) => void;
}) {
  const center = useMemo(() => domainCenterToScene(carton.position, carton.placedDimensions), [carton]);
  const size = useMemo(() => domainSizeToScene(carton.placedDimensions), [carton]);
  const fillColor = colorBySku ? colorForSku(carton.sku) : NEUTRAL_CARTON_COLOR;
  const edgeColor = selected ? SELECTED_EDGE_COLOR : carton.fragile ? FRAGILE_EDGE_COLOR : DEFAULT_EDGE_COLOR;

  // Légère séparation visuelle entre cartons (2%), purement cosmétique : ne modifie jamais
  // les coordonnées métier utilisées pour les calculs (position/placedDimensions inchangés).
  const visualScale = 0.985;

  return (
    <mesh
      position={[center[0], center[1] + explodeOffsetScene, center[2]]}
      scale={[visualScale, visualScale, visualScale]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(carton.instanceId);
      }}
    >
      <boxGeometry args={size} />
      <meshStandardMaterial color={fillColor} roughness={0.7} opacity={selected ? 1 : 0.96} transparent />
      <Edges color={edgeColor} linewidth={selected ? 2 : 1} />
    </mesh>
  );
}
