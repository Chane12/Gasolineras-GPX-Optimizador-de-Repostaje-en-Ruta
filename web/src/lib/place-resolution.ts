/**
 * Al buscar con un lugar escrito a mano (sin elegir una sugerencia), se comprueba antes de salir del
 * inicio. Así un error ("Mdrid") se arregla en su campo, con alternativas, y no en la pantalla de resultados.
 */
import { normalizePlace, type PlaceSuggestion } from "@/lib/api/queries";

export type Resolution =
  /** El lugar exacto, por haberlo elegido o porque el nombre coincide con la primera sugerencia que se llama así. */
  | { status: "found"; place: PlaceSuggestion }
  /** No lo pudimos comprobar (Photon no responde): se busca por nombre en la API, como siempre. */
  | { status: "unchecked" }
  /** No existe con ese nombre: alternativas parecidas (puede estar vacía). */
  | { status: "unknown"; alternatives: PlaceSuggestion[] };

export const MAX_ALTERNATIVES = 3;

export async function resolvePlace(
  value: { text: string; place?: PlaceSuggestion },
  suggest: (text: string) => Promise<PlaceSuggestion[]>,
): Promise<Resolution> {
  if (value.place) return { status: "found", place: value.place };
  let suggestions: PlaceSuggestion[];
  try {
    suggestions = await suggest(value.text);
  } catch {
    return { status: "unchecked" };
  }
  const wanted = normalizePlace(value.text);
  // "València / Valencia" o "Donostia / San Sebastián": vale cualquiera de los nombres.
  const exact = suggestions.find((s) => s.name.split(" / ").some((name) => normalizePlace(name) === wanted));
  if (exact) return { status: "found", place: exact };
  return { status: "unknown", alternatives: suggestions.slice(0, MAX_ALTERNATIVES) };
}
