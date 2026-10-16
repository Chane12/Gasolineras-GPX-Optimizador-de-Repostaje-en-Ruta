/**
 * Estilo propio del mapa (docs/web/diseno.md, «Mapa»): neutro, con la ruta como elemento más fuerte.
 * Teselas vectoriales de OpenFreeMap (esquema OpenMapTiles). Los colores no se escriben aquí: salen de
 * los tokens CSS (globals.css) en tiempo de ejecución, así que el modo noche llega solo.
 */
import type { ExpressionSpecification, LayerSpecification, StyleSpecification } from "maplibre-gl";

/** Colores del mapa, leídos de los tokens de globals.css. */
export interface MapPalette {
  bg: string;
  ink: string;
  muted: string;
  rule: string;
  accent: string;
  land: string;
  contour: string;
  road: string;
  roadCasing: string;
  water: string;
}

const PALETTE_TOKENS: Record<keyof MapPalette, string> = {
  bg: "--bg",
  ink: "--ink",
  muted: "--muted",
  rule: "--rule",
  accent: "--accent",
  land: "--map-land",
  contour: "--map-contour",
  road: "--map-road",
  roadCasing: "--map-road-casing",
  water: "--map-water",
};

/** Lee la paleta de los tokens CSS vigentes (claro u oscuro, según el sistema). */
export function readMapPalette(element: Element = document.documentElement): MapPalette {
  const css = getComputedStyle(element);
  const entries = Object.entries(PALETTE_TOKENS).map(([key, token]) => [
    key,
    css.getPropertyValue(token).trim(),
  ]);
  return Object.fromEntries(entries) as unknown as MapPalette;
}

export const OPENFREEMAP_TILES = "https://tiles.openfreemap.org/planet";
const GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
// Familjen Grotesk no existe como glifos del mapa: Noto Sans es la más neutra de las que sirve OpenFreeMap.
const FONT_BOLD = ["Noto Sans Bold"];
const FONT_ITALIC = ["Noto Sans Italic"];

export const ROUTE_SOURCE = "route";

/** Track de la ruta en GeoJSON ([lon, lat]). */
export type TrackCoordinates = ReadonlyArray<readonly [number, number] | readonly number[]>;

const name: ExpressionSpecification = ["coalesce", ["get", "name:es"], ["get", "name"]];

/** Ancho que crece con el zoom (carreteras): [zoom, ancho] por parejas. */
function widthByZoom(...stops: number[]): ExpressionSpecification {
  return ["interpolate", ["exponential", 1.4], ["zoom"], ...stops];
}

const MAJOR_ROADS = ["motorway", "trunk", "primary"];
const MINOR_ROADS = ["secondary", "tertiary"];
const LOCAL_ROADS = ["minor", "service"];

function roadLayers(p: MapPalette): LayerSpecification[] {
  const roads = (id: string, classes: string[], minzoom: number, casing: number[], fill: number[]) => {
    const filter: ExpressionSpecification = [
      "all",
      ["match", ["get", "class"], classes, true, false],
      ["!=", ["get", "brunnel"], "tunnel"],
    ];
    return [
      {
        id: `${id}-casing`,
        type: "line",
        source: "openmaptiles",
        "source-layer": "transportation",
        minzoom,
        filter,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": p.roadCasing, "line-width": widthByZoom(...casing) },
      },
      {
        id,
        type: "line",
        source: "openmaptiles",
        "source-layer": "transportation",
        minzoom,
        filter,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": p.road, "line-width": widthByZoom(...fill) },
      },
    ] satisfies LayerSpecification[];
  };
  return [
    ...roads("road-local", LOCAL_ROADS, 12, [12, 1.5, 18, 14], [12, 0.6, 18, 11]),
    ...roads("road-minor", MINOR_ROADS, 8, [8, 1.2, 12, 4, 18, 22], [8, 0.4, 12, 2.6, 18, 18]),
    ...roads("road-major", MAJOR_ROADS, 5, [5, 1.4, 10, 5, 18, 28], [5, 0.6, 10, 3.4, 18, 24]),
  ];
}

