/** Presentación de las gasolineras: nombres, horarios y cuántas recomendar (sin React, con tests). */

const LOWERCASE_WORDS = new Set(["de", "del", "la", "las", "los", "el", "y", "e", "en", "a"]);
/** Siglas habituales en los rótulos que no se tocan aunque lleven vocales. */
const ACRONYMS = new Set(["EESS", "ES", "EE.SS", "EE.SS.", "SL", "SA", "SLU", "SC", "SAT", "CV"]);

/**
 * El rótulo llega del MITECO tal cual, a menudo en mayúsculas ("E.S GREDOS"). Si está todo en mayúsculas,
 * se pasa a "E.S Gredos": las siglas cortas o con puntos se respetan y las partículas van en minúscula.
 */
export function formatStationName(name: string): string {
  const trimmed = name.trim().replace(/\s+/g, " ");
  if (/^\(?sin r[oó]tulo\)?$/i.test(trimmed)) return "Gasolinera";
  if (!trimmed || trimmed !== trimmed.toUpperCase() || !/\p{L}/u.test(trimmed)) return trimmed;
  return trimmed
    .split(" ")
    .map((word, index) => {
      const lower = word.toLocaleLowerCase("es");
      if (index > 0 && LOWERCASE_WORDS.has(lower)) return lower;
      // Siglas: con puntos (E.S, S.L.) o de 2–3 letras sin vocales (BP, GLP). "BP" sí, "SOL" no.
      if (ACRONYMS.has(word) || word.includes(".") || (word.length <= 3 && !/[AEIOUÁÉÍÓÚ]/.test(word)))
        return word;
      return lower.charAt(0).toLocaleUpperCase("es") + lower.slice(1);
    })
    .join(" ");
}

const SEGMENT = /^\s*([LMXJVSD](?:-[LMXJVSD])?)\s*:\s*(24H|(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2}))\s*$/i;

function hour(h: string, m: string): string {
  const value = Number(h);
  return m === "00" ? String(value) : `${value}:${m}`;
}

function formatSegment(match: RegExpMatchArray): { days: string; hours: string } {
  const [, days = "", whole = "", h1 = "", m1 = "", h2 = "", m2 = ""] = match;
  if (whole.toUpperCase() === "24H") return { days, hours: "24 h" };
  if (h1 === "00" && m1 === "00" && h2 === "23" && m2 === "59") return { days, hours: "24 h" };
  const end = h2 === "00" && m2 === "00" ? "24" : h2 === "23" && m2 === "59" ? "24" : hour(h2, m2);
  return { days, hours: `${hour(h1, m1)}–${end} h` };
}

/**
 * Horario corto para la lista: "24 h", "6–22 h" o, si cambia según el día, "L-V 6–22 h · S-D 7–22 h".
 * Si el MITECO lo escribe de otra forma, se devuelve tal cual (mejor el dato crudo que uno inventado).
 */
export function formatSchedule(schedule: string | null | undefined): string | null {
  const text = schedule?.trim();
  if (!text) return null;
  const parts = text.split(";").map((part) => part.match(SEGMENT));
  if (parts.some((p) => p === null)) return text;
  const segments = (parts as RegExpMatchArray[]).map(formatSegment);
  const only = segments[0];
  if (segments.length === 1 && only && only.days.toUpperCase() === "L-D") return only.hours;
  return segments.map((s) => `${s.days.toUpperCase()} ${s.hours}`).join(" · ");
}

const EARTH_RADIUS_KM = 6371.0088;

/** Longitud aproximada de un track [lon, lat] (haversine): sirve para decidir antes de buscar. */
export function trackLengthKm(track: ReadonlyArray<readonly number[]>): number {
  let total = 0;
  for (let i = 1; i < track.length; i++) {
    const [lon1 = 0, lat1 = 0] = track[i - 1] ?? [];
    const [lon2 = 0, lat2 = 0] = track[i] ?? [];
    const rad = Math.PI / 180;
    const dLat = (lat2 - lat1) * rad;
    const dLon = (lon2 - lon1) * rad;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
    total += 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
  }
  return total;
}

/** Cuántas de las más baratas recomendar, además de la más barata de cada tramo. */
export const RECOMMENDED_CHEAPEST = 4;
/** Tramos por ruta para "la más barata de cada tramo": con 4 más baratas salen unas 8–10 recomendadas. */
const SEGMENTS_PER_ROUTE = 6;

/** Longitud del tramo (km, en decenas, dentro de los límites de la API) según lo larga que sea la ruta. */
export function autoSegmentKm(routeKm: number): number {
  const rounded = Math.round(routeKm / SEGMENTS_PER_ROUTE / 10) * 10;
  return Math.min(300, Math.max(10, rounded));
}
