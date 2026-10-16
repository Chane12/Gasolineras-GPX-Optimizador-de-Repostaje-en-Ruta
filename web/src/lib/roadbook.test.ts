import { describe, expect, it } from "vitest";

import type { Station } from "@/lib/map/geo";

import { buildRoadbook, legLevel, longestLegKm } from "./roadbook";

const station = (id: string, km: number) =>
  ({ id, name: id, km_on_route: km, lat: 40, lon: -3, price: 1.6, open_24h: true }) as Station;

describe("buildRoadbook", () => {
  it("orders the stops by km and computes the partial distances", () => {
    const rows = buildRoadbook([station("B", 322), station("A", 82)], 352, {
      start: "Madrid",
      end: "Valencia",
    });

    expect(rows.map((r) => [r.kind, r.totalKm, r.partialKm])).toEqual([
      ["start", 0, null],
      ["stop", 82, 82],
      ["stop", 322, 240],
      ["end", 352, 30],
    ]);
    expect(longestLegKm(rows)).toBe(240);
  });

  it("works without stops", () => {
    expect(buildRoadbook([], 120, { start: "Salida", end: "Llegada" }).map((r) => r.partialKm)).toEqual([
      null,
      120,
    ]);
  });
});

describe("legLevel", () => {
  it("warns above 80 % of the autonomy and flags what exceeds it", () => {
    expect(legLevel(150, 250)).toBe("ok");
    expect(legLevel(210, 250)).toBe("warning");
    expect(legLevel(260, 250)).toBe("critical");
    expect(legLevel(900, 0)).toBe("ok");
  });
});
