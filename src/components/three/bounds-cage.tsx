import { Edges } from "@react-three/drei";
import type { PalletConfig } from "@/domain/types";
import { domainCenterToScene, domainSizeToScene } from "./coordinate-utils";

/** Boîte transparente matérialisant le volume utile maximal (débordement inclus). */
export function BoundsCage({ config }: { config: PalletConfig }) {
  const usableHeight = config.maxHeightIncludesPallet ? config.dimensions.height - config.emptyPalletHeightMm : config.dimensions.height;
  const dims = {
    length: config.dimensions.length + config.overhangMm,
    width: config.dimensions.width + config.overhangMm,
    height: Math.max(0, usableHeight),
  };
  const center = domainCenterToScene({ x: -config.overhangMm / 2, y: -config.overhangMm / 2, z: 0 }, dims);
  const size = domainSizeToScene(dims);

  return (
    <mesh position={center}>
      <boxGeometry args={size} />
      <meshBasicMaterial transparent opacity={0.02} color="#17a6a0" depthWrite={false} />
      <Edges color="#17a6a0" />
    </mesh>
  );
}
