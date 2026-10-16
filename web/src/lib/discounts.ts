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

/**
 * Recomendadas y resto con los descuentos aplicados. Las recomendadas se vuelven a elegir sobre el precio que
 * pagará el usuario, con la misma regla que la API: las `topN` más baratas y la más barata de cada tramo de
 * `segmentKm` km.
 */
export function withDiscounts(
  recommended: readonly Station[],
  others: readonly Station[],
  discounts: readonly Discount[],
  rule: { topN: number; segmentKm: number },
): { recommended: PricedStation[]; others: PricedStation[] } {
  if (!discounts.some(isValidDiscount)) return { recommended: [...recommended], others: [...others] };
  const all = [...recommended, ...others].map((s) => applyDiscounts(s, discounts));
  const chosen = new Set<PricedStation>([...all].sort((a, b) => a.price - b.price).slice(0, rule.topN));
  if (rule.segmentKm > 0) {
    const bySegment = new Map<number, PricedStation>();
    for (const s of all) {
      const segment = Math.floor(s.km_on_route / rule.segmentKm);
      const best = bySegment.get(segment);
      if (!best || s.price < best.price) bySegment.set(segment, s);
    }
    bySegment.forEach((s) => chosen.add(s));
  }
  return {
    recommended: [...chosen].sort((a, b) => a.km_on_route - b.km_on_route),
    others: all.filter((s) => !chosen.has(s)),
  };
}
