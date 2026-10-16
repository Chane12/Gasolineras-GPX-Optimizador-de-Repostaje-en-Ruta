/**
 * "Solo las de mi lado" (opciones avanzadas, punto 10d): a qué lado de la carretera queda cada gasolinera
 * según el sentido de la marcha (el del track). Se circula por la derecha: en autovía, las de la izquierda
 * obligan a cruzar (ir a la salida siguiente y volver).
 *
 * Solo se dice para las que están pegadas a la ruta (`MAX_SIDE_DISTANCE_M`): más lejos se llega por una
 * salida y el lado da igual. Validado contra el campo `Margen` del MITECO en la A-3 Madrid → Valencia
 * (sentido del kilometraje): 32 de 34 coinciden a menos de 100 m (y 9 de 9 a menos de 50 m).
 */

export type RoadSide = "right" | "left";

export const MAX_SIDE_DISTANCE_M = 100;

export function roadSides(
  track: ReadonlyArray<readonly number[]>,
  stations: ReadonlyArray<{ key: string; lat: number; lon: number }>,
  maxDistanceM = MAX_SIDE_DISTANCE_M,
): Map<string, RoadSide> {
  const sides = new Map<string, RoadSide>();
  if (track.length < 2) return sides;
  // Proyección local en metros (equirectangular): de sobra para decidir el lado a escala de 100 m.
  const meanLat = track.reduce((sum, p) => sum + (p[1] ?? 0), 0) / track.length;
  const kx = 111_320 * Math.cos((meanLat * Math.PI) / 180);
  const ky = 110_540;
  const xs = track.map((p) => (p[0] ?? 0) * kx);
  const ys = track.map((p) => (p[1] ?? 0) * ky);
  const minX = Math.min(...xs) - maxDistanceM;
  const maxX = Math.max(...xs) + maxDistanceM;
  const minY = Math.min(...ys) - maxDistanceM;
  const maxY = Math.max(...ys) + maxDistanceM;

  for (const station of stations) {
    const x = station.lon * kx;
    const y = station.lat * ky;
    if (x < minX || x > maxX || y < minY || y > maxY) continue;
    let best = Infinity;
    let cross = 0;
    for (let i = 0; i + 1 < xs.length; i++) {
      const ax = xs[i] ?? 0;
      const ay = ys[i] ?? 0;
      const dx = (xs[i + 1] ?? 0) - ax;
      const dy = (ys[i + 1] ?? 0) - ay;
      const len2 = dx * dx + dy * dy || 1e-9;
      const t = Math.min(1, Math.max(0, ((x - ax) * dx + (y - ay) * dy) / len2));
      const distance = Math.hypot(x - (ax + t * dx), y - (ay + t * dy));
      if (distance < best) {
        best = distance;
        cross = dx * (y - ay) - dy * (x - ax);
      }
    }
    if (best <= maxDistanceM && cross !== 0) sides.set(station.key, cross > 0 ? "left" : "right");
  }
  return sides;
}
