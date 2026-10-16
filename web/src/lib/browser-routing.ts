/**
 * Plan B de rutas y desvíos: si nuestro servidor no consigue respuesta de OSRM (los servidores públicos
 * limitan a veces las direcciones compartidas del alojamiento), el navegador le pregunta directamente.
 * OSRM admite peticiones desde otras webs (CORS) y así cuentan contra la conexión de cada usuario, como
 * cualquier visitante de su web. Mismo uso moderado que el servidor (ADR 0005): pocas peticiones, con
 * tiempo máximo, y el segundo servidor solo si falla el primero.
 */

const SERVERS = [
  "https://routing.openstreetmap.de/routed-car/route/v1/driving",
  "https://router.project-osrm.org/route/v1/driving",
];
const TIMEOUT_MS = 12_000;

export type LonLat = [number, number];

export class BrowserRoutingError extends Error {}

interface OsrmRoute {
  distance: number;
  duration: number;
  geometry?: { coordinates: number[][] };
}

async function askOsrm(
  points: readonly LonLat[],
  overview: "full" | "false",
  fetcher: typeof fetch,
): Promise<OsrmRoute> {
  const path = points.map(([lon, lat]) => `${lon.toFixed(6)},${lat.toFixed(6)}`).join(";");
  const query =
    overview === "full"
      ? "overview=full&geometries=geojson&steps=false&alternatives=false"
      : "overview=false&steps=false&alternatives=false";
  for (const server of SERVERS) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetcher(`${server}/${path}?${query}`, { signal: controller.signal });
      if (!response.ok) continue;
      const data = (await response.json()) as { code?: string; routes?: OsrmRoute[] };
      const route = data.routes?.[0];
      if (data.code === "Ok" && route) return route;
    } catch {
      // Sin red, tiempo agotado o respuesta rara: se prueba el siguiente servidor.
    } finally {
      clearTimeout(timer);
    }
  }
  throw new BrowserRoutingError("El servicio de rutas por carretera no responde ahora mismo.");
}

/** Ruta por carretera entre los puntos dados ([lon, lat]), con su geometría completa. */
export async function routeInBrowser(points: readonly LonLat[], fetcher: typeof fetch = fetch) {
  const route = await askOsrm(points, "full", fetcher);
  const coordinates = route.geometry?.coordinates ?? [];
  if (coordinates.length < 2) throw new BrowserRoutingError("La ruta devuelta es demasiado corta.");
  return { coordinates, distanceKm: route.distance / 1000, durationMin: route.duration / 60 };
}

/** Distancia y duración por carretera pasando por los puntos dados, sin geometría. */
export async function metricsInBrowser(points: readonly LonLat[], fetcher: typeof fetch = fetch) {
  const route = await askOsrm(points, "false", fetcher);
  return { distanceKm: route.distance / 1000, durationMin: route.duration / 60 };
}

/** Distancia del desvío para decidir los puntos de antes y después (la misma que usa el servidor). */
export const DETOUR_ANCHOR_M = 2000;

/** El track en metros (proyección local, de sobra a esta escala) y lo recorrido hasta cada punto. */
function measure(track: ReadonlyArray<readonly number[]>, refLat: number) {
  const kx = 111_320 * Math.cos(refLat * (Math.PI / 180));
  const ky = 110_540;
  const pts = track.map((p) => [(p[0] ?? 0) * kx, (p[1] ?? 0) * ky] as const);
  const cumulative = [0];
  for (let i = 1; i < pts.length; i++) {
    const [ax = 0, ay = 0] = pts[i - 1] ?? [];
    const [bx = 0, by = 0] = pts[i] ?? [];
    cumulative.push((cumulative[i - 1] ?? 0) + Math.hypot(bx - ax, by - ay));
  }
  return { kx, ky, pts, cumulative };
}

/** Metros recorridos por la ruta hasta el punto más cercano a la gasolinera. */
function alongTrack(geo: ReturnType<typeof measure>, station: { lat: number; lon: number }): number {
  const { kx, ky, pts, cumulative } = geo;
  const x = station.lon * kx;
  const y = station.lat * ky;
  let best = Infinity;
  let along = 0;
  for (let i = 0; i + 1 < pts.length; i++) {
    const [ax = 0, ay = 0] = pts[i] ?? [];
    const [bx = 0, by = 0] = pts[i + 1] ?? [];
    const dx = bx - ax;
    const dy = by - ay;
    const len2 = dx * dx + dy * dy || 1e-9;
    const t = Math.min(1, Math.max(0, ((x - ax) * dx + (y - ay) * dy) / len2));
    const d = Math.hypot(x - (ax + t * dx), y - (ay + t * dy));
    if (d < best) {
      best = d;
      along = (cumulative[i] ?? 0) + t * Math.sqrt(len2);
    }
  }
  return along;
}

/**
 * Puntos de la ruta `anchorM` metros antes y después de la gasolinera, en el sentido de la marcha
 * (proyección local en metros, de sobra a esta escala).
 */
