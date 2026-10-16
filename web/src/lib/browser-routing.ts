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

/**
 * Puntos de la ruta `anchorM` metros antes y después de la gasolinera, en el sentido de la marcha
 * (proyección local en metros, de sobra a esta escala).
 */
export function detourAnchors(
  track: ReadonlyArray<readonly number[]>,
  station: { lat: number; lon: number },
  anchorM = DETOUR_ANCHOR_M,
): { before: LonLat; after: LonLat } {
  const meanLat = (track[0]?.[1] ?? station.lat) * (Math.PI / 180);
  const kx = 111_320 * Math.cos(meanLat);
  const ky = 110_540;
  const pts = track.map((p) => [(p[0] ?? 0) * kx, (p[1] ?? 0) * ky] as const);
  const cumulative = [0];
  for (let i = 1; i < pts.length; i++) {
    const [ax = 0, ay = 0] = pts[i - 1] ?? [];
    const [bx = 0, by = 0] = pts[i] ?? [];
    cumulative.push((cumulative[i - 1] ?? 0) + Math.hypot(bx - ax, by - ay));
  }
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
