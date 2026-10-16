import { describe, expect, it } from "vitest";

import { etaAt, toLocalInput } from "./use-passing-time";

describe("etaAt", () => {
  it("estimates the time of passing from the departure and the average speed", () => {
    const eta = etaAt({ departure: "2026-10-19T07:30", speedKmh: 80 }, 200);
    expect(toLocalInput(eta)).toBe("2026-10-19T10:00");
  });
});
