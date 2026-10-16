/** Cálculos puros del mapa (sin MapLibre), para poder probarlos sin navegador. */
import type { PlateTone } from "@/components/price-plate";
import type { Schemas } from "@/lib/api/client";

import type { TrackCoordinates } from "./style";

export type Station = Schemas["Station"];

/** [[oeste, sur], [este, norte]], el formato de `fitBounds`. */
export type Bounds = [[number, number], [number, number]];

export function trackBounds(track: TrackCoordinates): Bounds | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const [lon, lat] of track) {
    if (lon === undefined || lat === undefined) continue;
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  return Number.isFinite(west)
    ? [
        [west, south],
        [east, north],
      ]
    : null;
}

/** Identificador estable de una gasolinera (el del MITECO o, si falta, su posición). */
export function stationKey(station: Pick<Station, "id" | "lat" | "lon">): string {
  return station.id ?? `${station.lat.toFixed(5)},${station.lon.toFixed(5)}`;
}

/** Diferencia mínima (€/L) para considerar caras a algunas: por debajo, todas son «sugeridas». */
const MIN_SPREAD = 0.01;

/**
 * Tono de la placa de cada gasolinera (diseno.md): la más barata en azul, las del tercio más caro
 * del rango mostrado en gris y el resto con borde de tinta. Los empates en el mínimo son todas «best».
 */
export function plateTones(stations: readonly Pick<Station, "price">[]): PlateTone[] {
  if (stations.length === 0) return [];
  const prices = stations.map((s) => s.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const expensiveFrom = min + ((max - min) * 2) / 3;
  return prices.map((price) => {
    if (price === min) return "best";
    if (max - min >= MIN_SPREAD && price >= expensiveFrom) return "expensive";
    return "suggested";
  });
}
