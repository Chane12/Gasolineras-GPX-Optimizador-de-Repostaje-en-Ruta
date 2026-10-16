import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PassingTimeOptions } from "./passing-time-options";

const settings = { enabled: true, departure: "2026-10-19T07:30", speedKmh: 80, hideClosed: false };

describe("PassingTimeOptions", () => {
  it("offers the average speed of the calculated route", async () => {
    const onChange = vi.fn();
    render(<PassingTimeOptions settings={settings} onChange={onChange} routeSpeedKmh={95} />);

    expect(screen.getByText(/unos 95 km\/h de media/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usar 95 km/h" }));
    expect(onChange).toHaveBeenCalledWith({ speedKmh: 95 });
  });

  it("gives the general advice when the route has no duration", () => {
    render(<PassingTimeOptions settings={settings} onChange={() => {}} />);

    expect(screen.getByText(/por autovía, unos 90 km\/h/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Usar/ })).not.toBeInTheDocument();
  });
});
