import { describe, expect, it } from "vitest";

import { normalizeOptions, serializeSearch } from "./search-params";

describe("search params", () => {
  it("writes a readable URL and leaves defaults out", () => {
    expect(serializeSearch("/ruta", { origen: "Madrid", destino: "Valencia" })).toBe(
      "/ruta?origen=Madrid&destino=Valencia",
    );
  });

  it("includes non-default options", () => {
    const url = serializeSearch("/ruta", {
      origen: "Ávila",
      destino: "Segovia",
      combustible: "diesel",
      radio: 10,
      tramo: 0,
      abierta24h: true,
      autonomia: 250,
    });

    const params = new URL(url, "https://x.test").searchParams;
    expect(params.get("origen")).toBe("Ávila");
    expect(params.get("combustible")).toBe("diesel");
    expect(params.get("radio")).toBe("10");
    expect(params.get("tramo")).toBe("0");
    expect(params.get("abierta24h")).toBe("true");
    expect(params.get("autonomia")).toBe("250");
    expect(params.has("top")).toBe(false);
  });

  it("clamps out-of-range values typed into the URL", () => {
    expect(normalizeOptions({ radio: 99, top: 0, tramo: 5, autonomia: 20 })).toEqual({
      radio: 15,
      top: 1,
      tramo: 10,
      autonomia: 50,
    });
    expect(normalizeOptions({ radio: 5, top: 5, tramo: 0, autonomia: 0 })).toEqual({
      radio: 5,
      top: 5,
      tramo: 0,
      autonomia: 0,
    });
  });
});
