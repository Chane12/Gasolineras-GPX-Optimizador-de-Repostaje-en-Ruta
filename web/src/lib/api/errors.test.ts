import { describe, expect, it } from "vitest";

import { MESSAGES, toApiError } from "./errors";

const response = (status: number, headers: Record<string, string> = {}) =>
  new Response(null, { status, headers });

describe("toApiError", () => {
  it("no response means no connection, and it is worth retrying", () => {
    const error = toApiError(undefined, undefined);
    expect(error.message).toBe(MESSAGES.network);
    expect(error.status).toBeNull();
    expect(error.isTransient).toBe(true);
  });

  it("uses the Spanish detail the API already sends", () => {
    const error = toApiError(response(400), { detail: "No encontramos la ubicación «Villarriba»." });
    expect(error.message).toBe("No encontramos la ubicación «Villarriba».");
    expect(error.isTransient).toBe(false);
  });

  it("schema validation errors (422, detail is a list) get a generic message", () => {
    expect(toApiError(response(422), { detail: [{ loc: ["body"], msg: "x" }] }).message).toBe(
      MESSAGES.invalid,
    );
  });

  it("429 keeps Retry-After", () => {
    const error = toApiError(response(429, { "retry-after": "42" }), { detail: "Espera un momento." });
    expect(error.retryAfterS).toBe(42);
    expect(error.message).toBe("Espera un momento.");
  });

  it("gateway errors without detail say the server is not answering", () => {
    expect(toApiError(response(502), "<html>Bad gateway</html>").message).toBe(MESSAGES.unavailable);
    expect(toApiError(response(503), undefined).isTransient).toBe(true);
  });

  it("anything else is unexpected", () => {
    expect(toApiError(response(418), {}).message).toBe(MESSAGES.unexpected);
  });
});
