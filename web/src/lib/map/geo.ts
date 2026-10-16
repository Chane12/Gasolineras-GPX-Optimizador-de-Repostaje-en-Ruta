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

/** Una placa en pantalla: el punto (px) al que apunta su piquito y su prioridad (menor = más importante). */
export interface PlacedPlate {
  key: string;
  x: number;
  y: number;
  priority: number;
}

/** Tamaño de una placa en pantalla (px), con margen: el piquito apunta al centro del borde inferior. */
export const PLATE_BOX = { width: 62, height: 30 } as const;

/**
 * Placas que se taparían con otra más importante: se dejan como punto. Se colocan por prioridad (paradas y
 * resaltada primero, después la más barata y por precio), y cada una solo si no pisa a las ya colocadas.
 */
export function overlappingPlates(plates: readonly PlacedPlate[], box = PLATE_BOX): Set<string> {
  const placed: { left: number; right: number; top: number; bottom: number }[] = [];
  const hidden = new Set<string>();
  for (const plate of [...plates].sort((a, b) => a.priority - b.priority)) {
    const rect = {
      left: plate.x - box.width / 2,
      right: plate.x + box.width / 2,
      top: plate.y - box.height,
      bottom: plate.y,
    };
    const clash = placed.some(
      (p) => rect.left < p.right && rect.right > p.left && rect.top < p.bottom && rect.bottom > p.top,
    );
    if (clash) hidden.add(plate.key);
    else placed.push(rect);
  }
  return hidden;
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
