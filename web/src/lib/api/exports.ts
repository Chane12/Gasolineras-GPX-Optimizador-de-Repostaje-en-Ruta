"use client";

import { useQuery } from "@tanstack/react-query";

import { type Station, stationKey } from "@/lib/map/geo";
import { formatStationName } from "@/lib/stations";

import { api, type ApiClient, type Schemas, unwrap } from "./client";

type Track = { coordinates: number[][] };

function ends(track: Track): { origin: [number, number]; destination: [number, number] } {
  const first = track.coordinates[0] ?? [0, 0];
  const last = track.coordinates.at(-1) ?? first;
  return { origin: [first[0] ?? 0, first[1] ?? 0], destination: [last[0] ?? 0, last[1] ?? 0] };
}

/**
 * Enlace de navegación de Google Maps con las paradas, preparado antes de pulsar (así el enlace es un <a>
 * normal y el navegador no lo bloquea). Google Maps admite 9 paradas intermedias: `truncated` dice cuántas
 * se quedaron fuera.
 */
export function useGmapsUrl(
  routeKey: string | null,
  track: Track | null,
  stops: readonly Station[],
  client: ApiClient = api,
) {
  return useQuery({
    queryKey: ["gmaps", routeKey, stops.map(stationKey)],
    enabled: routeKey !== null && track !== null,
    staleTime: Infinity,
    queryFn: () =>
      unwrap(
        client.POST("/export/gmaps-url", {
          body: {
            ...ends(track as Track),
            stops: stops.map((s) => ({ id: s.id ?? null, lat: s.lat, lon: s.lon })),
          },
        }),
      ),
  });
}

/** El GPX de la ruta con las paradas como waypoints (nombre y precio), descargado como archivo. */
export async function downloadGpx(
  track: Track,
  stops: readonly Station[],
  name: string,
  client: ApiClient = api,
): Promise<void> {
  const blob = await unwrap(
    client.POST("/export/gpx", {
      body: {
        name: name.slice(0, 120),
        track: track as Schemas["GpxExportRequest"]["track"],
        stops: stops.slice(0, 10).map((s) => ({
          name: formatStationName(s.name).slice(0, 120),
          lat: s.lat,
          lon: s.lon,
          price: s.price,
        })),
      },
      parseAs: "blob",
    }),
  );
  const url = URL.createObjectURL(blob as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${
    name
      .replace(/[^\p{L}\p{N}]+/gu, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase() || "ruta"
  }.gpx`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Máximo de paradas que acepta el GPX exportado (límite de la API). */
export const MAX_GPX_STOPS = 10;
