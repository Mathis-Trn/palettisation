"use client";

import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { PalletResult } from "@/domain/types";
import { PalletMesh } from "./pallet-mesh";
import { BoundsCage } from "./bounds-cage";
import { CartonMesh } from "./carton-mesh";
import { AxesLegend } from "./axes-legend";
import { mmToScene } from "./coordinate-utils";

export type SceneDisplayOptions = {
  showDimensionsCage: boolean;
  showAxes: boolean;
  colorBySku: boolean;
  hiddenSkus: Set<string>;
  layerIndex: number | null;
  explodeFactor: number;
};

export function PalletScene3D({
  pallet,
  options,
  selectedInstanceId,
  onSelect,
  resetSignal,
}: {
  pallet: PalletResult;
  options: SceneDisplayOptions;
  selectedInstanceId: string | null;
  onSelect: (instanceId: string | null) => void;
  resetSignal: number;
}) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);

  const layers = useMemo(() => {
    const zStarts = Array.from(new Set(pallet.placedCartons.map((c) => Math.round(c.position.z)))).sort((a, b) => a - b);
    return zStarts;
  }, [pallet]);

  const visibleCartons = useMemo(() => {
    return pallet.placedCartons.filter((c) => {
      if (options.hiddenSkus.has(c.sku)) return false;
      if (options.layerIndex !== null) {
        const layerZ = layers[options.layerIndex];
        if (Math.round(c.position.z) !== layerZ) return false;
      }
      return true;
    });
  }, [pallet, options.hiddenSkus, options.layerIndex, layers]);

  const cameraDistance = mmToScene(Math.max(pallet.config.dimensions.length, pallet.config.dimensions.height + 800, 2000)) * 1.4;

  return (
    <div className="relative h-[480px] w-full overflow-hidden rounded-lg border border-slate-200 bg-gradient-to-b from-slate-100 to-slate-200">
      <Canvas shadows camera={{ position: [cameraDistance, cameraDistance * 0.75, cameraDistance], fov: 45 }} onPointerMissed={() => onSelect(null)}>
        <Suspense fallback={null}>
          <ambientLight intensity={0.65} />
          <directionalLight position={[4, 6, 3]} intensity={1.1} castShadow shadow-mapSize={[1024, 1024]} />
          <directionalLight position={[-3, 4, -2]} intensity={0.35} />

          <PalletMesh config={pallet.config} />
          {options.showDimensionsCage && <BoundsCage config={pallet.config} />}
          {options.showAxes && <AxesLegend config={pallet.config} />}
          <Grid args={[20, 20]} cellColor="#c3cbd6" sectionColor="#98a3b3" fadeDistance={15} position={[0, -0.002, 0]} />

          {visibleCartons.map((carton) => {
            const layerOrdinal = layers.indexOf(Math.round(carton.position.z));
            const explodeOffsetScene = layerOrdinal >= 0 ? layerOrdinal * options.explodeFactor * 0.15 : 0;
            return (
              <CartonMesh
                key={carton.instanceId}
                carton={carton}
                colorBySku={options.colorBySku}
                selected={carton.instanceId === selectedInstanceId}
                explodeOffsetScene={explodeOffsetScene}
                onSelect={(id) => onSelect(id)}
              />
            );
          })}

          <OrbitControls ref={controlsRef} makeDefault enableDamping dampingFactor={0.08} />
          <CameraResetter controlsRef={controlsRef} resetSignal={resetSignal} />
        </Suspense>
      </Canvas>
    </div>
  );
}

function CameraResetter({ controlsRef, resetSignal }: { controlsRef: React.RefObject<OrbitControlsImpl | null>; resetSignal: number }) {
  useEffect(() => {
    if (resetSignal > 0) controlsRef.current?.reset();
  }, [controlsRef, resetSignal]);
  return null;
}
