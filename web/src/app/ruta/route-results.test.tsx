import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RouteMapProps } from "@/components/route-map/route-map";
import { fakeApi, jsonResponse, renderWithQuery } from "@/test-utils";

import { RouteResults } from "./route-results";

// MapLibre necesita WebGL, que jsdom no tiene: el mapa se sustituye por un doble que enseña lo que recibe.
const mapProps = vi.hoisted(() => ({ last: null as RouteMapProps | null }));
vi.mock("./route-map-lazy", () => ({
  RouteMapLazy: (props: RouteMapProps) => {
    mapProps.last = props;
    return <div data-testid="map" />;
  },
}));

const loadGpx = vi.hoisted(() => vi.fn());
vi.mock("@/lib/gpx-store", () => ({ loadGpx }));

const track = {
  type: "LineString",
  coordinates: [
    [-3.7, 40.4],
    [-0.37, 39.47],
  ],
};
const station = (id: string, name: string, price: number, km: number) => ({
  id,
  name,
  price,
  km_on_route: km,
  lat: 40,
  lon: -3,
  open_24h: true,
  town: "Tarancón",
});
const searchResponse = {
  prices: { status: "fresh", age_minutes: 12, station_count: 11000 },
  fuel: { id: "gasolina_95", label: "Gasolina 95", unit: "€/L" },
  route_km: 352.4,
  corridor_station_count: 40,
  max_price_in_corridor: 1.85,
  stations: [station("1", "Repsol", 1.659, 42), station("2", "Ballenoil", 1.639, 118)],
};

function api(overrides: Partial<Record<string, () => Response>> = {}) {
  const requests: string[] = [];
  const client = fakeApi((request) => {
    const path = new URL(request.url).pathname;
    requests.push(`${request.method} ${path}`);
    const override = overrides[path];
    if (override) return override();
    if (path === "/health") return jsonResponse({ status: "ok", prices: { status: "fresh" } });
    if (path.startsWith("/route/")) return jsonResponse({ track, point_count: 2 });
    if (path === "/search") return jsonResponse(searchResponse);
    return new Response(null, { status: 404 });
  });
  return { client, requests };
}

function renderAt(search: string, client: ReturnType<typeof api>["client"]) {
  return renderWithQuery(
    <NuqsTestingAdapter searchParams={search}>
      <RouteResults client={client} />
    </NuqsTestingAdapter>,
  );
}

describe("RouteResults", () => {
  beforeEach(() => {
    mapProps.last = null;
    loadGpx.mockReset();
  });

  it("shows the route, the price freshness and the stations on the map and in the list", async () => {
    const { client, requests } = api();
    renderAt("?origen=Madrid&destino=Valencia", client);

    expect(screen.getByRole("heading", { level: 1, name: "Madrid → Valencia" })).toBeInTheDocument();
    expect(await screen.findByText("352 km · Gasolina 95")).toBeInTheDocument();
    expect(screen.getByText("Precios MITECO · hace 12 min")).toBeInTheDocument();
    expect(requests).toContain("POST /route/text");

    const list = screen.getByRole("list");
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(within(list).getByText("MÁS BARATA")).toBeInTheDocument();
    expect(screen.getByTestId("map")).toBeInTheDocument();
    expect(mapProps.last?.track).toEqual(track.coordinates);
    expect(mapProps.last?.stations).toHaveLength(2);
  });

  it("adds a stop from the list and centres the map on a station", async () => {
    const user = userEvent.setup();
    renderAt("?origen=Madrid&destino=Valencia", api().client);

    await user.click(await screen.findByRole("button", { name: "Añadir Ballenoil a tus paradas" }));
    expect(screen.getByRole("button", { name: "Quitar Ballenoil de tus paradas" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect([...(mapProps.last?.stopKeys ?? [])]).toEqual(["2"]);

    await user.click(screen.getByRole("button", { name: "Repsol, ver en el mapa" }));
    expect(mapProps.last?.focusedKey).toBe("1");
  });

  it("sends the places picked from the suggestions so the API does not look them up again", async () => {
    const bodies: unknown[] = [];
    const client = fakeApi(async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/route/text") {
        bodies.push(await request.json());
        return jsonResponse({ track, point_count: 2 });
      }
      if (path === "/search") return jsonResponse(searchResponse);
      return jsonResponse({ status: "ok", prices: { status: "fresh" } });
    });
    renderAt("?origen=Madrid&destino=Val%C3%A8ncia&origenGeo=40.41678,-3.70379", client);

    expect(await screen.findByText("352 km · Gasolina 95")).toBeInTheDocument();
    expect(bodies).toEqual([
      {
        origin: "Madrid",
        destination: "València",
        origin_point: { lat: 40.41678, lon: -3.70379 },
        destination_point: null,
      },
    ]);
  });

  it("loads the sample route for the demo", async () => {
    const { client, requests } = api();
    renderAt("?demo=true", client);

    expect(await screen.findByText("352 km · Gasolina 95")).toBeInTheDocument();
    expect(requests).toContain("GET /route/demo");
  });

  it("explains the API error and lets the user retry", async () => {
    const { client } = api({
      "/route/text": () => jsonResponse({ detail: "No encontramos la ubicación «Mdrid»." }, { status: 400 }),
    });
    renderAt("?origen=Mdrid&destino=Valencia", client);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No encontramos la ubicación «Mdrid».");
    expect(within(alert).getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("asks to upload the GPX again when it is no longer on the device", async () => {
    loadGpx.mockResolvedValue(undefined);
    renderAt("?gpx=true", api().client);

    expect(await screen.findByRole("alert")).toHaveTextContent("No encontramos tu GPX en este dispositivo");
  });

  it("sends the stored GPX file to the API", async () => {
    loadGpx.mockResolvedValue({ name: "gredos.gpx", bytes: new ArrayBuffer(8), savedAt: "" });
    const { client, requests } = api();
    renderAt("?gpx=true", client);

    expect(await screen.findByText("352 km · Gasolina 95")).toBeInTheDocument();
    expect(requests).toContain("POST /route/gpx");
  });

  it("sends people back home when the URL has no route", () => {
    renderAt("?origen=Madrid", api().client);

    expect(screen.getByText(/Falta la ruta/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al inicio" })).toHaveAttribute("href", "/");
  });
});
