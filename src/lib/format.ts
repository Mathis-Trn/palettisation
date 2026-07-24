import type { TransportMode } from "@/domain/types";

export const TRANSPORT_MODE_LABELS: Record<TransportMode, string> = {
  routier: "Routier",
  maritime: "Maritime",
  aerien: "Aérien",
};

export function formatDateFr(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatInt(value: number): string {
  return new Intl.NumberFormat("fr-FR").format(Math.round(value));
}

export function formatMm(value: number): string {
  return `${formatInt(value)} mm`;
}

export function formatKg(value: number): string {
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(value)} kg`;
}

export function formatPercent(ratio: number): string {
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(ratio * 100)} %`;
}
