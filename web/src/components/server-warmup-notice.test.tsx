import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, jsonResponse, renderWithQuery } from "@/test-utils";

import { ServerWarmupNotice } from "./server-warmup-notice";

const healthy = { status: "ok", version: "0.1.0", prices: { status: "fresh", station_count: 11491 } };

describe("ServerWarmupNotice", () => {
  it("explains that the server is waking up when /health is slow", async () => {
    const client = fakeApi(() => new Promise<Response>(() => {}));

    renderWithQuery(<ServerWarmupNotice client={client} slowAfterMs={10} />);

    expect(await screen.findByRole("status")).toHaveTextContent("Despertando el servidor…");
  });

  it("shows nothing when the server answers", async () => {
    const client = fakeApi(() => jsonResponse(healthy));

    const { container } = renderWithQuery(<ServerWarmupNotice client={client} slowAfterMs={10} />);

    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the error and lets the user retry", async () => {
    let calls = 0;
    const client = fakeApi(() => {
      calls += 1;
      return calls === 1 ? new Response(null, { status: 503 }) : jsonResponse(healthy);
    });

    renderWithQuery(<ServerWarmupNotice client={client} slowAfterMs={10} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("El servidor no responde ahora mismo.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await screen.findByText((_, el) => el === document.body && !screen.queryByRole("alert"));
    expect(calls).toBe(2);
  });
});
