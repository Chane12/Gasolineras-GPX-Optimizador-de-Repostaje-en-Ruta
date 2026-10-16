import { describe, expect, it } from "vitest";

import type { Station } from "@/lib/map/geo";

import { applyDiscounts, type Discount, matchesBrand, personalize } from "./discounts";

const st = (id: string, name: string, price: number, km = 10) =>
  ({ id, name, price, km_on_route: km, lat: 40, lon: -3, open_24h: true }) as Station;

describe("matchesBrand", () => {
  it.each([
    ["E.S REPSOL", "Repsol", true],
    ["REPSOL BUTANO", "repsol", true],
    ["BP OIL", "BP", true],
    ["BPA SERVICIOS", "BP", false],
    ["MOEVE", "Moeve", true],
    ["GALP Energía", "galp", true],
    ["Petroprix", "", false],
  ])("%s / %s → %s", (name, brand, expected) => {
    expect(matchesBrand(name, brand)).toBe(expected);
  });
});

describe("applyDiscounts", () => {
  const discounts: Discount[] = [
    { brand: "Repsol", kind: "cents", value: 10 },
    { brand: "Repsol", kind: "percent", value: 3 },
    { brand: "Cepsa", kind: "percent", value: 99 }, // fuera de rango: no cuenta
  ];

  it("applies the best matching discount and keeps the pump price", () => {
    expect(applyDiscounts(st("1", "REPSOL", 1.7), discounts)).toMatchObject({
      price: 1.6,
      list_price: 1.7,
      discount_brand: "Repsol",
    });
    // Con 4,00 €/L, el 3 % (0,12) rebaja más que 10 céntimos.
    expect(applyDiscounts(st("1", "REPSOL", 4), discounts).price).toBeCloseTo(3.88, 3);
  });

  it("leaves other brands and invalid discounts alone", () => {
    expect(applyDiscounts(st("2", "CEPSA", 1.7), discounts)).toEqual(st("2", "CEPSA", 1.7));
  });
});

describe("personalize", () => {
  const rule = { topN: 1, segmentKm: 100 };
  const none = { discounts: [], excludedBrands: [] };

  it("chooses the recommended stations again with the prices I will pay", () => {
    // Sin descuento: la más barata es "a" (1,62) y por tramos de 100 km, "a" (km 50) y "b" (km 120).
    const recommended = [st("a", "PLENERGY", 1.62, 50), st("b", "BALLENOIL", 1.63, 120)];
    const others = [st("c", "REPSOL", 1.69, 80), st("d", "CEPSA", 1.7, 150)];

    const result = personalize(
      recommended,
      others,
      { ...none, discounts: [{ brand: "Repsol", kind: "cents", value: 10 }] },
      rule,
    );

    // Con 10 céntimos, Repsol (1,59) es la más barata y la del primer tramo.
    expect(result.recommended.map((s) => [s.id, s.price])).toEqual([
      ["c", 1.59],
      ["b", 1.63],
    ]);
    expect(result.others.map((s) => s.id)).toEqual(["a", "d"]);
  });

  it("leaves out the brands I do not want, and recommends others instead", () => {
    const recommended = [st("a", "PLENERGY", 1.62, 50), st("b", "BALLENOIL", 1.63, 120)];
    const others = [st("c", "REPSOL", 1.69, 80), st("d", "CEPSA", 1.7, 150)];

    const result = personalize(recommended, others, { ...none, excludedBrands: ["Plenergy"] }, rule);

    expect(result.recommended.map((s) => s.id)).toEqual(["c", "b"]);
    expect([...result.recommended, ...result.others].map((s) => s.id)).not.toContain("a");
  });

  it("keeps the API choice without preferences", () => {
    const recommended = [st("a", "X", 1.6)];
    expect(personalize(recommended, [], none, rule).recommended).toEqual(recommended);
  });
});