function baseLayers(p: MapPalette): LayerSpecification[] {
  return [
    { id: "land", type: "background", paint: { "background-color": p.land } },
    // OpenFreeMap no trae curvas de nivel: los bosques y parques con el tono de las curvas dan la textura.
    {
      id: "landcover-wood",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "landcover",
      filter: ["match", ["get", "class"], ["wood", "forest"], true, false],
      paint: { "fill-color": p.contour, "fill-opacity": 0.7 },
    },
    {
      id: "park",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "park",
      paint: { "fill-color": p.contour, "fill-opacity": 0.5 },
    },
    {
      id: "water",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "water",
      paint: { "fill-color": p.water },
    },
    {
      id: "waterway",
      type: "line",
      source: "openmaptiles",
      "source-layer": "waterway",
      minzoom: 8,
      paint: { "line-color": p.water, "line-width": widthByZoom(8, 0.6, 14, 2.5) },
    },
    {
      id: "boundary-country",
      type: "line",
      source: "openmaptiles",
      "source-layer": "boundary",
      filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1]],
      paint: { "line-color": p.muted, "line-width": 1, "line-dasharray": [3, 2] },
    },
    ...roadLayers(p),
  ];
}

function labelLayers(p: MapPalette): LayerSpecification[] {
  const halo = { "text-halo-color": p.land, "text-halo-width": 1.6 };
  return [
    {
      id: "water-name",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "water_name",
      minzoom: 7,
      layout: { "text-field": name, "text-font": FONT_ITALIC, "text-size": 11 },
      paint: { "text-color": p.muted, ...halo },
    },
    {
      id: "place-village",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      minzoom: 10,
      filter: ["match", ["get", "class"], ["village", "suburb"], true, false],
      layout: { "text-field": name, "text-font": FONT_BOLD, "text-size": 11 },
      paint: { "text-color": p.muted, ...halo },
    },
    // Ciudades en mayúsculas con interletrado, como en un atlas.
    {
      id: "place-town",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      minzoom: 8,
      filter: ["==", ["get", "class"], "town"],
      layout: {
        "text-field": name,
        "text-font": FONT_BOLD,
        "text-size": 11,
        "text-transform": "uppercase",
        "text-letter-spacing": 0.08,
      },
      paint: { "text-color": p.ink, ...halo },
    },
    {
      id: "place-city",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      minzoom: 4,
      filter: ["==", ["get", "class"], "city"],
      layout: {
        "text-field": name,
        "text-font": FONT_BOLD,
        "text-size": ["interpolate", ["linear"], ["zoom"], 5, 11, 10, 14],
        "text-transform": "uppercase",
        "text-letter-spacing": 0.1,
      },
      paint: { "text-color": p.ink, ...halo },
    },
  ];
}

/** La ruta: azul de 5 px con un halo del color del fondo (blanco en claro). */
function routeLayers(p: MapPalette): LayerSpecification[] {
  const layout = { "line-cap": "round", "line-join": "round" } as const;
  return [
    {
      id: "route-halo",
      type: "line",
      source: ROUTE_SOURCE,
      layout,
      paint: { "line-color": p.bg, "line-width": 11 },
    },
    {
      id: "route",
      type: "line",
      source: ROUTE_SOURCE,
      layout,
      paint: { "line-color": p.accent, "line-width": 5 },
    },
  ];
}

/**
 * Estilo completo de MapLibre con la ruta dentro: al cambiar de tema basta con `setStyle` de nuevo.
 * Los nombres de lugar van por encima de la ruta para que se lean.
 */
export function buildMapStyle(palette: MapPalette, track: TrackCoordinates): StyleSpecification {
  return {
    version: 8,
    glyphs: GLYPHS,
    sources: {
      openmaptiles: { type: "vector", url: OPENFREEMAP_TILES },
      [ROUTE_SOURCE]: {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: track.map(([lon, lat]) => [lon ?? 0, lat ?? 0]) },
        },
      },
    },
    layers: [...baseLayers(palette), ...routeLayers(palette), ...labelLayers(palette)],
  };
}
