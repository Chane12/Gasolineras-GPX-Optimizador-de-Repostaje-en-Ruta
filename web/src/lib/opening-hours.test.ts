import { describe, expect, it } from "vitest";

import { isOpenAt } from "./opening-hours";

// 2026-10-19 es lunes; 2026-10-24, sábado; 2026-10-25, domingo.
const at = (day: number, hh: number, mm = 0) => new Date(2026, 9, day, hh, mm);

describe("isOpenAt", () => {
  it.each([
    ["L-D: 24H", at(25, 3), true],
    ["L-D: 06:00-22:00", at(19, 5, 59), false],
    ["L-D: 06:00-22:00", at(19, 6), true],
    ["L-D: 06:00-22:00", at(19, 22), false],
    ["L-V: 06:00-22:00; S-D: 08:00-14:00", at(24, 7), false],
    ["L-V: 06:00-22:00; S-D: 08:00-14:00", at(24, 9), true],
    ["L-V: 06:00-22:00; S-D: 08:00-14:00", at(24, 15), false],
    ["L-S: 06:00-22:00", at(25, 12), false], // domingo cerrada
    ["L-D: 00:00-23:59", at(19, 23, 59), true],
  ])("%s at %s → %s", (schedule, date, expected) => {
    expect(isOpenAt(schedule, date)).toBe(expected);
  });

  it("handles opening hours past midnight", () => {
    expect(isOpenAt("L-D: 06:00-02:00", at(19, 1))).toBe(true); // tramo del domingo
    expect(isOpenAt("L-D: 06:00-02:00", at(19, 3))).toBe(false);
    expect(isOpenAt("L-V: 22:00-06:00", at(24, 3))).toBe(true); // viernes noche → sábado de madrugada
    expect(isOpenAt("L-V: 22:00-06:00", at(25, 3))).toBe(false); // sábado noche no abre
  });

  it("does not guess with formats it does not understand", () => {
    expect(isOpenAt("L: 24H", at(19, 12))).toBeNull(); // solo "L": ambiguo
    expect(isOpenAt("Consultar en la gasolinera", at(19, 12))).toBeNull();
    expect(isOpenAt(null, at(19, 12))).toBeNull();
  });
});
