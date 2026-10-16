import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fakeApi, jsonResponse, renderWithQuery } from "@/test-utils";

import { SearchForm, type SearchSubmission } from "./search-form";

const FUELS = [
  { id: "gasolina_95", label: "Gasolina 95" },
  { id: "diesel", label: "Diésel (Gasoil A)" },
];

const place = (name: string, context: string, lat: number, lon: number) => ({
  name,
  context,
  lat,
  lon,
  kind: "city",
});
const MADRID = place("Madrid", "Comunidad de Madrid", 40.41678, -3.70379);
const MADRIDEJOS = place("Madridejos", "Toledo, Castilla-La Mancha", 39.468, -3.532);
const VALENCIA = place("València", "Comunitat Valenciana", 39.46975, -0.37739);
const VALENCIA_DJ = place("Valencia de Don Juan", "León, Castilla y León", 42.29, -5.52);

/** Sugerencias simuladas: lo que devolvería Photon para cada texto (sin acentos ni mayúsculas). */
const SUGGESTIONS: Record<string, unknown[]> = {
  valen: [VALENCIA, VALENCIA_DJ],
  valencia: [VALENCIA, VALENCIA_DJ],
  madrid: [MADRID, MADRIDEJOS],
  mdrid: [MADRID, MADRIDEJOS],
  avila: [place("Ávila", "Castilla y León", 40.65, -4.69)],
  segovia: [place("Segovia", "Castilla y León", 40.94, -4.11)],
  xyzzy: [],
};

function setup({ placesDown = false } = {}) {
  const onSubmit = vi.fn<(s: SearchSubmission) => void>();
  const client = fakeApi((request) => {
    const url = new URL(request.url);
    if (url.pathname === "/fuels") return jsonResponse(FUELS);
    if (url.pathname === "/places/suggest") {
      if (placesDown) return jsonResponse({ detail: "Photon no responde" }, { status: 503 });
      const q = (url.searchParams.get("q") ?? "")
        .normalize("NFD")
        .replace(/\p{Diacritic}/gu, "")
        .toLowerCase()
        .trim();
      return jsonResponse({ places: SUGGESTIONS[q] ?? [] });
    }
    return new Response(null, { status: 404 });
  });
  renderWithQuery(<SearchForm onSubmit={onSubmit} client={client} />);
  return { onSubmit, user: userEvent.setup() };
}

const origin = () => screen.getByRole("combobox", { name: "Origen" });
const destination = () => screen.getByRole("combobox", { name: "Destino" });
const submit = () => screen.getByRole("button", { name: "Ver gasolineras de la ruta" });

