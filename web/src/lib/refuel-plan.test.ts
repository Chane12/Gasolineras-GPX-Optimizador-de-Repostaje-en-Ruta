import { describe, expect, it } from "vitest";

import { type PlanSettings, planRefuels, type PlanStation } from "./refuel-plan";

const st = (key: string, km: number, price: number): PlanStation => ({ key, km, price });
const settings = (over: Partial<PlanSettings> = {}): PlanSettings => ({
  autonomyKm: 300,
  startFraction: 1,
  reserveKm: 0,
  mode: "cheapest",
  ...over,
});

describe("planRefuels", () => {
  it("needs no stop when the tank reaches the destination", () => {
    expect(planRefuels([st("a", 100, 1.6)], 250, settings())).toEqual({
      status: "ok",
      stops: [],
      averagePrice: null,
    });
  });

  it("buys just enough to reach a cheaper station, then fills up there", () => {
    // 500 km, depósito de 300 km. Sale con la mitad (150 km).
    const stations = [st("caraA", 100, 1.8), st("barataB", 220, 1.5), st("caraC", 400, 1.9)];
    const plan = planRefuels(stations, 500, settings({ startFraction: 0.5 }));

    expect(plan.status).toBe("ok");
    if (plan.status !== "ok") return;
    // Lo justo para llegar a B (desde el km 100 con 50 km) y, en B, lo justo para llegar al destino.
    // El cálculo va en pasos de 1,5 km (300 km / 200 niveles): las cantidades, con ese margen.
    expect(plan.stops.map((s) => [s.key, s.full])).toEqual([
      ["caraA", false],
      ["barataB", false],
    ]);
    expect((plan.stops[0]?.fill ?? 0) * 300).toBeCloseTo(70, -0.5);
    expect((plan.stops[1]?.fill ?? 0) * 300).toBeCloseTo(280, -0.5);
  });

  it("is cheaper than stopping at every station on the way", () => {
    const stations = [
      st("a", 80, 1.7),
      st("b", 160, 1.55),
      st("c", 240, 1.75),
      st("d", 320, 1.6),
      st("e", 450, 1.8),
    ];
    const plan = planRefuels(stations, 600, settings({ startFraction: 0.4 }));

    if (plan.status !== "ok") throw new Error(plan.status);
    expect(plan.averagePrice).toBeLessThan(1.65);
    expect(plan.stops.map((s) => s.key)).not.toContain("e");
  });

  it("never goes below the reserve", () => {
    // Con 50 km de reserva, el depósito útil es de 250 km: el km 260 ya no se alcanza desde la salida.
    const stations = [st("a", 200, 1.6), st("b", 260, 1.4), st("c", 420, 1.6)];
    const plan = planRefuels(stations, 600, settings({ reserveKm: 50 }));

    if (plan.status !== "ok") throw new Error(plan.status);
    expect(plan.stops[0]?.key).toBe("a");
  });

  it("with «fewest stops» stops late, only where needed", () => {
    const stations = [st("pronto", 50, 1.4), st("tarde", 260, 1.7), st("c", 520, 1.6)];
    const plan = planRefuels(stations, 700, settings({ mode: "fewest" }));

    if (plan.status !== "ok") throw new Error(plan.status);
    expect(plan.stops.map((s) => s.key)).toEqual(["tarde", "c"]);
    // En la cara echa lo justo para llegar a la siguiente, más barata, y allí el resto.
    expect(plan.stops[0]?.full).toBe(false);
  });

  it("does not stop to add a little to save a fraction of a cent", () => {
    // Ir de la primera a la segunda (1 km después, 0,001 €/L más barata) no compensa otra parada.
    const stations = [st("a", 100, 1.67), st("b", 101, 1.669), st("c", 250, 1.7), st("d", 380, 1.7)];
    const plan = planRefuels(stations, 500, settings({ startFraction: 0.4 }));

    if (plan.status !== "ok") throw new Error(plan.status);
    expect(plan.stops.filter((s) => s.km < 110)).toHaveLength(1);
  });

  it("does not stop at every station when several have the same price", () => {
    const stations = [
      st("a", 159, 1.669),
      st("b", 160, 1.669),
      st("c", 161, 1.669),
      st("d", 236, 1.67),
      st("e", 420, 1.7),
    ];
    const plan = planRefuels(stations, 550, settings({ startFraction: 0.6 }));

    if (plan.status !== "ok") throw new Error(plan.status);
    expect(plan.stops.filter((s) => s.price === 1.669)).toHaveLength(1);
  });

  it("says where the route cannot be done", () => {
    const plan = planRefuels([st("a", 100, 1.6), st("b", 500, 1.6)], 700, settings());

    expect(plan).toEqual({ status: "impossible", fromKm: 100, toKm: 500, reason: "gap" });
  });

  it("refuses to start below the reserve", () => {
    expect(planRefuels([], 100, settings({ startFraction: 0.1, reserveKm: 50 }))).toMatchObject({
      status: "impossible",
      reason: "start-below-reserve",
    });
  });
});

/** Coste mínimo exacto por programación dinámica (km enteros): la referencia para «lo más barato». */
function optimalCost(
  stations: PlanStation[],
  routeKm: number,
  capacity: number,
  startFuel: number,
): number | null {
  const sorted = [...stations].sort((a, b) => a.km - b.km);
  // best[f] = coste mínimo para estar en el punto actual con f km en el depósito.
  let best = new Map<number, number>([[startFuel, 0]]);
  let pos = 0;
  const points = [...sorted, { key: "fin", km: routeKm, price: 0 }];
  for (const point of points) {
    const next = new Map<number, number>();
    const dist = point.km - pos;
    for (const [fuel, cost] of best) {
      const left = fuel - dist;
      if (left < 0) continue;
      if (point.key === "fin") {
        next.set(0, Math.min(next.get(0) ?? Infinity, cost));
        continue;
      }
      for (let buy = 0; left + buy <= capacity; buy++) {
        const c = cost + buy * point.price;
        if (c < (next.get(left + buy) ?? Infinity)) next.set(left + buy, c);
      }
    }
    best = next;
    pos = point.km;
  }
  return best.size > 0 ? Math.min(...best.values()) : null;
}

function costOf(plan: ReturnType<typeof planRefuels>, capacity: number): number | null {
  if (plan.status !== "ok") return null;
  return plan.stops.reduce((sum, s) => sum + s.fill * capacity * s.price, 0);
}

describe("planRefuels «lo más barato» is optimal", () => {
  it("matches the exact optimum on random routes", () => {
    let seed = 7;
    const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let run = 0; run < 300; run++) {
      const routeKm = 60 + Math.floor(random() * 80);
      const capacity = 20 + Math.floor(random() * 30);
      const startFuel = Math.floor(random() * capacity);
      const kms = new Set<number>();
      while (kms.size < 6) kms.add(1 + Math.floor(random() * (routeKm - 1)));
      const stations = [...kms].map((km, i) => st(`s${i}`, km, 1 + Math.floor(random() * 50) / 100));

      const expected = optimalCost(stations, routeKm, capacity, startFuel);
      // Sin coste por parada y con km enteros (depósito < 200 km), el plan debe ser el óptimo exacto.
      const plan = planRefuels(
        stations,
        routeKm,
        { autonomyKm: capacity, startFraction: startFuel / capacity, reserveKm: 0, mode: "cheapest" },
        { stopPenalty: 0 },
      );
      if (expected === null) expect(plan.status).toBe("impossible");
      else expect(costOf(plan, capacity)).toBeCloseTo(expected, 6);
    }
  });
});
