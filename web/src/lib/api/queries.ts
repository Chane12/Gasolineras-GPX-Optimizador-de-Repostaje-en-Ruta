"use client";

import { keepPreviousData, QueryClient, useQuery } from "@tanstack/react-query";

import { routeInBrowser } from "@/lib/browser-routing";
import { loadGpx } from "@/lib/gpx-store";

import { api, type ApiClient, ApiError, type Schemas, unwrap } from "./client";

const MAX_RETRIES = 3;

/** Reintentos solo para fallos transitorios (sin red, 5xx); nunca para errores del usuario (4xx). */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  return error instanceof ApiError && error.isTransient && failureCount < MAX_RETRIES;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}

/** Estado del servidor y antigüedad de los precios. Sirve también para despertar la API al entrar. */
export function useHealth(client: ApiClient = api) {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => unwrap(client.GET("/health")),
    staleTime: 60_000,
  });
}

/** Combustibles en el orden de la interfaz (cambian muy rara vez). */
export function useFuels(client: ApiClient = api) {
  return useQuery({
    queryKey: ["fuels"],
    queryFn: () => unwrap(client.GET("/fuels")),
    staleTime: Infinity,
  });
}

/** De dónde sale la ruta: texto (origen/destino), el GPX guardado en el dispositivo o la demo. */
export type RouteSource =
  | {
      kind: "text";
      origin: string;
      destination: string;
      /** El lugar elegido en las sugerencias: la API no lo vuelve a buscar por nombre. */
      originPoint?: { lat: number; lon: number };
      destinationPoint?: { lat: number; lon: number };
    }
  | { kind: "gpx" }
  | { kind: "demo" };

/** Clave corta de la ruta para las cachés (el track entero es demasiado grande para una clave). */
export function routeSourceKey(source: RouteSource): string {
  if (source.kind !== "text") return source.kind;
  const at = (p?: { lat: number; lon: number }) => (p ? `@${p.lat},${p.lon}` : "");
  return `text:${source.origin}${at(source.originPoint)}→${source.destination}${at(source.destinationPoint)}`;
}

export class MissingGpxError extends Error {
  constructor() {
    super("No encontramos tu GPX en este dispositivo. Vuelve al inicio y súbelo otra vez.");
  }
}

async function fetchRoute(client: ApiClient, source: RouteSource) {
  switch (source.kind) {
    case "text":
      try {
        return await unwrap(
          client.POST("/route/text", {
            body: {
              origin: source.origin,
              destination: source.destination,
              origin_point: source.originPoint ?? null,
              destination_point: source.destinationPoint ?? null,
            },
          }),
        );
      } catch (error) {
        // El servidor no consigue ruta (OSRM o Nominatim no le responden): plan B desde el navegador.
        if (!(error instanceof ApiError) || error.status !== 503) throw error;
        return routeWithoutServer(client, source, error);
      }
    case "demo":
      return unwrap(client.GET("/route/demo"));
    case "gpx": {
      const stored = await loadGpx();
      if (!stored) throw new MissingGpxError();
      const form = new FormData();
      form.append("file", new Blob([stored.bytes], { type: "application/gpx+xml" }), stored.name);
      // El contrato tipa el archivo como string (binario); el cuerpo real es el FormData.
      return unwrap(client.POST("/route/gpx", { body: { file: stored.name }, bodySerializer: () => form }));
    }
  }
}

/** Primer lugar sugerido para un nombre (el exacto si lo hay), para el plan B de la ruta. */
async function placeFor(client: ApiClient, text: string): Promise<{ lat: number; lon: number }> {
  const places = await unwrap(client.GET("/places/suggest", { params: { query: { q: text } } }))
    .then((r) => r.places)
    .catch(() => []);
  const wanted = normalizePlace(text);
  const place =
    places.find((p) => p.name.split(" / ").some((n) => normalizePlace(n) === wanted)) ?? places[0];
  if (!place) throw new ApiError(`No encontramos la ubicación «${text}».`, 400);
  return place;
}

