// Formato de cifras para la interfaz, en español de España.

const priceFormatter = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const oneDecimal = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const twoDecimals = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** 1.639 → "1,639" (sin unidad: el precio va en mono y la unidad aparte). */
export function formatPrice(eurPerLitre: number): string {
  return priceFormatter.format(eurPerLitre);
}

/** Diferencia de precio por litro: 0.21 → "0,21". */
export function formatPriceDelta(eurPerLitre: number): string {
  return twoDecimals.format(eurPerLitre);
}

/** Importe en euros: 5.4 → "5,40". */
export function formatEuros(euros: number): string {
  return twoDecimals.format(euros);
}

/** Kilómetro de la ruta (hito): 118.4 → "118". */
export function formatKm(km: number): string {
  return String(Math.round(km));
}

/** Distancia corta (desvíos): 1.23 → "1,2". */
export function formatShortKm(km: number): string {
  return oneDecimal.format(km);
}

/** Antigüedad legible: 12 → "12 min", 190 → "3 h", 3000 → "2 días". */
export function formatAge(minutes: number): string {
  if (minutes < 60) return `${Math.max(0, Math.floor(minutes))} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "1 día" : `${days} días`;
}
