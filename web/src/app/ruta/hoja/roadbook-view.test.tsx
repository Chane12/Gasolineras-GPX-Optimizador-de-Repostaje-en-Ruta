import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NuqsTestingAdapter, type UrlUpdateEvent } from "nuqs/adapters/testing";
import { describe, expect, it } from "vitest";

import { fakeApi, jsonResponse, renderWithQuery } from "@/test-utils";

import { RoadbookView } from "./roadbook-view";

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
  lon: -3 + Number(id) / 100,
  open_24h: true,
  schedule: "L-D: 24H",
  town: "TARANCÓN",
});
const searchResponse = {
  prices: { status: "fresh", age_minutes: 5, station_count: 11000, fetched_at: "2026-10-16T08:12:00Z" },
  fuel: { id: "gasolina_95", label: "Gasolina 95" },
  route_km: 352,
  corridor_station_count: 40,
  max_price_in_corridor: 1.85,
  stations: [station("1", "BALLENOIL", 1.629, 82), station("2", "REPSOL", 1.668, 322)],
  other_stations: [],
};

function api() {
  const gmapsBodies: unknown[] = [];
  const client = fakeApi(async (request) => {
    const path = new URL(request.url).pathname;
    if (path.startsWith("/route/")) return jsonResponse({ track, point_count: 2 });
    if (path === "/search") return jsonResponse(searchResponse);
    if (path === "/detours") {
      const body = (await request.json()) as { stations: { id: string; lat: number; lon: number }[] };
      return jsonResponse({
        detours: body.stations.map((s) => ({ ...s, detour_km: 0.8, detour_min: 1 })),
        complete: true,
      });
    }
    if (path === "/export/gmaps-url") {
      gmapsBodies.push(await request.json());
      return jsonResponse({ url: "https://www.google.com/maps/dir/?api=1&x", truncated: 0 });
    }
    return jsonResponse({ status: "ok", prices: { status: "fresh" } });
  });
  return { client, gmapsBodies };
}

function renderAt(search: string, client = api().client, onUrlUpdate?: (e: UrlUpdateEvent) => void) {
  return renderWithQuery(
    <NuqsTestingAdapter searchParams={search} onUrlUpdate={onUrlUpdate} hasMemory>
      <RoadbookView client={client} />
    </NuqsTestingAdapter>,
  );
}

const PLAN = "?origen=Madrid&destino=Valencia&paradas=2~1";

describe("RoadbookView", () => {
  it("lists start, stops in route order and arrival with total and partial km", async () => {
    renderAt(PLAN);

    expect(screen.getByRole("heading", { level: 1, name: "Madrid → Valencia" })).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: /Roadbook/ });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringMatching(/^0—Salida · Madrid/),
      expect.stringMatching(/^8282Repostar · Ballenoil, Tarancón/),
      expect.stringMatching(/^322240Repostar · Repsol, Tarancón/),
      expect.stringMatching(/^35230Llegada · Valencia/),
    ]);
    expect(rows[1]).toHaveTextContent("1,629 €/L");
    expect(await within(rows[1] as HTMLElement).findByText(/desvío 0,8 km/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 }).nextSibling).toHaveTextContent("352 km · 2 paradas");
  });

  it("prepares the Google Maps link with the stops in order", async () => {
    const { client, gmapsBodies } = api();
    renderAt(PLAN, client);

    const link = await screen.findByRole("link", { name: /Navegar con Google Maps/ });
    expect(link).toHaveAttribute("href", "https://www.google.com/maps/dir/?api=1&x");
    expect(gmapsBodies).toHaveLength(1);
    expect(gmapsBodies[0]).toMatchObject({
      origin: [-3.7, 40.4],
      destination: [-0.37, 39.47],
      stops: [{ id: "1" }, { id: "2" }],
    });
  });

  it("removes a stop from the plan (and from the URL)", async () => {
    const user = userEvent.setup();
    const updates: string[] = [];
    renderAt(PLAN, api().client, (e) => updates.push(e.queryString));

    await user.click(await screen.findByRole("button", { name: "Quitar la parada de Repsol" }));

    expect(updates.at(-1)).toContain("paradas=1");
    expect(updates.at(-1)).not.toContain("2~");
    expect(screen.queryByText(/Repostar · Repsol/)).not.toBeInTheDocument();
  });

  it("warns about stretches longer than the autonomy", async () => {
    renderAt(`${PLAN}&autonomia=200`);

    expect(
      await screen.findByText(/240 km desde el repostaje anterior: más que tu autonomía \(200 km\)/),
    ).toBeInTheDocument();
  });

  it("invites to choose stops when there are none", async () => {
    renderAt("?origen=Madrid&destino=Valencia");

    expect(await screen.findByText("Aún no has elegido paradas para esta ruta.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Elegir paradas" })).toHaveAttribute(
      "href",
      "/ruta?origen=Madrid&destino=Valencia",
    );
  });
});
