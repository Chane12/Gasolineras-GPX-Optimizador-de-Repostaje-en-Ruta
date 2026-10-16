/**
 * Planificar los repostajes (opciones avanzadas, punto 10a): qué paradas hacer y cuánto echar en cada una
 * para no bajar nunca de la reserva. Sin React y sin red; todo en km de autonomía (el combustible se mide
 * por los km que da), así que no hace falta saber litros ni consumo.
 *
 * Programación dinámica exacta sobre el nivel del depósito (en pasos de pocos km): minimiza lo que se paga
 * más un coste fijo por parada. Ese coste es pequeño en "lo más barato" (evita parar a echar un poco para
 * ahorrar una milésima) y grande en "menos paradas" (solo se para cuando compensa).
 */

export interface PlanStation {
  key: string;
  km: number;
  price: number;
}

export type PlanMode = "cheapest" | "fewest";

export interface PlanSettings {
  /** Km que da el depósito lleno. */
  autonomyKm: number;
  /** Con cuánto se sale, de 0 a 1 (fracción del depósito). */
  startFraction: number;
  /** Km por debajo de los que no se quiere bajar nunca. */
  reserveKm: number;
  mode: PlanMode;
}

export interface PlannedStop {
  key: string;
  km: number;
  price: number;
  /** Lo que se echa, como fracción del depósito (0–1]. */
  fill: number;
  /** Se llena el depósito. */
  full: boolean;
}

export type RefuelPlan =
  | { status: "ok"; stops: PlannedStop[]; averagePrice: number | null }
  /** Con esos datos no se llega: el tramo sin gasolinera alcanzable. */
  | { status: "impossible"; fromKm: number; toKm: number; reason: "gap" | "start-below-reserve" };

const EPS = 1e-9;
/** Niveles del depósito como máximo (el paso es de 1 km, o más con autonomías de más de 200 km). */
const MAX_LEVELS = 200;
/** Coste fijo por parada, en fracción de un depósito lleno al precio de referencia. */
const STOP_PENALTY: Record<PlanMode, number> = { cheapest: 0.02, fewest: 0.5 };

export function planRefuels(
  stations: readonly PlanStation[],
  routeKm: number,
  settings: PlanSettings,
  /** Solo para tests: coste fijo por parada (en precio × km) en lugar del de cada modo. */
  options: { stopPenalty?: number } = {},
): RefuelPlan {
  const capacity = settings.autonomyKm;
  const reserve = Math.min(Math.max(0, settings.reserveKm), capacity);
  // Se trabaja con lo que hay por encima de la reserva: llegar con 0 = llegar justo con la reserva.
  const usableKm = capacity - reserve;
  const startKm = settings.startFraction * capacity - reserve;
  if (startKm < -EPS) return { status: "impossible", fromKm: 0, toKm: 0, reason: "start-below-reserve" };

  const sorted = [...stations].filter((s) => s.km > 0 && s.km < routeKm).sort((a, b) => a.km - b.km);
  const points = [...sorted.map((s) => s.km), routeKm];

  // Tramos imposibles, para decir dónde: hasta la primera gasolinera con lo que se lleva, o entre dos
  // seguidas con el depósito lleno.
  const firstPoint = points[0] ?? routeKm;
  if (firstPoint > startKm + EPS) return { status: "impossible", fromKm: 0, toKm: firstPoint, reason: "gap" };
  for (let i = 0; i + 1 < points.length; i++) {
    const from = points[i] ?? 0;
    const to = points[i + 1] ?? routeKm;
    if (to - from > usableKm + EPS && to > startKm + EPS) {
      return { status: "impossible", fromKm: from, toKm: to, reason: "gap" };
    }
  }

  const unit = Math.max(1, usableKm / MAX_LEVELS);
  const levels = Math.max(0, Math.floor(usableKm / unit + 1e-6));
  // Posiciones en niveles, redondeadas una sola vez: los tramos suman exactamente el total de la ruta.
  const at = (km: number) => Math.round(km / unit);
  const start = Math.min(levels, Math.round(Math.max(0, startKm) / unit));
  const referencePrice = sorted.length > 0 ? Math.max(...sorted.map((s) => s.price)) : 0;
  const penalty = options.stopPenalty ?? STOP_PENALTY[settings.mode] * capacity * referencePrice;

  // cost[l]: lo mínimo pagado (más paradas) para llegar al punto actual con l niveles en el depósito.
  let cost = new Float64Array(levels + 1).fill(Infinity);
  const firstLevel = start - at(firstPoint);
  if (firstLevel >= 0) cost[firstLevel] = 0;
  // Para reconstruir el plan: en cada gasolinera, con qué nivel se llegó y cuánto se compró.
  const arrivedWith: Int32Array[] = [];
  const boughtLevels: Int32Array[] = [];

  sorted.forEach((station, i) => {
    const distance = at(points[i + 1] ?? routeKm) - at(station.km);
    const next = new Float64Array(levels + 1).fill(Infinity);
    const from = new Int32Array(levels + 1).fill(-1);
    const bought = new Int32Array(levels + 1);
    for (let a = 0; a <= levels; a++) {
      const base = cost[a] ?? Infinity;
      if (base === Infinity) continue;
      for (let b = Math.max(0, distance - a); a + b <= levels; b++) {
        const left = a + b - distance;
        const total = base + (b > 0 ? b * unit * station.price + penalty : 0);
        if (total < (next[left] ?? Infinity) - 1e-9) {
          next[left] = total;
          from[left] = a;
          bought[left] = b;
        }
      }
    }
    arrivedWith.push(from);
    boughtLevels.push(bought);
    cost = next;
  });

  // Destino: el nivel con el que se llega pagando menos.
  let level = -1;
  let best = Infinity;
  cost.forEach((c, l) => {
    if (c < best - 1e-9) {
      best = c;
      level = l;
    }
  });
  if (level < 0) return { status: "impossible", fromKm: 0, toKm: routeKm, reason: "gap" };

  const stops: PlannedStop[] = [];
  let paid = 0;
  let boughtKm = 0;
  for (let i = sorted.length - 1; i >= 0; i--) {
    const a = arrivedWith[i]?.[level] ?? -1;
    const b = boughtLevels[i]?.[level] ?? 0;
    const station = sorted[i];
    if (a < 0 || !station) break;
    if (b > 0) {
      const km = b * unit;
      stops.unshift({
        key: station.key,
        km: station.km,
        price: station.price,
        fill: Math.min(1, km / capacity),
        full: a + b >= levels,
      });
      paid += km * station.price;
      boughtKm += km;
    }
    level = a;
  }
  return { status: "ok", stops, averagePrice: boughtKm > 0 ? paid / boughtKm : null };
}