/**
 * Plan B: la ruta se calcula en el navegador (OSRM directo) con los puntos elegidos o, si se escribieron a
 * mano, con el primer lugar sugerido. Si tampoco así, se muestra el error original del servidor.
 */
async function routeWithoutServer(
  client: ApiClient,
  source: Extract<RouteSource, { kind: "text" }>,
  serverError: ApiError,
) {
  try {
    const origin = source.originPoint ?? (await placeFor(client, source.origin));
    const destination = source.destinationPoint ?? (await placeFor(client, source.destination));
    const route = await routeInBrowser([
      [origin.lon, origin.lat],
      [destination.lon, destination.lat],
    ]);
    return {
      track: { type: "LineString" as const, coordinates: route.coordinates },
      point_count: route.coordinates.length,
      origin: { query: source.origin, lat: origin.lat, lon: origin.lon },
      destination: { query: source.destination, lat: destination.lat, lon: destination.lon },
      duration_min: route.durationMin,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 400) throw error;
    throw serverError;
  }
}

/** Ruta validada por la API. No caduca: el mismo origen y destino dan la misma ruta en la sesión. */
export function useRoute(source: RouteSource | null, client: ApiClient = api) {
  return useQuery({
    queryKey: ["route", source ? routeSourceKey(source) : null],
    queryFn: () => fetchRoute(client, source as RouteSource),
    enabled: source !== null,
    staleTime: Infinity,
    retry: (count, error) => {
      if (error instanceof MissingGpxError) return false;
      // Un 503 ya probó el plan B en el navegador: un solo reintento, para no hacer esperar con un error.
      if (error instanceof ApiError && error.status === 503) return count < 1;
      return shouldRetry(count, error);
    },
  });
}

export type SearchOptions = Omit<Schemas["SearchRequest"], "track">;

/** Gasolineras a lo largo de la ruta. Los precios cambian: a los 10 min se vuelven a pedir al volver. */
export function useStationSearch(
  route: { key: string; track: { type?: "LineString"; coordinates: number[][] } } | null,
  options: SearchOptions,
  client: ApiClient = api,
) {
  return useQuery({
    queryKey: ["search", route?.key ?? null, options],
    // Las coordenadas de /route son siempre pares [lon, lat]: el tipo de salida es solo más laxo.
    queryFn: () =>
      unwrap(
        client.POST("/search", {
          body: { ...options, track: route!.track as Schemas["SearchRequest"]["track"] },
        }),
      ),
    enabled: route !== null,
    staleTime: 10 * 60_000,
    // Al cambiar un filtro se siguen viendo los resultados anteriores hasta que llegan los nuevos.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === (route?.key ?? null) ? previous : undefined,
  });
}

export type PlaceSuggestion = Schemas["PlaceSuggestion"];

/** Texto normalizado para comparar lugares: sin acentos, mayúsculas ni espacios de más. */
export function normalizePlace(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

export const MIN_SUGGEST_CHARS = 2;

export function placeSuggestionsQuery(text: string, client: ApiClient = api) {
  const q = text.trim();
  return {
    queryKey: ["places", normalizePlace(q)],
    queryFn: async () => (await unwrap(client.GET("/places/suggest", { params: { query: { q } } }))).places,
    staleTime: 60 * 60_000,
    // Si Photon no responde, simplemente no hay sugerencias: nada de reintentos mientras se escribe.
    retry: false,
  };
}

/** Sugerencias de lugares para lo que se lleva escrito (la espera entre teclas se aplica fuera). */
export function usePlaceSuggestions(text: string, client: ApiClient = api) {
  return useQuery({
    ...placeSuggestionsQuery(text, client),
    enabled: normalizePlace(text).length >= MIN_SUGGEST_CHARS,
    placeholderData: keepPreviousData,
  });
}
