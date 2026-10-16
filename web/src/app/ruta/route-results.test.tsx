import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NuqsTestingAdapter, type UrlUpdateEvent } from "nuqs/adapters/testing";
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
const station = (id: string, name: string, price: number, km: number, schedule = "L-D: 24H") => ({
  id,
  name,
  price,
  km_on_route: km,
  lat: 40,
  lon: -3 + Number(id) / 100,
  open_24h: schedule.includes("24H"),
  schedule,
  town: "TARANCÓN",
});
const searchResponse = {
  prices: { status: "fresh", age_minutes: 12, station_count: 11000 },
  fuel: { id: "gasolina_95", label: "Gasolina 95" },
  route_km: 352.4,
  corridor_station_count: 40,
  max_price_in_corridor: 1.85,
  stations: [
    station("1", "REPSOL", 1.659, 42),
    station("2", "E.S BALLENOIL", 1.639, 118, "L-D: 06:00-22:00"),
  ],
  other_stations: [station("3", "CEPSA", 1.712, 205), station("4", "GALP", 1.699, 300)],
};

interface Requests {
  paths: string[];
  searches: Record<string, unknown>[];
}

function api(overrides: Partial<Record<string, () => Response>> = {}) {
  const requests: Requests = { paths: [], searches: [] };
  const client = fakeApi(async (request) => {
    const path = new URL(request.url).pathname;
    requests.paths.push(`${request.method} ${path}`);
    const override = overrides[path];
    if (override) return override();
    if (path === "/health") return jsonResponse({ status: "ok", prices: { status: "fresh" } });
    if (path === "/fuels") return jsonResponse([{ id: "gasolina_95", label: "Gasolina 95" }]);
    if (path.startsWith("/route/")) return jsonResponse({ track, point_count: 2 });
    if (path === "/search") {
      requests.searches.push((await request.json()) as Record<string, unknown>);
      return jsonResponse(searchResponse);
    }
    if (path === "/detours") {
      const body = (await request.json()) as { stations: { id: string; lat: number; lon: number }[] };
      // Desvío simulado: 3,1 km la gasolinera 1 y 0,4 km las demás.
      const detours = body.stations.map((st) => ({
        ...st,
        detour_km: st.id === "1" ? 3.1 : 0.4,
        detour_min: st.id === "1" ? 4 : 1,
      }));
      return jsonResponse({ detours, complete: true });
    }
    return new Response(null, { status: 404 });
  });
  return { client, requests };
}

function renderAt(
  search: string,
  client: ReturnType<typeof api>["client"],
  onUrlUpdate?: (e: UrlUpdateEvent) => void,
) {
  return renderWithQuery(
    <NuqsTestingAdapter searchParams={search} onUrlUpdate={onUrlUpdate} hasMemory>
      <RouteResults client={client} />
    </NuqsTestingAdapter>,
  );
}

const recommendedList = () => screen.getByRole("list", { name: "Gasolineras recomendadas" });
const loaded = () => screen.findAllByText("352 km · Gasolina 95");

