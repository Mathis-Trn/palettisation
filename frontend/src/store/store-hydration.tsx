"use client";

import { useEffect } from "react";
import { useSimulationStore } from "./simulation-store";

/** Déclenche la réhydratation du store depuis le localStorage après le montage côté client,
 *  pour éviter tout écart entre le rendu serveur et le rendu client. */
export function StoreHydration() {
  useEffect(() => {
    void useSimulationStore.persist.rehydrate();
  }, []);
  return null;
}
