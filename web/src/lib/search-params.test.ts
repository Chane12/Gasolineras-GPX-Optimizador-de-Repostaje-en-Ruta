import { describe, expect, it } from "vitest";

import {
  normalizeOptions,
  parseAsLatLon,
  routeSourceFrom,
  searchOptionsFrom,
  serializeSearch,
} from "./search-params";

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

describe("routeSourceFrom", () => {
  const empty = { demo: false, gpx: false, origen: null, destino: null };

  it("prefers the demo, then the GPX, then origin and destination", () => {
    expect(routeSourceFrom({ ...empty, demo: true, origen: "Madrid", destino: "Valencia" })).toEqual({
      kind: "demo",
    });
    expect(routeSourceFrom({ ...empty, gpx: true })).toEqual({ kind: "gpx" });
    expect(routeSourceFrom({ ...empty, origen: " Madrid ", destino: "Valencia" })).toEqual({
      kind: "text",
      origin: "Madrid",
      destination: "Valencia",
    });
  });

  it("is null when the route is incomplete", () => {
    expect(routeSourceFrom(empty)).toBeNull();
    expect(routeSourceFrom({ ...empty, origen: "Madrid", destino: "  " })).toBeNull();
  });
});

describe("searchOptionsFrom", () => {
  it("maps the URL to the /search request, fixing out-of-range values", () => {
    expect(
      searchOptionsFrom({
        origen: "Madrid",
        destino: "Valencia",
        origenGeo: null,
        destinoGeo: null,
        gpx: false,
        demo: false,
        combustible: "diesel",
        radio: 99,
        top: 5,
        tramo: 0,
        abierta24h: true,
        vaciada: false,
        autonomia: 250,
      }),
    ).toEqual({
      fuel: "diesel",
      max_detour_km: 15,
      top_n: 5,
      segment_km: 0,
      only_24h: true,
      all_on_route: false,
      autonomy_km: 250,
      include_others: false,
    });
  });
});

describe("place coordinates in the URL", () => {
  it("writes the picked points as lat,lon with 5 decimals and reads them back", () => {
    const url = serializeSearch("/ruta", {
      origen: "Madrid",
      destino: "València",
      origenGeo: { lat: 40.416775, lon: -3.70379 },
      destinoGeo: { lat: 39.46975, lon: -0.37739 },
    });
    const params = new URL(url, "https://x.test").searchParams;

    expect(params.get("origenGeo")).toBe("40.41678,-3.70379");
    expect(parseAsLatLon.parse(params.get("destinoGeo") ?? "")).toEqual({ lat: 39.46975, lon: -0.37739 });
  });

  it("ignores broken or impossible coordinates", () => {
    expect(parseAsLatLon.parse("abc")).toBeNull();
    expect(parseAsLatLon.parse("40.4")).toBeNull();
    expect(parseAsLatLon.parse("140,-3")).toBeNull();
  });

  it("passes the picked points to the route", () => {
    expect(
      routeSourceFrom({
        demo: false,
        gpx: false,
        origen: "Madrid",
        destino: "València",
        origenGeo: { lat: 40.41678, lon: -3.70379 },
        destinoGeo: null,
      }),
    ).toEqual({
      kind: "text",
      origin: "Madrid",
      destination: "València",
      originPoint: { lat: 40.41678, lon: -3.70379 },
    });
  });
});
