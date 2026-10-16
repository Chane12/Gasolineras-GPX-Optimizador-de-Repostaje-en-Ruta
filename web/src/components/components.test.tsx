import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FreshnessPill } from "./freshness-pill";
import { Hito } from "./hito";
import { PricePlate } from "./price-plate";
import { StationRow } from "./station-row";
import { SummaryStats } from "./summary-stats";

function renderRow(overrides: Partial<Parameters<typeof StationRow>[0]> = {}) {
  const onTogglePlan = vi.fn();
  render(
    <ul>
      <StationRow
        name="Ballenoil"
        kmOnRoute={118.2}
        price={1.639}
        town="Tarancón"
        schedule="24 h"
        detourKm={0.43}
        inPlan={false}
        onTogglePlan={onTogglePlan}
        {...overrides}
      />
    </ul>,
  );
  return { onTogglePlan };
}

describe("StationRow", () => {
  it("shows name, details, km and price in Spanish format", () => {
    renderRow();

    const row = screen.getByRole("listitem");
    expect(row).toHaveTextContent("Ballenoil");
    expect(row).toHaveTextContent("Tarancón · 24 h · desvío 0,4 km");
    expect(row).toHaveTextContent("km 118");
    expect(row).toHaveTextContent("1,639 euros por litro");
  });

  it("adds the station to the plan with an accessible toggle button", async () => {
    const { onTogglePlan } = renderRow();

    const button = screen.getByRole("button", { name: "Añadir Ballenoil a tus paradas" });
    expect(button).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(button);

    expect(onTogglePlan).toHaveBeenCalledOnce();
  });

  it("offers to remove it once it is in the plan", () => {
    renderRow({ inPlan: true });

    expect(screen.getByRole("button", { name: "Quitar Ballenoil de tus paradas" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("labels the cheapest station and omits unknown details", () => {
    renderRow({ cheapest: true, town: null, schedule: null, detourKm: null });

    expect(screen.getByText("MÁS BARATA")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).not.toHaveTextContent("desvío");
  });
});

describe("Hito", () => {
  it("reads as a kilometre for screen readers", () => {
    render(<Hito km={322.6} />);
    expect(screen.getByText("km", { exact: false }).parentElement).toHaveTextContent("km 323");
  });
});

describe("PricePlate", () => {
  it("announces the cheapest plate", () => {
    render(<PricePlate price={1.639} tone="best" />);
    expect(screen.getByText(/La más barata/).parentElement).toHaveTextContent("La más barata: 1,639");
  });
});

describe("SummaryStats", () => {
  it("renders a description list", () => {
    render(
      <SummaryStats
        stats={[
          { label: "Encontradas", value: "9" },
          { label: "Mejor precio", value: "1,639" },
        ]}
      />,
    );

    expect(screen.getByText("Encontradas").tagName).toBe("DT");
    expect(screen.getByText("9").tagName).toBe("DD");
  });
});

describe("FreshnessPill", () => {
  it.each([
    ["fresh", 12, "Precios MITECO · hace 12 min"],
    ["stale", 190, "Precios de hace 3 h"],
    ["very_stale", 3000, "Precios de hace 2 días: pueden no estar al día"],
    ["loading", null, "Cargando precios…"],
    ["unavailable", null, "Precios no disponibles ahora mismo"],
  ] as const)("%s → %s", (status, age, text) => {
    render(<FreshnessPill status={status} ageMinutes={age} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });
});
