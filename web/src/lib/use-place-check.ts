"use client";

import { useQueryClient } from "@tanstack/react-query";

import type { PlaceValue } from "@/components/place-input";
import { api, type ApiClient } from "@/lib/api/client";
import { type PlaceSuggestion, placeSuggestionsQuery } from "@/lib/api/queries";
import { resolvePlace } from "@/lib/place-resolution";
import type { LatLon } from "@/lib/search-params";

/** Un extremo de la ruta: el nombre y, si se conoce, el punto exacto (elegido en las sugerencias). */
export interface RouteEnd {
  text: string;
  point?: LatLon;
}

export interface PlaceProblem {
  message: string;
  alternatives: PlaceSuggestion[];
}

export type PlaceRole = "origen" | "destino";

function toRouteEnd(value: PlaceValue, place?: PlaceSuggestion): RouteEnd {
  const chosen = place ?? value.place;
  return chosen
    ? { text: chosen.name, point: { lat: chosen.lat, lon: chosen.lon } }
    : { text: value.text.trim() };
}

/**
 * Comprueba un lugar escrito antes de buscar: el exacto si se eligió o coincide con una sugerencia, o un
 * problema con alternativas para mostrarlo en su campo. Lo usan el inicio y la barra de la ruta.
 */
export function usePlaceCheck(client: ApiClient = api) {
  const queryClient = useQueryClient();
  return async function check(
    role: PlaceRole,
    value: PlaceValue,
  ): Promise<{ end?: RouteEnd; problem?: PlaceProblem }> {
    if (value.text.trim().length < 2) {
      return {
        problem: {
          message: role === "origen" ? "Escribe de dónde sales." : "Escribe a dónde vas.",
          alternatives: [],
        },
      };
    }
    const result = await resolvePlace(value, (text) =>
      queryClient.fetchQuery(placeSuggestionsQuery(text, client)),
    );
    if (result.status === "found") return { end: toRouteEnd(value, result.place) };
    if (result.status === "unchecked") return { end: toRouteEnd(value) };
    const typed = value.text.trim();
    return {
      problem: {
        message:
          result.alternatives.length > 0
            ? `«${typed}» no aparece tal cual. ¿Te refieres a…?`
            : `No encontramos «${typed}». Revisa cómo está escrito o prueba con un pueblo cercano.`,
        alternatives: result.alternatives,
      },
    };
  };
}

/** El valor del campo para un lugar ya conocido (p. ej. leído de la URL). */
export function placeValueFrom(text: string | null, point: LatLon | null): PlaceValue {
  if (!text) return { text: "" };
  return point
    ? { text, place: { name: text, context: "", lat: point.lat, lon: point.lon, kind: "" } }
    : { text };
}
