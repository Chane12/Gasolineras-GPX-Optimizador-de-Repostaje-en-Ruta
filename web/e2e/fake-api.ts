import type { Page, Route } from "@playwright/test";

/**
 * API simulada para la e2e: la web construida apunta a http://127.0.0.1:8000 (valor por defecto de
 * NEXT_PUBLIC_API_URL) y aquí se responden esas peticiones con datos fijos. Las teselas del mapa se
 * bloquean: la prueba no usa la red.
 */
const API = "http://127.0.0.1:8000";

// Ruta de ejemplo corta (Talavera → Arenas de San Pedro aproximada), con puntos cada pocos km.
const track = {
  type: "LineString",
  coordinates: Array.from({ length: 40 }, (_, i) => [-4.83 + i * 0.012, 39.96 + i * 0.006]),
};

const station = (id: string, name: string, price: number, km: number, i: number) => ({
  id,
  name,
  price,
  km_on_route: km,
  lat: 39.96 + i * 0.006 + 0.0004,
  lon: -4.83 + i * 0.012,
  open_24h: true,
  schedule: "L-D: 24H",
  town: "TALAVERA DE LA REINA",
  address: "AVENIDA DE PORTUGAL, 1",
  savings_vs_max: Math.round((1.9 - price) * 1000) / 1000,
});

const search = {
  prices: { status: "fresh", age_minutes: 7, station_count: 11800, fetched_at: "2026-10-16T08:00:00Z" },
  fuel: { id: "gasolina_95", label: "Gasolina 95" },
  route_km: 52,
  corridor_station_count: 6,
  max_price_in_corridor: 1.9,
  stations: [
    station("1", "BALLENOIL", 1.629, 6, 4),
    station("2", "REPSOL", 1.689, 25, 18),
    station("3", "CEPSA", 1.709, 44, 33),
  ],
  other_stations: [station("4", "SHELL", 1.799, 15, 11), station("5", "GALP", 1.849, 35, 26)],
  autonomy: null,
};

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

export async function useFakeApi(page: Page) {
  await page.route("https://tiles.openfreemap.org/**", (route) => route.abort());
  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url());
    switch (url.pathname) {
      case "/health":
        return json(route, { status: "ok", version: "e2e", prices: search.prices });
      case "/fuels":
        return json(route, [
          { id: "gasolina_95", label: "Gasolina 95" },
          { id: "diesel", label: "Diésel (Gasoil A)" },
        ]);
      case "/route/demo":
      case "/route/text":
        return json(route, { track, point_count: track.coordinates.length });
      case "/search":
        return json(route, search);
      case "/detours": {
        const body = route.request().postDataJSON() as {
          stations: { id: string; lat: number; lon: number }[];
        };
        return json(route, {
          detours: body.stations.map((s) => ({ ...s, detour_km: 0.6, detour_min: 1.2 })),
          complete: true,
        });
      }
      case "/export/gmaps-url":
        return json(route, { url: "https://www.google.com/maps/dir/?api=1&e2e=1", truncated: 0 });
      case "/places/suggest":
        return json(route, { places: [] });
      default:
        return json(route, { detail: "No simulado en la e2e" }, 404);
    }
  });
}
