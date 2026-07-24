import { Html } from "@react-three/drei";
import type { PalletConfig } from "@/domain/types";
import { mmToScene } from "./coordinate-utils";

/** Repère des axes : X = longueur, Y (vertical, scène) = hauteur métier, Z (profondeur, scène) = largeur métier. */
export function AxesLegend({ config }: { config: PalletConfig }) {
  const lengthScene = mmToScene(config.dimensions.length);
  const widthScene = mmToScene(config.dimensions.width);
  const usableHeight = config.maxHeightIncludesPallet ? config.dimensions.height - config.emptyPalletHeightMm : config.dimensions.height;
  const heightScene = mmToScene(Math.max(0, usableHeight));

  const labelClass = "pointer-events-none select-none rounded bg-navy-900/85 px-1.5 py-0.5 text-[10px] font-semibold text-white";

  return (
    <group>
      <axesHelper args={[Math.max(lengthScene, widthScene, heightScene) * 0.4]} />
      <Html position={[lengthScene + 0.05, 0, 0]}>
        <span className={labelClass}>X — Longueur</span>
      </Html>
      <Html position={[0, 0, widthScene + 0.05]}>
        <span className={labelClass}>Y — Largeur</span>
      </Html>
      <Html position={[0, heightScene + 0.05, 0]}>
        <span className={labelClass}>Z — Hauteur</span>
      </Html>
    </group>
  );
}
