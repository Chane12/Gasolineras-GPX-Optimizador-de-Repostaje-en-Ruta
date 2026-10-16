/**
 * La búsqueda vive en la URL (docs/web/plan.md): compartir el enlace es compartir la búsqueda.
 * Nombres en español porque se ven en el enlace: /ruta?origen=Madrid&destino=Valencia&combustible=diesel
 * Los valores por defecto no se escriben en la URL.
 */
import {
  createSerializer,
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  parseAsStringLiteral,
} from "nuqs/server"; // apto para servidor y cliente

import type { Schemas } from "@/lib/api/client";

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

export const searchParams = {
  origen: parseAsString,
  destino: parseAsString,
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
