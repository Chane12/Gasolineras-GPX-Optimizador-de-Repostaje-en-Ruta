/** Hoja de ruta (roadbook): filas de salida, paradas y llegada con km totales y parciales. Sin React. */
import type { Station } from "@/lib/map/geo";

export type RoadbookRow =
  | { kind: "start"; totalKm: 0; partialKm: null; place: string }
  | { kind: "stop"; totalKm: number; partialKm: number; station: Station }
  | { kind: "end"; totalKm: number; partialKm: number; place: string };

export function buildRoadbook(
  stops: readonly Station[],
  routeKm: number,
  places: { start: string; end: string },
): RoadbookRow[] {
  const sorted = [...stops].sort((a, b) => a.km_on_route - b.km_on_route);
  const rows: RoadbookRow[] = [{ kind: "start", totalKm: 0, partialKm: null, place: places.start }];
  let previous = 0;
  for (const station of sorted) {
    rows.push({
      kind: "stop",
      totalKm: station.km_on_route,
      partialKm: station.km_on_route - previous,
      station,
    });
    previous = station.km_on_route;
  }
  rows.push({ kind: "end", totalKm: routeKm, partialKm: Math.max(0, routeKm - previous), place: places.end });
  return rows;
}

export type LegLevel = "ok" | "warning" | "critical";

/** Cada tramo entre repostajes frente a la autonomía: aviso por encima del 80 %, crítico si la supera. */
export function legLevel(partialKm: number, autonomyKm: number): LegLevel {
  if (autonomyKm <= 0) return "ok";
  if (partialKm > autonomyKm) return "critical";
  return partialKm > autonomyKm * 0.8 ? "warning" : "ok";
}

/** El tramo más largo sin repostar (para el resumen de la autonomía). */
export function longestLegKm(rows: readonly RoadbookRow[]): number {
  return Math.max(0, ...rows.map((r) => r.partialKm ?? 0));
}
