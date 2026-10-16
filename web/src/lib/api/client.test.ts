import { describe, expect, it } from "vitest";

import { fakeApi, jsonResponse } from "@/test-utils";

import { ApiError, unwrap } from "./client";
import { MESSAGES } from "./errors";

describe("api client", () => {
  it("returns typed data from the contract", async () => {
    const client = fakeApi(() => jsonResponse([{ id: "diesel", label: "Diésel (Gasoil A)" }]));

    const fuels = await unwrap(client.GET("/fuels"));

    expect(fuels[0]?.label).toBe("Diésel (Gasoil A)");
  });

  it("sends JSON bodies to the right path", async () => {
    let seen: { url: string; body: unknown } | null = null;
    const client = fakeApi(async (request) => {
      seen = { url: request.url, body: await request.json() };
      return jsonResponse({ detail: "No encontramos la ubicación «X»." }, { status: 400 });
    });

    await expect(
      unwrap(client.POST("/route/text", { body: { origin: "X", destination: "Y" } })),
    ).rejects.toThrow("No encontramos la ubicación «X».");
    expect(seen).toEqual({ url: "http://api.test/route/text", body: { origin: "X", destination: "Y" } });
  });

  it("turns a network failure into an ApiError with a Spanish message", async () => {
    const client = fakeApi(() => {
      throw new TypeError("Failed to fetch");
    });

    const error = await unwrap(client.GET("/health")).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe(MESSAGES.network);
  });
});
