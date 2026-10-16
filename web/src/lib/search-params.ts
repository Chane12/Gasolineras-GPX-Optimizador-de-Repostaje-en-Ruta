/**
 * La búsqueda vive en la URL (docs/web/plan.md): compartir el enlace es compartir la búsqueda.
 * Nombres en español porque se ven en el enlace: /ruta?origen=Madrid&destino=Valencia&combustible=diesel
 * Los valores por defecto no se escriben en la URL.
 */
import {
  createParser,
  createSerializer,
  parseAsArrayOf,
  type inferParserType,
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  parseAsStringLiteral,
} from "nuqs/server"; // apto para servidor y cliente

import type { Schemas } from "@/lib/api/client";
import type { RouteSource, SearchOptions } from "@/lib/api/queries";

export type FuelId = Schemas["Fuel"]["id"];

/** Identificadores del contrato (api/openapi.json). El tipo de abajo obliga a mantenerlos completos. */
export const FUEL_IDS = [
  "gasolina_95",
  "gasolina_95_premium",
  "gasolina_98",
  "diesel",
  "diesel_premium",
  "glp",
  "gnc",
  "gnl",
  "gasoil_b",
  "gasolina_95_e10",
  "gasolina_98_e10",
  "hidrogeno",
] as const satisfies readonly FuelId[];

type MissingFuelIds = Exclude<FuelId, (typeof FUEL_IDS)[number]>;
const allFuelIdsListed: [MissingFuelIds] extends [never] ? true : false = true;
void allFuelIdsListed;

export const DEFAULT_FUEL: FuelId = "gasolina_95";

/** Límites de la API (SearchRequest): fuera de rango, la API respondería 422. */
export const LIMITS = {
  radioKm: { min: 1, max: 15, default: 5 },
  top: { min: 1, max: 20, default: 5 },
  tramoKm: { min: 10, max: 300, default: 50 },
  autonomiaKm: { min: 50, max: 2000 },
} as const;

export interface LatLon {
  lat: number;
  lon: number;
}

/** Punto "lat,lon" con 5 decimales (~1 m): el lugar elegido en las sugerencias, para no volver a buscarlo. */
export const parseAsLatLon = createParser<LatLon>({
  parse(value) {
    const [lat, lon] = value.split(",").map(Number);
    if (lat === undefined || lon === undefined || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
    return { lat, lon };
  },
  serialize: ({ lat, lon }) => `${lat.toFixed(5)},${lon.toFixed(5)}`,
  eq: (a, b) => a.lat === b.lat && a.lon === b.lon,
});

export const searchParams = {
  origen: parseAsString,
  destino: parseAsString,
  /** Coordenadas del origen elegido en las sugerencias (opcional). */
  origenGeo: parseAsLatLon,
  destinoGeo: parseAsLatLon,
  /** La ruta es el GPX guardado en el dispositivo (un archivo no cabe en la URL). */
  gpx: parseAsBoolean.withDefault(false),
  /** Ruta de ejemplo por la Sierra de Gredos. */
  demo: parseAsBoolean.withDefault(false),
  combustible: parseAsStringLiteral(FUEL_IDS).withDefault(DEFAULT_FUEL),
  radio: parseAsInteger.withDefault(LIMITS.radioKm.default),
  top: parseAsInteger.withDefault(LIMITS.top.default),
  /** Más barata cada X km; 0 = desactivado. */
  tramo: parseAsInteger.withDefault(LIMITS.tramoKm.default),
  abierta24h: parseAsBoolean.withDefault(false),
  vaciada: parseAsBoolean.withDefault(false),
  /** Autonomía del vehículo en km; 0 = sin aviso de autonomía (opcional, desactivado por defecto). */
  autonomia: parseAsInteger.withDefault(0),
  /** Paradas elegidas (id del MITECO; si falta, "lat,lon"), separadas por "~": el enlace las comparte. */
  paradas: parseAsArrayOf(parseAsString, "~").withDefault([]),
};

export const serializeSearch = createSerializer(searchParams);

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, Math.round(value)));

/** Opciones listas para la API, corrigiendo valores fuera de rango que alguien haya escrito en la URL. */
export function normalizeOptions(p: { radio: number; top: number; tramo: number; autonomia: number }): {
  radio: number;
  top: number;
  tramo: number;
  autonomia: number;
} {
  return {
    radio: clamp(p.radio, LIMITS.radioKm.min, LIMITS.radioKm.max),
    top: clamp(p.top, LIMITS.top.min, LIMITS.top.max),
    tramo: p.tramo <= 0 ? 0 : clamp(p.tramo, LIMITS.tramoKm.min, LIMITS.tramoKm.max),
    autonomia: p.autonomia <= 0 ? 0 : clamp(p.autonomia, LIMITS.autonomiaKm.min, LIMITS.autonomiaKm.max),
  };
}

export type SearchState = inferParserType<typeof searchParams>;

/** De dónde sale la ruta según la URL; null si falta (p. ej. un enlace a /ruta sin parámetros). */
export function routeSourceFrom(
  p: Pick<SearchState, "demo" | "gpx" | "origen" | "destino"> &
    Partial<Pick<SearchState, "origenGeo" | "destinoGeo">>,
): RouteSource | null {
  if (p.demo) return { kind: "demo" };
  if (p.gpx) return { kind: "gpx" };
  const origin = p.origen?.trim();
  const destination = p.destino?.trim();
  if (!origin || !destination) return null;
  return {
    kind: "text",
    origin,
    destination,
    ...(p.origenGeo ? { originPoint: p.origenGeo } : {}),
    ...(p.destinoGeo ? { destinationPoint: p.destinoGeo } : {}),
  };
}

/** Opciones de /search a partir de la URL (con los valores fuera de rango ya corregidos). */
export function searchOptionsFrom(p: SearchState): SearchOptions {
  const o = normalizeOptions(p);
  return {
    fuel: p.combustible,
    max_detour_km: o.radio,
    top_n: o.top,
    segment_km: o.tramo,
    only_24h: p.abierta24h,
    all_on_route: p.vaciada,
    autonomy_km: o.autonomia,
    include_others: false,
  };
}
