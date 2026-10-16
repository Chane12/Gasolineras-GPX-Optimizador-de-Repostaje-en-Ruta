import type { LayerSpecification } from "maplibre-gl";
import { describe, expect, it } from "vitest";

import { buildMapStyle, type MapPalette, readMapPalette, ROUTE_SOURCE } from "./style";

// Valores de prueba: el estilo no inventa colores, solo usa los que le da la paleta.
const palette: MapPalette = {
  bg: "token-bg",
  ink: "token-ink",
  muted: "token-muted",
  rule: "token-rule",
  accent: "token-accent",
  land: "token-land",
  contour: "token-contour",
  road: "token-road",
  roadCasing: "token-road-casing",
  water: "token-water",
};

const track = [
  [-4.6, 40.6],
  [-4.1, 40.9],
];

function layer(id: string): LayerSpecification {
  const found = buildMapStyle(palette, track).layers.find((l) => l.id === id);
  if (!found) throw new Error(`No layer ${id}`);
  return found;
}

describe("buildMapStyle", () => {
  it("draws the route from the track with the accent over a halo", () => {
    const style = buildMapStyle(palette, track);

    expect(style.sources[ROUTE_SOURCE]).toMatchObject({
      type: "geojson",
      data: { geometry: { type: "LineString", coordinates: track } },
    });
    expect(layer("route")).toMatchObject({ paint: { "line-color": "token-accent", "line-width": 5 } });
    expect(layer("route-halo")).toMatchObject({ paint: { "line-color": "token-bg" } });
  });

  it("puts the route above roads and place names above the route", () => {
    const ids = buildMapStyle(palette, track).layers.map((l) => l.id);

    expect(ids.indexOf("route-halo")).toBeGreaterThan(ids.indexOf("road-major"));
    expect(ids.indexOf("place-city")).toBeGreaterThan(ids.indexOf("route"));
  });

  it("uses OpenFreeMap tiles and atlas-style city names", () => {
    const style = buildMapStyle(palette, track);

    expect(style.sources.openmaptiles).toMatchObject({ url: "https://tiles.openfreemap.org/planet" });
    expect(layer("place-city")).toMatchObject({ layout: { "text-transform": "uppercase" } });
    expect(layer("land")).toMatchObject({ paint: { "background-color": "token-land" } });
  });

  it("only uses colours from the palette", () => {
    const used = JSON.stringify(buildMapStyle(palette, track).layers).match(/"[a-z-]+-color":"[^"]+"/g) ?? [];

    expect(used.length).toBeGreaterThan(5);
    for (const entry of used) expect(entry).toMatch(/:"token-/);
  });
});

describe("readMapPalette", () => {
  it("reads the map colours from the CSS tokens", () => {
    const element = document.createElement("div");
    element.style.setProperty("--accent", " token-from-css ");
    element.style.setProperty("--map-water", "water-from-css");
    document.body.append(element);

    const read = readMapPalette(element);

    expect(read.accent).toBe("token-from-css");
    expect(read.water).toBe("water-from-css");
    element.remove();
  });
});
