import { describe, expect, it } from "vitest";

import {
  BrowserRoutingError,
  detourAnchors,
  detourInBrowser,
  routeInBrowser,
  spliceStopsInBrowser,
} from "./browser-routing";

function osrm(handler: (points: number[][]) => { distance: number; duration: number } | null) {
  const urls: string[] = [];
  const fetcher = (async (input: RequestInfo | URL) => {
    const url = String(input);
    urls.push(url);
    const path = url.split("/driving/")[1]?.split("?")[0] ?? "";
    const points = path.split(";").map((p) => p.split(",").map(Number));
    const result = handler(points);
    if (!result) return new Response(JSON.stringify({ code: "NoRoute" }), { status: 400 });
    return new Response(
      JSON.stringify({
        code: "Ok",
        routes: [{ ...result, geometry: { coordinates: points } }],
      }),
    );
  }) as typeof fetch;
  return { fetcher, urls };
}

describe("routeInBrowser", () => {
  it("asks OSRM for the road route with its full geometry", async () => {
    const { fetcher, urls } = osrm(() => ({ distance: 352_000, duration: 14_400 }));

    const route = await routeInBrowser(
      [
        [-3.7, 40.4],
        [-0.37, 39.47],
      ],
      fetcher,
    );

    expect(route).toMatchObject({ distanceKm: 352, durationMin: 240 });
    expect(route.coordinates).toHaveLength(2);
    expect(urls[0]).toContain("routing.openstreetmap.de");
    expect(urls[0]).toContain("overview=full&geometries=geojson");
  });

  it("tries the second server when the first one fails, and gives up clearly", async () => {
    let calls = 0;
    const flaky = (async () => {
      calls++;
      if (calls === 1) return new Response("busy", { status: 429 });
      return new Response(
        JSON.stringify({
          code: "Ok",
          routes: [
            {
              distance: 1000,
              duration: 60,
              geometry: {
                coordinates: [
                  [0, 0],
                  [1, 1],
                ],
              },
            },
          ],
        }),
      );
    }) as typeof fetch;
    await expect(
      routeInBrowser(
        [
          [0, 0],
          [1, 1],
        ],
        flaky,
      ),
    ).resolves.toMatchObject({ distanceKm: 1 });

    const down = (async () => new Response("no", { status: 503 })) as typeof fetch;
    await expect(
      routeInBrowser(
        [
          [0, 0],
          [1, 1],
        ],
        down,
      ),
    ).rejects.toBeInstanceOf(BrowserRoutingError);
  });
});

describe("detourInBrowser", () => {
  // Carretera recta de oeste a este, de unos 17 km.
  const track = [
    [-3.1, 40.0],
    [-2.9, 40.0],
  ];

  it("places the anchors 2 km before and after the station, in the direction of travel", () => {
    const { before, after } = detourAnchors(track, { lat: 40.0005, lon: -3.0 });
    expect(before[0]).toBeLessThan(-3.0);
    expect(after[0]).toBeGreaterThan(-3.0);
    // ~2 km a 40° N son ~0,0235° de longitud.
    expect(-3.0 - before[0]).toBeCloseTo(0.0235, 2);
  });

  it("is the extra distance of stopping on the way", async () => {
    const { fetcher } = osrm((points) =>
      points.length === 3 ? { distance: 4600, duration: 300 } : { distance: 4000, duration: 240 },
    );

    const detour = await detourInBrowser(track, { lat: 40.0005, lon: -3.0 }, fetcher);
    expect(detour.km).toBeCloseTo(0.6, 6);
    expect(detour.minutes).toBeCloseTo(1, 6);
  });
});

describe("spliceStopsInBrowser", () => {
  // Carretera recta de oeste a este con un punto cada ~850 m (0,01° a 40° N).
  const track = Array.from({ length: 21 }, (_, i) => [-3.1 + i * 0.01, 40.0]);
  const roadThrough = (points: number[][]) => {
    // Camino "por carretera": los puntos pedidos con un punto intermedio entre cada par.
    const out: number[][] = [];
    points.forEach((p, i) => {
      const prev = points[i - 1];
      if (prev) out.push([((prev[0] ?? 0) + (p[0] ?? 0)) / 2, ((prev[1] ?? 0) + (p[1] ?? 0)) / 2 + 0.001]);
      out.push(p);
    });
    return out;
  };
  const fakeOsrm = () => {
    const requests: number[][][] = [];
    const fetcher = (async (input: RequestInfo | URL) => {
      const path = String(input).split("/driving/")[1]?.split("?")[0] ?? "";
      const points = path.split(";").map((p) => p.split(",").map(Number));
      requests.push(points);
      return new Response(
        JSON.stringify({
          code: "Ok",
          routes: [{ distance: 1, duration: 1, geometry: { coordinates: roadThrough(points) } }],
        }),
      );
    }) as typeof fetch;
    return { fetcher, requests };
  };

  it("replaces the stretch around each stop with the road into the station", async () => {
    const { fetcher, requests } = fakeOsrm();
    const station = { lat: 40.002, lon: -3.0 };

    const spliced = await spliceStopsInBrowser(track, [station], fetcher);

    expect(requests).toHaveLength(1);
    const [start, via, end] = requests[0] ?? [];
    expect(via).toEqual([-3.0, 40.002]);
    // Sale de la ruta antes de la gasolinera y vuelve después, en puntos del propio track.
    expect(start?.[0]).toBeLessThan(-3.0);
    expect(end?.[0]).toBeGreaterThan(-3.0);
    expect(track).toContainEqual(start);
    expect(track).toContainEqual(end);
    expect(spliced).not.toBeNull();
    expect(spliced).toContainEqual([-3.0, 40.002]);
    expect(spliced?.[0]).toEqual(track[0]);
    expect(spliced?.at(-1)).toEqual(track.at(-1));
    // Sin puntos repetidos en las uniones y siempre hacia delante.
    const lons = (spliced ?? []).map((p) => p[0] ?? 0);
    expect(lons.every((lon, i) => i === 0 || lon > (lons[i - 1] ?? 0))).toBe(true);
  });

  it("asks once for stops close to each other, and once per group", async () => {
    const { fetcher, requests } = fakeOsrm();
    await spliceStopsInBrowser(
      track,
      [
        { lat: 40.002, lon: -2.95 },
        { lat: 40.002, lon: -3.06 },
        { lat: 40.002, lon: -3.05 },
      ],
      fetcher,
    );

    expect(requests).toHaveLength(2);
    // En el sentido de la marcha: primero las dos cercanas, juntas.
    expect(requests[0]?.slice(1, 3)).toEqual([
      [-3.06, 40.002],
      [-3.05, 40.002],
    ]);
    expect(requests[1]?.[1]).toEqual([-2.95, 40.002]);
  });

  it("gives up (null) when OSRM does not answer, and leaves a route without stops as it is", async () => {
    const down = (async () => new Response("no", { status: 503 })) as typeof fetch;
    await expect(spliceStopsInBrowser(track, [{ lat: 40.002, lon: -3.0 }], down)).resolves.toBeNull();
    await expect(spliceStopsInBrowser(track, [], down)).resolves.toEqual(track);
  });
});
