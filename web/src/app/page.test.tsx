import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithQuery } from "@/test-utils";

import Home from "./page";

describe("Home", () => {
  it("shows the product name as the main heading", () => {
    renderWithQuery(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "Gasolineras en Ruta" })).toBeInTheDocument();
  });
});
