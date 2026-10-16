import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Tests sin red (como en Python): cualquier fetch real falla. Los tests que hablan con la API
// inyectan su propio fetch simulado (createApiClient({ fetch })).
vi.stubGlobal("fetch", () => Promise.reject(new TypeError("Red desactivada en los tests")));

// Sin "globals" de Vitest, Testing Library no limpia el DOM solo entre tests.
afterEach(() => {
  cleanup();
});
