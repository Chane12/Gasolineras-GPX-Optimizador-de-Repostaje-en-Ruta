import { expect, test } from "@playwright/test";

import { useFakeApi } from "./fake-api";

/**
 * Presupuesto de rendimiento (plan, "Calidad"): el inicio no carga el mapa (MapLibre se pide al llegar a la
 * ruta) y su JavaScript, comprimido, no pasa del presupuesto.
 */
const HOME_JS_BUDGET_KB = 260;

test("the home page stays light and does not load the map", async ({ page }) => {
  await useFakeApi(page);
  const scripts: { url: string; bytes: number }[] = [];
  page.on("response", async (response) => {
    if (response.request().resourceType() !== "script") return;
    // Lo que viaja por la red (comprimido), que es lo que cuenta en un móvil con 4G.
    const sizes = await response
      .request()
      .sizes()
      .catch(() => null);
    scripts.push({ url: response.url(), bytes: sizes?.responseBodySize ?? 0 });
  });

  await page.goto("/", { waitUntil: "networkidle" });

  const totalKb = scripts.reduce((sum, s) => sum + s.bytes, 0) / 1024;
  test.info().annotations.push({ type: "JS del inicio", description: `${totalKb.toFixed(0)} KB` });
  expect(scripts.some((s) => /maplibre/i.test(s.url))).toBe(false);
  expect(totalKb).toBeLessThan(HOME_JS_BUDGET_KB);
});