export function detourAnchors(
  track: ReadonlyArray<readonly number[]>,
  station: { lat: number; lon: number },
  anchorM = DETOUR_ANCHOR_M,
): { before: LonLat; after: LonLat } {
  const geo = measure(track, track[0]?.[1] ?? station.lat);
  const { cumulative } = geo;
  const along = alongTrack(geo, station);
  const total = cumulative.at(-1) ?? 0;
  const at = (distance: number): LonLat => {
    const target = Math.min(total, Math.max(0, distance));
    let i = 0;
    while (i + 1 < cumulative.length - 1 && (cumulative[i + 1] ?? 0) < target) i++;
    const start = cumulative[i] ?? 0;
    const end = cumulative[i + 1] ?? start;
    const t = end > start ? (target - start) / (end - start) : 0;
    const a = track[i] ?? track[0] ?? [0, 0];
    const b = track[i + 1] ?? a;
    return [(a[0] ?? 0) + t * ((b[0] ?? 0) - (a[0] ?? 0)), (a[1] ?? 0) + t * ((b[1] ?? 0) - (a[1] ?? 0))];
  };
  return { before: at(along - anchorM), after: at(along + anchorM) };
}

/** Cuánto antes y después de cada parada se sale y se vuelve a la ruta en el GPX exportado. */
export const SPLICE_ANCHOR_M = 1000;

/**
 * El track desviado por cada parada para el GPX: se sustituye el tramo de la ruta alrededor de cada
 * gasolinera (desde `anchorM` antes hasta `anchorM` después) por el camino real por carretera que entra
 * en ella. Las paradas a menos de 2 × `anchorM` entre sí van en la misma petición. Si OSRM no responde
 * para alguna, devuelve `null` (el servidor lo intentará por su cuenta).
 */
export async function spliceStopsInBrowser(
  track: ReadonlyArray<readonly number[]>,
  stops: ReadonlyArray<{ lat: number; lon: number }>,
  fetcher: typeof fetch = fetch,
  anchorM = SPLICE_ANCHOR_M,
): Promise<number[][] | null> {
  if (track.length < 2 || stops.length === 0) return track.map((p) => [...p]);
  const geo = measure(track, track[0]?.[1] ?? 0);
  const { cumulative } = geo;
  const lastIndex = track.length - 1;
  // Índice del último punto del track a `distance` metros o antes / del primero a esa distancia o después.
  const indexBefore = (distance: number) => {
    let i = 0;
    while (i < lastIndex && (cumulative[i + 1] ?? Infinity) <= distance) i++;
    return i;
  };
  const indexAfter = (distance: number) => {
    let i = lastIndex;
    while (i > 0 && (cumulative[i - 1] ?? -Infinity) >= distance) i--;
    return i;
  };

  const placed = stops
    .map((stop) => ({ stop, along: alongTrack(geo, stop) }))
    .sort((a, b) => a.along - b.along);
  const groups: { from: number; to: number; stops: { lat: number; lon: number }[] }[] = [];
  for (const { stop, along } of placed) {
    const from = indexBefore(along - anchorM);
    const to = Math.min(lastIndex, Math.max(from + 1, indexAfter(along + anchorM)));
    const last = groups.at(-1);
    if (last && from <= last.to) {
      last.to = Math.max(last.to, to);
      last.stops.push(stop);
    } else {
      groups.push({ from, to, stops: [stop] });
    }
  }

  const pieces: number[][][] = [];
  let next = 0;
  for (const group of groups) {
    const start = track[group.from] ?? [0, 0];
    const end = track[group.to] ?? start;
    let road: number[][];
    try {
      road = (
        await routeInBrowser(
          [
            [start[0] ?? 0, start[1] ?? 0],
            ...group.stops.map((s): LonLat => [s.lon, s.lat]),
            [end[0] ?? 0, end[1] ?? 0],
          ],
          fetcher,
        )
      ).coordinates;
    } catch {
      return null;
    }
    pieces.push(track.slice(next, group.from + 1).map((p) => [...p]));
    // Los extremos son puntos del track: el camino por carretera empieza y acaba en ellos.
    pieces.push(road.slice(1, -1));
    next = group.to;
  }
  pieces.push(track.slice(next).map((p) => [...p]));
  return pieces.flat();
}

/** Desvío real (como el del servidor): ruta(antes → gasolinera → después) − ruta(antes → después). */
export async function detourInBrowser(
  track: ReadonlyArray<readonly number[]>,
  station: { lat: number; lon: number },
  fetcher: typeof fetch = fetch,
): Promise<{ km: number; minutes: number }> {
  const { before, after } = detourAnchors(track, station);
  const via = await metricsInBrowser([before, [station.lon, station.lat], after], fetcher);
  const direct = await metricsInBrowser([before, after], fetcher);
  return {
    km: Math.max(0, via.distanceKm - direct.distanceKm),
    minutes: Math.max(0, via.durationMin - direct.durationMin),
  };
}
