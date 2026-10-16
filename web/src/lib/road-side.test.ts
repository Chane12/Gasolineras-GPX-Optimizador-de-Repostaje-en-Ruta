import { describe, expect, it } from "vitest";

import { roadSides } from "./road-side";

// Una carretera recta de oeste a este, a 40° N.
const track = [
  [-3.0, 40.0],
  [-2.9, 40.0],
  [-2.8, 40.0],
];
const north = 40 + 50 / 110_540; // 50 m al norte
const south = 40 - 50 / 110_540;

describe("roadSides", () => {
  it("going east, the north side is on the left and the south side on the right", () => {
    const sides = roadSides(track, [
      { key: "norte", lat: north, lon: -2.95 },
      { key: "sur", lat: south, lon: -2.85 },
    ]);
    expect(Object.fromEntries(sides)).toEqual({ norte: "left", sur: "right" });
  });

  it("swaps when travelling the other way", () => {
    const sides = roadSides([...track].reverse(), [{ key: "norte", lat: north, lon: -2.95 }]);
    expect(sides.get("norte")).toBe("right");
  });

  it("says nothing for stations away from the road", () => {
    const far = 40 + 300 / 110_540;
    expect(roadSides(track, [{ key: "lejos", lat: far, lon: -2.9 }]).size).toBe(0);
  });
});
