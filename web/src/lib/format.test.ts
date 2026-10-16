import { describe, expect, it } from "vitest";

import { formatAge, formatEuros, formatKm, formatPrice, formatPriceDelta, formatShortKm } from "./format";

describe("format", () => {
  it("prices use a decimal comma and three decimals", () => {
    expect(formatPrice(1.639)).toBe("1,639");
    expect(formatPrice(0.9)).toBe("0,900");
  });

  it("deltas and euros use two decimals", () => {
    expect(formatPriceDelta(0.21)).toBe("0,21");
    expect(formatEuros(5.4)).toBe("5,40");
  });

  it("route km are whole numbers and detours have one decimal", () => {
    expect(formatKm(118.4)).toBe("118");
    expect(formatKm(117.5)).toBe("118");
    expect(formatShortKm(1.23)).toBe("1,2");
  });

  it.each([
    [0, "0 min"],
    [12.7, "12 min"],
    [59, "59 min"],
    [60, "1 h"],
    [190, "3 h"],
    [1439, "23 h"],
    [1440, "1 día"],
    [3000, "2 días"],
  ])("age %s min → %s", (minutes, expected) => {
    expect(formatAge(minutes)).toBe(expected);
  });
});
