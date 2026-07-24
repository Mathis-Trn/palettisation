import type { PalletConfig } from "@/domain/types";
import { domainCenterToScene, domainSizeToScene } from "./coordinate-utils";

export function PalletMesh({ config }: { config: PalletConfig }) {
  const dims = { length: config.dimensions.length, width: config.dimensions.width, height: config.emptyPalletHeightMm };
  const position = { x: 0, y: 0, z: -config.emptyPalletHeightMm };
  const center = domainCenterToScene(position, dims);
  const size = domainSizeToScene(dims);

  return (
    <group>
      <mesh position={center} castShadow receiveShadow>
        <boxGeometry args={size} />
        <meshStandardMaterial color="#b9885a" roughness={0.9} />
      </mesh>
      {/* Plancher, légèrement plus grand que la palette pour ancrer visuellement la scène. */}
      <mesh position={[center[0], center[1] - size[1] / 2 - 0.005, center[2]]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[size[0] * 3, size[2] * 3]} />
        <meshStandardMaterial color="#e7ebf1" />
      </mesh>
    </group>
  );
}
