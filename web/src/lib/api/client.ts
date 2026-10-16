import createClient from "openapi-fetch";

import { ApiError, toApiError } from "./errors";
import type { components, paths } from "./schema";

/** Tipos del contrato, generados desde api/openapi.json (`pnpm api:types`). Nunca escritos a mano. */
export type Schemas = components["schemas"];

/** URL de la API. En local, uvicorn; en producción, la de Render (variable de entorno al construir). */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function createApiClient(options: { baseUrl?: string; fetch?: typeof globalThis.fetch } = {}) {
  return createClient<paths>({ baseUrl: options.baseUrl ?? API_URL, fetch: options.fetch });
}

export type ApiClient = ReturnType<typeof createApiClient>;

/** Cliente por defecto de la web. */
export const api = createApiClient();

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * Espera una llamada del cliente y devuelve sus datos, o lanza ApiError con un mensaje en español.
 * Ejemplo: `const fuels = await unwrap(api.GET("/fuels"));`
 */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await call;
  } catch {
    throw toApiError(undefined, undefined); // fetch rechazado: sin red o servidor inalcanzable
  }
  if (result.error !== undefined || !result.response.ok || result.data === undefined) {
    throw toApiError(result.response, result.error);
  }
  return result.data;
}

export { ApiError };
