import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SourcesPage from "./fuentes/page";
import PrivacyPage from "./privacidad/page";

describe("information pages", () => {
  it("credits every data source", () => {
    render(<SourcesPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Fuentes de datos" })).toBeInTheDocument();
    for (const source of ["MITECO", "OpenStreetMap", "OpenFreeMap", "Photon", "Nominatim", "OSRM"]) {
      expect(screen.getAllByText(new RegExp(source)).length).toBeGreaterThan(0);
    }
  });

  it("explains that nothing personal is kept", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Privacidad" })).toBeInTheDocument();
    expect(screen.getByText(/no hay cookies/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacidad" })).toHaveAttribute("href", "/privacidad");
  });
});
