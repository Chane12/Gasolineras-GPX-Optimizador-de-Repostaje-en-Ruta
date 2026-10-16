import { describe, expect, it } from "vitest";

import { plateTones, stationKey, trackBounds } from "./geo";

describe("trackBounds", () => {
  it("returns west-south and east-north corners of the track", () => {
    expect(
      trackBounds([
        [-4.6, 40.6],
        [-4.1, 40.9],
        [-4.4, 40.5],
      ]),
    ).toEqual([
      [-4.6, 40.5],
      [-4.1, 40.9],
    ]);
  });

  it("is null for an empty track", () => {
    expect(trackBounds([])).toBeNull();
  });
});

describe("stationKey", () => {
  it("uses the MITECO id when there is one, and the position otherwise", () => {
    expect(stationKey({ id: "1234", lat: 40, lon: -4 })).toBe("1234");
    expect(stationKey({ id: null, lat: 40.123456, lon: -4.5 })).toBe("40.12346,-4.50000");
  });
});

describe("plateTones", () => {
  it("marks the cheapest (ties included) as best and the top third of the range as expensive", () => {
    const prices = [1.659, 1.639, 1.712, 1.639, 1.668];
    expect(plateTones(prices.map((price) => ({ price })))).toEqual([
      "suggested",
      "best",
      "expensive",
      "best",
      "suggested",
    ]);
  });

  it("does not call any station expensive when prices barely differ", () => {
    expect(plateTones([{ price: 1.6 }, { price: 1.605 }])).toEqual(["best", "suggested"]);
  });

  it("handles no stations", () => {
    expect(plateTones([])).toEqual([]);
  });
});
