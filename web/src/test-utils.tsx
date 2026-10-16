import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

import { createApiClient } from "@/lib/api/client";

/** Render con un QueryClient propio del test (sin reintentos ni caché compartida). */
export function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

/** Respuesta JSON simulada. */
export function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json", ...init.headers },
    ...init,
  });
}

/** Cliente de la API cuyo fetch responde con la función dada (sin red). */
export function fakeApi(respond: (request: Request) => Response | Promise<Response>) {
  return createApiClient({
    baseUrl: "http://api.test",
    fetch: (input) => Promise.resolve(respond(input as Request)),
  });
}
