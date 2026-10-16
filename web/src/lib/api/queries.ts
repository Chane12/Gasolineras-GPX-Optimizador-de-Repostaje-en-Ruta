"use client";

import { QueryClient, useQuery } from "@tanstack/react-query";

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
  { kind: "text"; origin: string; destination: string } | { kind: "gpx" } | { kind: "demo" };

/** Clave corta de la ruta para las cachés (el track entero es demasiado grande para una clave). */
export function routeSourceKey(source: RouteSource): string {
  return source.kind === "text" ? `text:${source.origin}→${source.destination}` : source.kind;
}

export class MissingGpxError extends Error {
  constructor() {
    super("No encontramos tu GPX en este dispositivo. Vuelve al inicio y súbelo otra vez.");
  }
}

async function fetchRoute(client: ApiClient, source: RouteSource) {
  switch (source.kind) {
    case "text":
      return unwrap(
        client.POST("/route/text", { body: { origin: source.origin, destination: source.destination } }),
      );
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

/** Ruta validada por la API. No caduca: el mismo origen y destino dan la misma ruta en la sesión. */
export function useRoute(source: RouteSource | null, client: ApiClient = api) {
  return useQuery({
    queryKey: ["route", source ? routeSourceKey(source) : null],
    queryFn: () => fetchRoute(client, source as RouteSource),
    enabled: source !== null,
    staleTime: Infinity,
    retry: (count, error) => !(error instanceof MissingGpxError) && shouldRetry(count, error),
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
  });
}
