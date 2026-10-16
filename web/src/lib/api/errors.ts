/** Error de la API ya traducido a un mensaje para el usuario (en español). */
export class ApiError extends Error {
  constructor(
    message: string,
    /** Código HTTP; null si no hubo respuesta (sin conexión, servidor inalcanzable). */
    readonly status: number | null,
    /** Segundos a esperar antes de reintentar (429). */
    readonly retryAfterS: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Merece la pena reintentar automáticamente: sin conexión o fallo temporal del servidor. */
  get isTransient(): boolean {
    return this.status === null || this.status >= 500;
  }
}

export const MESSAGES = {
  network: "No hay conexión con el servidor. Comprueba tu conexión e inténtalo de nuevo.",
  invalid: "Algún dato no es válido. Revísalo e inténtalo de nuevo.",
  tooMany: "Has hecho demasiadas peticiones seguidas. Espera un momento y vuelve a intentarlo.",
  unavailable: "El servidor no responde ahora mismo. Inténtalo de nuevo en unos segundos.",
  unexpected: "Ha ocurrido un error inesperado. Inténtalo de nuevo.",
} as const;

function detailOf(body: unknown): string | null {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return null;
}

/**
 * Convierte una respuesta fallida en ApiError. La API ya explica sus errores en español en `detail`
 * (400, 413, 429, 503…); solo se inventa el mensaje cuando no lo trae (422 de validación, proxies, red).
 */
export function toApiError(response: Response | undefined, body: unknown): ApiError {
  if (!response) return new ApiError(MESSAGES.network, null);

  const { status } = response;
  const retryAfter = Number(response.headers.get("retry-after"));
  const retryAfterS = Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null;
  const detail = detailOf(body);

  if (status === 422) return new ApiError(MESSAGES.invalid, status);
  if (detail) return new ApiError(detail, status, retryAfterS);
  if (status === 429) return new ApiError(MESSAGES.tooMany, status, retryAfterS);
  if (status === 502 || status === 503 || status === 504) return new ApiError(MESSAGES.unavailable, status);
  return new ApiError(MESSAGES.unexpected, status);
}