describe("RouteResults", () => {
  beforeEach(() => {
    mapProps.last = null;
    loadGpx.mockReset();
  });

  it("shows the route, the price freshness, the summary and the recommended stations", async () => {
    const { client, requests } = api();
    renderAt("?origen=Madrid&destino=Valencia", client);

    expect(screen.getByRole("heading", { level: 1, name: "Madrid → Valencia" })).toBeInTheDocument();
    await loaded();
    expect(screen.getAllByText("Precios MITECO · hace 12 min").length).toBeGreaterThan(0);
    expect(requests.paths).toContain("POST /route/text");

    const rows = within(recommendedList()).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Repsol");
    expect(rows[1]).toHaveTextContent("E.S Ballenoil");
    expect(rows[1]).toHaveTextContent("Tarancón · 6–22 h");
    expect(within(rows[1] as HTMLElement).getByText("MÁS BARATA")).toBeInTheDocument();
    expect(screen.getByText("Recomendadas").nextSibling).toHaveTextContent("2 de 4");
    expect(mapProps.last?.stations).toHaveLength(2);
  });

  it("asks for the recommended stations plus the rest of the corridor", async () => {
    const { client, requests } = api();
    renderAt("?origen=Madrid&destino=Valencia", client);

    await loaded();
    expect(requests.searches[0]).toMatchObject({ top_n: 4, include_others: true, fuel: "gasolina_95" });
    expect(requests.searches[0]?.segment_km).toBeGreaterThanOrEqual(10);
  });

  it("shows every station of the route on demand and sorts by price", async () => {
    const user = userEvent.setup();
    renderAt("?origen=Madrid&destino=Valencia", api().client);

    await user.click(await screen.findByRole("button", { name: "Ver las 4 gasolineras de la ruta" }));
    const all = screen.getByRole("list", { name: "Todas las gasolineras" });
    expect(
      within(all)
        .getAllByRole("listitem")
        .map((r) => r.textContent?.match(/^km (\d+)/)?.[1]),
    ).toEqual(["42", "118", "205", "300"]);

    await user.click(screen.getByRole("button", { name: "Por precio" }));
    expect(within(all).getAllByRole("listitem")[0]).toHaveTextContent("E.S Ballenoil");
    expect(within(all).getAllByRole("listitem")[3]).toHaveTextContent("Cepsa");

    await user.click(screen.getByRole("button", { name: "Ver solo las recomendadas" }));
    expect(within(recommendedList()).getAllByRole("listitem")).toHaveLength(2);
  });

  it("applies filters at once: they go to the URL", async () => {
    const user = userEvent.setup();
    const updates: string[] = [];
    renderAt("?origen=Madrid&destino=Valencia", api().client, (e) => updates.push(e.queryString));

    await user.click(await screen.findByRole("button", { name: "Solo abiertas 24 h" }));
    expect(updates.at(-1)).toContain("abierta24h=true");
    await user.selectOptions(screen.getByLabelText("Distancia máxima a la ruta"), "10");
    expect(updates.at(-1)).toContain("radio=10");
  });

  it("sends the filters from the URL to the search", async () => {
    const { client, requests } = api();
    renderAt("?origen=Madrid&destino=Valencia&abierta24h=true&vaciada=true&radio=10&autonomia=250", client);

    await loaded();
    expect(requests.searches[0]).toMatchObject({
      only_24h: true,
      all_on_route: true,
      max_detour_km: 10,
      autonomy_km: 250,
    });
    expect(screen.getByRole("button", { name: "Solo abiertas 24 h" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Autonomía 250 km" })).toBeInTheDocument();
  });

  it("adds stops to «Tu ruta» and centres the map on a station", async () => {
    const user = userEvent.setup();
    renderAt("?origen=Madrid&destino=Valencia", api().client);

    const tuRuta = screen.getByRole("region", { name: "Tu ruta" });
    expect(tuRuta).toHaveTextContent("Añade tus paradas con +");
    await user.click(await screen.findByRole("button", { name: "Añadir E.S Ballenoil a tus paradas" }));
    expect(screen.getByRole("button", { name: "Quitar E.S Ballenoil de tus paradas" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(tuRuta).toHaveTextContent("1 parada · km 118");
    expect([...(mapProps.last?.stopKeys ?? [])]).toEqual(["2"]);

    await user.click(screen.getByRole("button", { name: "Repsol, ver la ficha" }));
    expect(mapProps.last?.focusedKey).toBe("1");
  });

  it("shows the rest of the corridor as dots, and gives a plate to the one picked from the list", async () => {
    const user = userEvent.setup();
    renderAt("?origen=Madrid&destino=Valencia", api().client);

    await loaded();
    expect(mapProps.last?.otherStations?.map((s) => s.id)).toEqual(["3", "4"]);

    await user.click(screen.getByRole("button", { name: "Ver las 4 gasolineras de la ruta" }));
    await user.click(screen.getByRole("button", { name: "Cepsa, ver la ficha" }));
    expect(mapProps.last?.focusedKey).toBe("3");
    expect(mapProps.last?.stations.map((s) => s.id)).toEqual(["1", "2", "3"]);
    expect(mapProps.last?.otherStations?.map((s) => s.id)).toEqual(["4"]);
  });

  it("shows the real detour of each recommended station and sorts by it", async () => {
    const user = userEvent.setup();
    renderAt("?origen=Madrid&destino=Valencia", api().client);

    await screen.findByText(/desvío 3,1 km/);
    await user.click(screen.getByRole("button", { name: "Por desvío" }));
    const rows = within(recommendedList()).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("E.S Ballenoil");
    expect(rows[0]).toHaveTextContent("desvío 0,4 km");
    expect(rows[1]).toHaveTextContent("Repsol");
  });

  it("opens the station sheet from the list, moves between stations and goes back", async () => {
    const user = userEvent.setup();
    const updates: string[] = [];
    renderAt("?origen=Madrid&destino=Valencia", api().client, (e) => updates.push(e.queryString));

    await user.click(await screen.findByRole("button", { name: "Repsol, ver la ficha" }));
    const sheet = screen.getByRole("article", { name: "Repsol" });
    expect(updates.at(-1)).toContain("gasolinera=1");
    expect(sheet).toHaveTextContent("1,659");
    expect(sheet).toHaveTextContent("Abierta 24 h, todos los días");
    expect(await within(sheet).findByText("3,1 km ida y vuelta · +4 min")).toBeInTheDocument();
    expect(sheet).toHaveTextContent("en 76 km (E.S Ballenoil)");
    expect(within(sheet).getByRole("link", { name: /Cómo llegar/ })).toHaveAttribute(
      "href",
      expect.stringContaining("destination=40,-2.99"),
    );
    expect(mapProps.last?.focusedKey).toBe("1");

    await user.click(within(sheet).getByRole("button", { name: "Añadir parada" }));
    expect(screen.getByRole("region", { name: "Tu ruta" })).toHaveTextContent("1 parada · km 42");

    await user.click(within(sheet).getByRole("button", { name: /Siguiente: E.S Ballenoil, km 118/ }));
    expect(screen.getByRole("article", { name: /E.S Ballenoil/ })).toHaveTextContent("MÁS BARATA");

    await user.click(screen.getByRole("button", { name: "Volver a la lista" }));
    expect(recommendedList()).toBeInTheDocument();
  });

  it("opens the sheet of a station shared by link", async () => {
    renderAt("?origen=Madrid&destino=Valencia&gasolinera=2", api().client);

    expect(await screen.findByRole("article", { name: /E.S Ballenoil/ })).toHaveTextContent("6–22 h");
  });

  it("highlights the plate of the row under the pointer", async () => {
    const user = userEvent.setup();
    renderAt("?origen=Madrid&destino=Valencia", api().client);

    await loaded();
    const rows = within(recommendedList()).getAllByRole("listitem");
    await user.hover(rows[1] as HTMLElement);
    expect(mapProps.last?.highlightedKey).toBe("2");
    await user.unhover(rows[1] as HTMLElement);
    expect(mapProps.last?.highlightedKey).toBeNull();
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
      if (path === "/fuels") return jsonResponse([{ id: "gasolina_95", label: "Gasolina 95" }]);
      return jsonResponse({ status: "ok", prices: { status: "fresh" } });
    });
    renderAt("?origen=Madrid&destino=Val%C3%A8ncia&origenGeo=40.41678,-3.70379", client);

    await loaded();
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

    await loaded();
    expect(requests.paths).toContain("GET /route/demo");
  });

  it("explains the API error and lets the user retry", async () => {
    const { client } = api({
      "/route/text": () => jsonResponse({ detail: "No encontramos la ubicación «Mdrid»." }, { status: 400 }),
    });
    renderAt("?origen=Mdrid&destino=Valencia", client);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No encontramos la ubicación «Mdrid».");
    expect(within(alert).getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
    expect(screen.getByText("No se pudo calcular la ruta")).toBeInTheDocument();
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

    await loaded();
    expect(requests.paths).toContain("POST /route/gpx");
  });

  it("sends people back home when the URL has no route", () => {
    renderAt("?origen=Madrid", api().client);

    expect(screen.getByText(/Falta la ruta/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al inicio" })).toHaveAttribute("href", "/");
  });
});
