import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { v4 as uuid } from "uuid";
import type { CartonLineRow, OptimizationResult, Simulation, SimulationSettings } from "@/domain/types";
import { PALLET_PRESETS, STORAGE_SCHEMA_VERSION, DEFAULT_FRAGILE_MAX_WEIGHT_ON_TOP_KG } from "@/domain/constants";

export function defaultSettings(): SimulationSettings {
  return {
    transportMode: "routier",
    palletConfig: { ...PALLET_PRESETS.routier },
    globalRotationsEnabled: true,
    optimizationLevel: "rapide",
    fragileMaxWeightOnTopKg: DEFAULT_FRAGILE_MAX_WEIGHT_ON_TOP_KG,
  };
}

function nowIso(): string {
  return new Date().toISOString();
}

function createBlankSimulation(name: string): Simulation {
  const id = uuid();
  return {
    id,
    name,
    createdAtIso: nowIso(),
    updatedAtIso: nowIso(),
    settings: defaultSettings(),
    cartonLines: [],
    storageVersion: STORAGE_SCHEMA_VERSION,
  };
}

type SimulationStoreState = {
  simulations: Simulation[];
  hasHydrated: boolean;
  setHasHydrated: (value: boolean) => void;

  createSimulation: (name?: string) => string;
  duplicateSimulation: (id: string) => string | null;
  deleteSimulation: (id: string) => void;
  renameSimulation: (id: string, name: string) => void;

  updateSettings: (id: string, settings: Partial<SimulationSettings>) => void;
  replaceCartonLines: (id: string, lines: CartonLineRow[]) => void;
  addCartonLine: (id: string, line: Omit<CartonLineRow, "id">) => void;
  updateCartonLine: (id: string, lineId: string, patch: Partial<CartonLineRow>) => void;
  removeCartonLine: (id: string, lineId: string) => void;
  duplicateCartonLine: (id: string, lineId: string) => void;

  setResult: (id: string, result: OptimizationResult | undefined) => void;
  setActiveJob: (id: string, jobId: string, createdAtIso: string) => void;
  clearActiveJob: (id: string) => void;
  getSimulation: (id: string) => Simulation | undefined;
};

export const useSimulationStore = create<SimulationStoreState>()(
  persist(
    (set, get) => ({
      simulations: [],
      hasHydrated: false,
      setHasHydrated: (value) => set({ hasHydrated: value }),

      createSimulation: (name) => {
        const simulation = createBlankSimulation(name?.trim() || `Simulation du ${new Date().toLocaleDateString("fr-FR")}`);
        set((state) => ({ simulations: [simulation, ...state.simulations] }));
        return simulation.id;
      },

      duplicateSimulation: (id) => {
        const source = get().simulations.find((s) => s.id === id);
        if (!source) return null;
        const copy: Simulation = {
          ...source,
          id: uuid(),
          name: `${source.name} (copie)`,
          createdAtIso: nowIso(),
          updatedAtIso: nowIso(),
          cartonLines: source.cartonLines.map((line) => ({ ...line, id: uuid() })),
        };
        set((state) => ({ simulations: [copy, ...state.simulations] }));
        return copy.id;
      },

      deleteSimulation: (id) => {
        set((state) => ({ simulations: state.simulations.filter((s) => s.id !== id) }));
      },

      renameSimulation: (id, name) => {
        set((state) => ({
          simulations: state.simulations.map((s) => (s.id === id ? { ...s, name, updatedAtIso: nowIso() } : s)),
        }));
      },

      updateSettings: (id, settingsPatch) => {
        set((state) => ({
          simulations: state.simulations.map((s) =>
            s.id === id ? { ...s, settings: { ...s.settings, ...settingsPatch }, updatedAtIso: nowIso() } : s
          ),
        }));
      },

      replaceCartonLines: (id, lines) => {
        set((state) => ({
          simulations: state.simulations.map((s) => (s.id === id ? { ...s, cartonLines: lines, updatedAtIso: nowIso() } : s)),
        }));
      },

      addCartonLine: (id, line) => {
        set((state) => ({
          simulations: state.simulations.map((s) =>
            s.id === id ? { ...s, cartonLines: [...s.cartonLines, { ...line, id: uuid() }], updatedAtIso: nowIso() } : s
          ),
        }));
      },

      updateCartonLine: (id, lineId, patch) => {
        set((state) => ({
          simulations: state.simulations.map((s) =>
            s.id === id
              ? {
                  ...s,
                  cartonLines: s.cartonLines.map((line) => (line.id === lineId ? { ...line, ...patch } : line)),
                  updatedAtIso: nowIso(),
                }
              : s
          ),
        }));
      },

      removeCartonLine: (id, lineId) => {
        set((state) => ({
          simulations: state.simulations.map((s) =>
            s.id === id ? { ...s, cartonLines: s.cartonLines.filter((line) => line.id !== lineId), updatedAtIso: nowIso() } : s
          ),
        }));
      },

      duplicateCartonLine: (id, lineId) => {
        set((state) => ({
          simulations: state.simulations.map((s) => {
            if (s.id !== id) return s;
            const source = s.cartonLines.find((line) => line.id === lineId);
            if (!source) return s;
            const index = s.cartonLines.findIndex((line) => line.id === lineId);
            const copy: CartonLineRow = { ...source, id: uuid(), sku: `${source.sku}-copie` };
            const next = [...s.cartonLines];
            next.splice(index + 1, 0, copy);
            return { ...s, cartonLines: next, updatedAtIso: nowIso() };
          }),
        }));
      },

      setResult: (id, result) => {
        set((state) => ({
          simulations: state.simulations.map((s) => (s.id === id ? { ...s, lastResult: result, updatedAtIso: nowIso() } : s)),
        }));
      },

      setActiveJob: (id, jobId, createdAtIso) => {
        set((state) => ({
          simulations: state.simulations.map((s) =>
            s.id === id ? { ...s, activeJobId: jobId, activeJobCreatedAtIso: createdAtIso } : s
          ),
        }));
      },

      clearActiveJob: (id) => {
        set((state) => ({
          simulations: state.simulations.map((s) =>
            s.id === id ? { ...s, activeJobId: undefined, activeJobCreatedAtIso: undefined } : s
          ),
        }));
      },

      getSimulation: (id) => get().simulations.find((s) => s.id === id),
    }),
    {
      name: "palettisation3d.simulations",
      version: STORAGE_SCHEMA_VERSION,
      storage: createJSONStorage(() => localStorage),
      skipHydration: true,
      partialize: (state) => ({ simulations: state.simulations }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
