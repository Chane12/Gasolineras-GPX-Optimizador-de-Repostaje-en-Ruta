import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/test-utils";

import Home from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("Home", () => {
  it("leads with the product promise and the search form", () => {
    renderWithQuery(<Home />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Organiza tu ruta y decide dónde repostar." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Buscar gasolineras en tu ruta" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Probar con una ruta de ejemplo" })).toHaveAttribute(
      "href",
      "/ruta?demo=true",
    );
  });

  it("credits the data sources", () => {
    renderWithQuery(<Home />);

    expect(screen.getByRole("contentinfo")).toHaveTextContent("Ministerio para la Transición Ecológica");
    expect(screen.getByRole("contentinfo")).toHaveTextContent("OpenStreetMap");
  });
});
