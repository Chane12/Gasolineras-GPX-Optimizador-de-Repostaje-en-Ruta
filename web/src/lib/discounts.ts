/**
 * Mis descuentos (opciones avanzadas, punto 10c): los que escribe el usuario por marca (tarjetas, apps…).
 * No hay datos oficiales de descuentos: nunca se inventan, solo se aplican los que él indica.
 */
import type { Station } from "@/lib/map/geo";

export interface Discount {
  /** Marca tal como la escribe el usuario ("Repsol", "Moeve"…): se busca dentro del rótulo. */
  brand: string;
  kind: "cents" | "percent";
  /** Céntimos por litro o porcentaje. */
  value: number;
}

/** Una gasolinera con el precio que pagará el usuario; `list_price` es el del surtidor si hay descuento. */
export type PricedStation = Station & { list_price?: number; discount_brand?: string };

export const MAX_CENTS = 50;
export const MAX_PERCENT = 30;

const normalize = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

/** ¿El rótulo es de esa marca? Palabra completa: "BP" no casa con "BPA", "Repsol" sí con "E.S REPSOL". */
export function matchesBrand(stationName: string, brand: string): boolean {
  const wanted = normalize(brand);
  if (!wanted) return false;
  return ` ${normalize(stationName)} `.includes(` ${wanted} `);
}

export function isValidDiscount(d: Discount): boolean {
  const limit = d.kind === "cents" ? MAX_CENTS : MAX_PERCENT;
  return normalize(d.brand).length > 0 && d.value > 0 && d.value <= limit;
}

/** Precio con el mejor descuento aplicable (si varios casan, el que más rebaja). */
export function applyDiscounts<T extends Station>(
  station: T,
  discounts: readonly Discount[],
): T & PricedStation {
  let best: { price: number; brand: string } | null = null;
  for (const d of discounts) {
    if (!isValidDiscount(d) || !matchesBrand(station.name, d.brand)) continue;
    const price = d.kind === "cents" ? station.price - d.value / 100 : station.price * (1 - d.value / 100);
    if (!best || price < best.price) best = { price, brand: d.brand.trim() };
  }
  if (!best) return station;
  return {
    ...station,
    price: Math.max(0, Math.round(best.price * 1000) / 1000),
    list_price: station.price,
    discount_brand: best.brand,
  };
}

/** Regla de las recomendadas (la misma que usa la API): las `topN` más baratas y la más barata de cada tramo. */
export interface RecommendationRule {
  topN: number;
  segmentKm: number;
}

/** Elige las recomendadas de una lista con la regla dada. */
export function recommend<T extends Station>(stations: readonly T[], rule: RecommendationRule): Set<T> {
  const chosen = new Set<T>([...stations].sort((a, b) => a.price - b.price).slice(0, rule.topN));
  if (rule.segmentKm > 0) {
    const bySegment = new Map<number, T>();
    for (const s of stations) {
      const segment = Math.floor(s.km_on_route / rule.segmentKm);
      const best = bySegment.get(segment);
      if (!best || s.price < best.price) bySegment.set(segment, s);
    }
    bySegment.forEach((s) => chosen.add(s));
  }
  return chosen;
}

/**
 * Recomendadas y resto con las preferencias del usuario (opciones avanzadas): sus descuentos y las marcas
 * que no quiere. Si hay alguna, las recomendadas se vuelven a elegir con los precios que pagará y sin esas
 * marcas, con la misma regla que la API; si no, se dejan las de la API.
 */
export function personalize(
  recommended: readonly Station[],
  others: readonly Station[],
  preferences: { discounts: readonly Discount[]; excludedBrands: readonly string[] },
  rule: RecommendationRule,
): { recommended: PricedStation[]; others: PricedStation[] } {
  const excluded = preferences.excludedBrands.filter((b) => b.trim());
  const hasDiscounts = preferences.discounts.some(isValidDiscount);
  if (!hasDiscounts && excluded.length === 0) return { recommended: [...recommended], others: [...others] };
  const pool = [...recommended, ...others]
    .filter((s) => !excluded.some((brand) => matchesBrand(s.name, brand)))
    .map((s) => applyDiscounts(s, preferences.discounts));
  const chosen = recommend(pool, rule);
  return {
    recommended: pool.filter((s) => chosen.has(s)).sort((a, b) => a.km_on_route - b.km_on_route),
    others: pool.filter((s) => !chosen.has(s)),
  };
}
