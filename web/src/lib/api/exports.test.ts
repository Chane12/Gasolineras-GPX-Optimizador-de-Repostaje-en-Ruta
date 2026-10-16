import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Station } from "@/lib/map/geo";
import { fakeApi } from "@/test-utils";

import { downloadGpx } from "./exports";

const track = { coordinates: Array.from({ length: 21 }, (_, i) => [-3.1 + i * 0.01, 40.0]) };
const stop = {
  id: "1",
  name: "REPSOL",
  lat: 40.002,
  lon: -3.0,
  price: 1.559,
  km_on_route: 8.5,
  open_24h: true,
  schedule: null,
} as unknown as Station;

function capturingApi() {
  const bodies: Record<string, unknown>[] = [];
  const client = fakeApi(async (request) => {
    bodies.push((await request.json()) as Record<string, unknown>);
    return new Response("<gpx/>", { headers: { "content-type": "application/gpx+xml" } });
  });
  return { client, bodies };
}

describe("downloadGpx", () => {
  beforeEach(() => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends the track already routed through the stops, so the server does not need OSRM", async () => {
    const { client, bodies } = capturingApi();
    const osrm = (async (input: RequestInfo | URL) => {
      const path = String(input).split("/driving/")[1]?.split("?")[0] ?? "";
      const coordinates = path.split(";").map((p) => p.split(",").map(Number));
      return new Response(
        JSON.stringify({ code: "Ok", routes: [{ distance: 1, duration: 1, geometry: { coordinates } }] }),
      );
    }) as typeof fetch;

    await downloadGpx(track, [stop], "Hoja de ruta", client, osrm);

    const body = bodies[0] as {
      splice_detours: boolean;
      track: { coordinates: number[][] };
      stops: unknown[];
    };
    expect(body.splice_detours).toBe(false);
    expect(body.track.coordinates).toContainEqual([-3.0, 40.002]);
    expect(body.stops).toHaveLength(1);
  });

  it("lets the server try when the browser cannot reach OSRM either", async () => {
    const { client, bodies } = capturingApi();
    const down = (async () => new Response("no", { status: 503 })) as typeof fetch;

    await downloadGpx(track, [stop], "Hoja de ruta", client, down);

    const body = bodies[0] as { splice_detours: boolean; track: { coordinates: number[][] } };
    expect(body.splice_detours).toBe(true);
    expect(body.track.coordinates).toEqual(track.coordinates);
  });
});
