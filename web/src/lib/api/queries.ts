"use client";

import { QueryClient, useQuery } from "@tanstack/react-query";

import { api, type ApiClient, ApiError, unwrap } from "./client";

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