describe("SearchForm", () => {
  it("suggests places while typing and keeps the exact place picked", async () => {
    const { onSubmit, user } = setup();

    await user.type(destination(), "Valen");
    const list = await screen.findByRole("listbox", { name: "Sugerencias de destino" });
    expect(
      within(list)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["ValènciaComunitat Valenciana", "Valencia de Don JuanLeón, Castilla y León"]);
    await user.click(within(list).getByRole("option", { name: /Valencia de Don Juan/ }));
    expect(destination()).toHaveValue("Valencia de Don Juan");
    expect(screen.queryByRole("listbox", { name: "Sugerencias de destino" })).not.toBeInTheDocument();

    await user.type(origin(), "Madrid");
    await user.click(submit());

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        kind: "text",
        origen: { text: "Madrid", point: { lat: 40.41678, lon: -3.70379 } },
        destino: { text: "Valencia de Don Juan", point: { lat: 42.29, lon: -5.52 } },
        combustible: "gasolina_95",
      }),
    );
  });

  it("can be used with the keyboard: arrows to move, Enter to pick", async () => {
    const { user } = setup();

    await user.type(destination(), "Valen");
    await screen.findByRole("option", { name: /València/ });
    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(screen.getByRole("option", { name: /Valencia de Don Juan/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.keyboard("{Enter}");

    expect(destination()).toHaveValue("Valencia de Don Juan");
  });

  it("explains a misspelt place in its field and offers alternatives, without leaving the page", async () => {
    const { onSubmit, user } = setup();

    await user.type(origin(), "Mdrid");
    await user.type(destination(), "Valencia");
    await user.keyboard("{Escape}");
    await user.click(submit());

    const message = await screen.findByText("«Mdrid» no aparece tal cual. ¿Te refieres a…?");
    expect(onSubmit).not.toHaveBeenCalled();
    expect(origin()).toHaveAttribute("aria-invalid", "true");
    await user.click(
      within(message.closest("[role=alert]") as HTMLElement).getByRole("button", {
        name: /^MadridComunidad/,
      }),
    );
    expect(origin()).toHaveValue("Madrid");
    expect(screen.queryByText(/no aparece tal cual/)).not.toBeInTheDocument();

    await user.click(submit());
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0]?.[0]).toMatchObject({
      origen: { text: "Madrid" },
      destino: { text: "València", point: { lat: 39.46975, lon: -0.37739 } },
    });
  });

  it("says when a place does not exist at all", async () => {
    const { onSubmit, user } = setup();

    await user.type(origin(), "Xyzzy");
    await user.type(destination(), "Valencia");
    await user.click(submit());

    expect(await screen.findByText(/No encontramos «Xyzzy». Revisa cómo está escrito/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("still searches by name when suggestions are unavailable", async () => {
    const { onSubmit, user } = setup({ placesDown: true });

    await user.type(origin(), "Ávila");
    await user.type(destination(), "Segovia");
    await user.click(submit());

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        kind: "text",
        origen: { text: "Ávila" },
        destino: { text: "Segovia" },
        combustible: "gasolina_95",
      }),
    );
  });

  it("explains what is missing instead of submitting", async () => {
    const { onSubmit, user } = setup();

    await user.click(submit());

    expect(await screen.findByText("Escribe de dónde sales.")).toBeInTheDocument();
    expect(screen.getByText("Escribe a dónde vas.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("swaps origin and destination", async () => {
    const { user } = setup();

    await user.type(origin(), "Ávila");
    await user.type(destination(), "Segovia");
    await user.click(screen.getByRole("button", { name: "Intercambiar origen y destino" }));

    expect(origin()).toHaveValue("Segovia");
    expect(destination()).toHaveValue("Ávila");
  });

  it("lists the fuels from the API", async () => {
    const { onSubmit, user } = setup();

    await screen.findByRole("option", { name: "Diésel (Gasoil A)" });
    await user.selectOptions(screen.getByLabelText("Combustible"), "diesel");
    await user.type(origin(), "Ávila");
    await user.type(destination(), "Segovia");
    await user.click(submit());

    await waitFor(() => expect(onSubmit.mock.calls[0]?.[0].combustible).toBe("diesel"));
  });

  it("uses a GPX file instead of origin and destination", async () => {
    const { onSubmit, user } = setup();
    const file = new File(["<gpx></gpx>"], "ruta.gpx", { type: "application/gpx+xml" });

    await user.upload(screen.getByLabelText("Archivo GPX de tu ruta"), file);
    expect(screen.getByText("ruta.gpx")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Origen" })).not.toBeInTheDocument();
    await user.click(submit());

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({ kind: "gpx", file, combustible: "gasolina_95" }),
    );
  });

  it("refuses files that are not GPX", async () => {
    setup();
    const user = userEvent.setup({ applyAccept: false }); // the browser would filter by `accept`; drag & drop would not
    const file = new File(["x"], "foto.jpg", { type: "image/jpeg" });

    await user.upload(screen.getByLabelText("Archivo GPX de tu ruta"), file);

    expect(screen.getByText(/Elige un archivo .gpx/)).toBeInTheDocument();
    expect(origin()).toBeInTheDocument();
  });
});
