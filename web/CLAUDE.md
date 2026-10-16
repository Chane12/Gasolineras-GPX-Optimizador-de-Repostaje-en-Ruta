# web/ — la web (Next.js)

Sustituye a la app Streamlit (Fase 2). Antes de tocar nada, lee:

- [`docs/web/plan.md`](../docs/web/plan.md): pantallas, flujo, paridad y orden de trabajo.
- [`docs/web/diseno.md`](../docs/web/diseno.md): sistema de diseño aprobado por el propietario. Es la fuente de verdad visual, con las maquetas en `docs/web/maquetas/`.
- [ADR 0008](../docs/decisions/0008-web-stack.md): stack y motivos.

## Node y pnpm: siempre los del proyecto

- **Node 24 LTS** fijado en `/.node-version`. Se instala en `/.tools/node` con `./scripts/setup-node.sh` (descarga oficial con la suma SHA-256 verificada). El Node del sistema no se usa.
- **pnpm** en la versión de `packageManager` (`package.json`). Siempre a través del envoltorio, desde la raíz del repo:
  ```bash
  ./scripts/pnpm -C web dev            # http://localhost:3000
  ./scripts/pnpm -C web test           # vitest
  ./scripts/pnpm -C web lint | typecheck | format | build
  ./scripts/pnpm -C web add <paquete>  # añadir dependencias (nunca npm ni yarn)
  ```
  El envoltorio desactiva también la telemetría de Next.js.
- **Seguridad de dependencias** (`pnpm-workspace.yaml`):
  - `minimumReleaseAge` impide instalar versiones publicadas hace menos de 7 días.
  - Los scripts de instalación de las dependencias están bloqueados (`allowBuilds`). Para permitir uno, dilo en el PR y explica por qué.
- `pnpm-lock.yaml` va en el repo. El CI instala con `--frozen-lockfile`.

## Reglas

- **TypeScript estricto** (`strict`, `noUncheckedIndexedAccess`, `verbatimModuleSyntax`). Nada de `any`; si hace falta, `unknown` y estrechar el tipo.
- **Los tipos de la API se generan** desde `api/openapi.json` (paso 4 del plan); nunca se escriben a mano.
- **Diseño**: solo los tokens de `diseno.md`, a través del tema de Tailwind. Nada de colores, fuentes o radios sueltos. Nada de pastel, degradados ni emojis. El azul (`accent`) es el único color de acción y el rojo, solo el del hito.
- **Accesibilidad**:
  - `<button>` y `<a href>` reales, con `aria-label` en los botones de solo icono.
  - Objetivos táctiles de al menos 44 px y contraste AA.
  - Todo lo del mapa tiene que poder hacerse también desde la lista.
- **Textos en español** (tuteo, vocabulario de carretera); identificadores y código en inglés (ADR 0004). Precios con coma decimal (`1,639 €/L`).
- **Tests**:
  - `*.test.ts(x)` junto al código, con Testing Library y consultas por rol o texto, como lo usaría una persona.
  - Sin red: la API se simula.
- Estructura: `src/app/` (rutas, App Router), y más adelante `src/components/`, `src/lib/` (cliente de la API, utilidades) y `src/styles/` según se necesiten.

## Verificación

`./scripts/verify.sh` (desde la raíz) ejecuta también la web: dependencias, lint, tipos, formato, tests y `next build`. Si cambias algo visual, compáralo con la maqueta correspondiente y di en el PR qué no has podido comprobar (p. ej. en un móvil real).
