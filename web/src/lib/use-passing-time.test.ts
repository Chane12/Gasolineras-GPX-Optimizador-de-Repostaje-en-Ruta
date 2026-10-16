import { describe, expect, it } from "vitest";

import { etaAt, routeSpeedKmh, toLocalInput } from "./use-passing-time";

describe("etaAt", () => {
  it("estimates the time of passing from the departure and the average speed", () => {
    const eta = etaAt({ departure: "2026-10-19T07:30", speedKmh: 80 }, 200);
    expect(toLocalInput(eta)).toBe("2026-10-19T10:00");
  });
});

describe("routeSpeedKmh", () => {
  it("is the average speed of the calculated route, rounded to 5 km/h", () => {
    expect(routeSpeedKmh(352, 220)).toBe(95);
  });

  it("is unknown without a duration (GPX routes) or with nonsense", () => {
    expect(routeSpeedKmh(352, null)).toBeNull();
    expect(routeSpeedKmh(undefined, 220)).toBeNull();
    expect(routeSpeedKmh(352, 1)).toBeNull();
  });
});
