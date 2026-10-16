import { defineConfig, devices } from "@playwright/test";

/**
 * e2e de la web (punto 13 del plan): el flujo completo en móvil y ordenador, con la API simulada y sin red
 * (ver e2e/fake-api.ts). Usa el build de `next build` (lo hace verify.sh antes) y el Chrome del sistema.
 *   ./scripts/pnpm -C web e2e
 */
const PORT = 3100;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: "chrome",
    locale: "es-ES",
    timezoneId: "Europe/Madrid",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "ordenador", use: { viewport: { width: 1440, height: 900 } } },
    {
      name: "movil",
      use: { ...devices["Pixel 7"], channel: "chrome", viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command: `pnpm exec next start -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
