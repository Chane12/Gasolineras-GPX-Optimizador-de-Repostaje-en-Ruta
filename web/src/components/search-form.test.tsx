import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fakeApi, jsonResponse, renderWithQuery } from "@/test-utils";

import { SearchForm, type SearchSubmission } from "./search-form";

const FUELS = [
  { id: "gasolina_95", label: "Gasolina 95" },
  { id: "diesel", label: "Diésel (Gasoil A)" },
];

function setup() {
  const onSubmit = vi.fn<(s: SearchSubmission) => void>();
  const client = fakeApi(() => jsonResponse(FUELS));
  renderWithQuery(<SearchForm onSubmit={onSubmit} client={client} />);
  return { onSubmit, user: userEvent.setup() };
}

const defaults = {
  combustible: "gasolina_95",
  radio: 5,
  top: 5,
  tramo: 50,
  abierta24h: false,
  vaciada: false,
  autonomia: 0,
};

describe("SearchForm", () => {
  it("submits origin, destination and default options (autonomy off)", async () => {
    const { onSubmit, user } = setup();

    await user.type(screen.getByLabelText("Origen"), " Madrid ");
    await user.type(screen.getByLabelText("Destino"), "Valencia");
    await user.click(screen.getByRole("button", { name: "Ver gasolineras de la ruta" }));

    expect(onSubmit).toHaveBeenCalledWith({
      kind: "text",
      origen: "Madrid",
      destino: "Valencia",
      options: defaults,
    });
  });

  it("explains what is missing instead of submitting", async () => {
    const { onSubmit, user } = setup();

    await user.click(screen.getByRole("button", { name: "Ver gasolineras de la ruta" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Origen")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Origen")).toHaveAccessibleDescription("Escribe de dónde sales.");
    expect(screen.getByText("Escribe a dónde vas.")).toBeInTheDocument();
  });

  it("swaps origin and destination", async () => {
    const { user } = setup();

    await user.type(screen.getByLabelText("Origen"), "Ávila");
    await user.type(screen.getByLabelText("Destino"), "Segovia");
    await user.click(screen.getByRole("button", { name: "Intercambiar origen y destino" }));

    expect(screen.getByLabelText("Origen")).toHaveValue("Segovia");
    expect(screen.getByLabelText("Destino")).toHaveValue("Ávila");
  });

  it("lists the fuels from the API", async () => {
    const { onSubmit, user } = setup();

    await screen.findByRole("option", { name: "Diésel (Gasoil A)" });
    await user.selectOptions(screen.getByLabelText("Combustible"), "diesel");
    await user.type(screen.getByLabelText("Origen"), "Ávila");
    await user.type(screen.getByLabelText("Destino"), "Segovia");
    await user.click(screen.getByRole("button", { name: "Ver gasolineras de la ruta" }));

    expect(onSubmit.mock.calls[0]?.[0].options.combustible).toBe("diesel");
  });

  it("autonomy is optional: off by default, then a profile or custom km", async () => {
    const { onSubmit, user } = setup();

    await user.click(screen.getByText("Más opciones"));
    expect(screen.getByText(/aviso de autonomía desactivado/)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/Avisarme de tramos más largos/));
    await user.click(screen.getByRole("radio", { name: /Otra/ }));
    await user.type(screen.getByLabelText("Tu autonomía (km)"), "32a0");
    await user.type(screen.getByLabelText("Origen"), "Ávila");
    await user.type(screen.getByLabelText("Destino"), "Segovia");
    await user.click(screen.getByRole("button", { name: "Ver gasolineras de la ruta" }));

    expect(onSubmit.mock.calls[0]?.[0].options.autonomia).toBe(320);
    expect(screen.getByText(/autonomía 320 km/)).toBeInTheDocument();
  });

  it("rejects an impossible custom autonomy", async () => {
    const { onSubmit, user } = setup();

    await user.click(screen.getByText("Más opciones"));
    await user.click(screen.getByLabelText(/Avisarme de tramos más largos/));
    await user.click(screen.getByRole("radio", { name: /Otra/ }));
    await user.type(screen.getByLabelText("Tu autonomía (km)"), "9");
    await user.type(screen.getByLabelText("Origen"), "Ávila");
    await user.type(screen.getByLabelText("Destino"), "Segovia");
    await user.click(screen.getByRole("button", { name: "Ver gasolineras de la ruta" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/Indica tu autonomía en km/)).toBeInTheDocument();
  });

  it("uses a GPX file instead of origin and destination", async () => {
    const { onSubmit, user } = setup();
    const file = new File(["<gpx></gpx>"], "ruta.gpx", { type: "application/gpx+xml" });

    await user.upload(screen.getByLabelText("Archivo GPX de tu ruta"), file);
    expect(screen.getByText("ruta.gpx")).toBeInTheDocument();
    expect(screen.queryByLabelText("Origen")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ver gasolineras de la ruta" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ kind: "gpx", file, options: defaults }));
  });

  it("refuses files that are not GPX", async () => {
    setup();
    const user = userEvent.setup({ applyAccept: false }); // the browser would filter by `accept`; drag & drop would not
    const file = new File(["x"], "foto.jpg", { type: "image/jpeg" });

    await user.upload(screen.getByLabelText("Archivo GPX de tu ruta"), file);

    expect(screen.getByText(/Elige un archivo .gpx/)).toBeInTheDocument();
    expect(screen.getByLabelText("Origen")).toBeInTheDocument();
  });
});
