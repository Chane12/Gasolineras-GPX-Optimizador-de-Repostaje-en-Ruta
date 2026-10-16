import { describe, expect, it } from "vitest";

import { autoSegmentKm, formatSchedule, formatStationName, trackLengthKm } from "./stations";

describe("formatStationName", () => {
  it.each([
    ["E.S GREDOS", "E.S Gredos"],
    ["BALLENOIL", "Ballenoil"],
    ["BP", "BP"],
    ["EESS ROTONDA", "EESS Rotonda"],
    ["ESTACION DE SERVICIO LA RAYA", "Estacion de Servicio la Raya"],
    ["PETROPRIX  ÁVILA", "Petroprix Ávila"],
    ["Repsol", "Repsol"],
    ["GALP Energía", "GALP Energía"],
    ["24", "24"],
  ])("%s → %s", (raw, expected) => {
    expect(formatStationName(raw)).toBe(expected);
  });
});

describe("formatSchedule", () => {
  it.each([
    ["L-D: 24H", "24 h"],
    ["L-D: 06:00-22:00", "6–22 h"],
    ["L-D: 06:30-22:30", "6:30–22:30 h"],
    ["L-D: 06:00-00:00", "6–24 h"],
    ["L-D: 00:00-23:59", "24 h"],
    ["L-V: 06:00-22:00; S-D: 07:00-22:00", "L-V 6–22 h · S-D 7–22 h"],
    ["L-S: 06:00-22:00; D: 08:00-14:00", "L-S 6–22 h · D 8–14 h"],
    ["L: 07:00-23:00", "L 7–23 h"],
    ["Consultar en la gasolinera", "Consultar en la gasolinera"],
  ])("%s → %s", (raw, expected) => {
    expect(formatSchedule(raw)).toBe(expected);
  });

  it("is null without a schedule", () => {
    expect(formatSchedule(null)).toBeNull();
    expect(formatSchedule("  ")).toBeNull();
  });
});

describe("trackLengthKm", () => {
  it("measures a track along the great circle", () => {
    // Madrid → Valencia en línea recta: unos 300 km.
    expect(
      trackLengthKm([
        [-3.7038, 40.4168],
        [-0.3763, 39.4699],
      ]),
    ).toBeCloseTo(302, -1);
    expect(trackLengthKm([[-3.7, 40.4]])).toBe(0);
  });
});

describe("autoSegmentKm", () => {
  it("splits the route in about six stretches, within the API limits", () => {
    expect(autoSegmentKm(352)).toBe(60);
    expect(autoSegmentKm(30)).toBe(10);
    expect(autoSegmentKm(5000)).toBe(300);
  });
});
