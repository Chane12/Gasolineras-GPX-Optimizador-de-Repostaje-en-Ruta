# Gasolineras en Ruta — instrucciones para agentes de IA

Optimizador de repostaje en ruta para España: cruza una ruta (GPX u origen/destino) con los precios oficiales del MITECO y sugiere dónde repostar más barato, con radar de autonomía. Público: motoristas y conductores. Lo desarrolla una persona con ayuda de IA: **el repo es la única memoria entre sesiones**.

## Al empezar cada sesión

1. Lee `docs/ROADMAP.md` → fase actual y siguiente tarea.
2. Si vas a tocar una carpeta con su propio `CLAUDE.md`, se cargará solo; respétalo.
3. Antes de cambiar algo "raro", busca el porqué en `docs/decisions/` (ADRs).

## Mapa del repo

| Ruta | Qué es | Estado |
|---|---|---|
| `core/` | Motor geoespacial `gasolineras_core` (lógica de negocio, sin UI) | Activo |
| `legacy/streamlit/` | App Streamlit actual, **en producción** (Streamlit Community Cloud) | Congelada: solo bugs |
| `api/` | FastAPI sobre `core` (`gasolineras_api`) | Fase 1 (esqueleto) |
| `web/` | Next.js | Fase 2 (no existe aún) |
| `docs/` | `ROADMAP.md`, `architecture.md`, `decisions/` (ADRs) | |
| `scripts/` | `verify.sh`, `export-legacy-requirements.sh`, `smoke_legacy.py` | |
| `.claude/` | Hooks (formateo automático) y skills del proyecto | |

## Comandos

```bash
uv sync --all-packages                            # instalar todo el workspace
./scripts/verify.sh                               # lint + formato + tipos + tests + requirements (lo mismo que el CI)
./scripts/verify.sh --smoke                       # + arranca la app Streamlit con la demo (usa red)
uv run pytest -q                                  # solo tests
uv run gasolineras --help                         # CLI del motor
uv run streamlit run legacy/streamlit/app.py      # app actual en local
uv run uvicorn gasolineras_api.main:app --reload  # API en local (http://127.0.0.1:8000/docs)
./scripts/export-legacy-requirements.sh           # tras cambiar dependencias de core o legacy
```

Dependencias: **solo con `uv`** (`uv add --package gasolineras-core <pkg>`), nunca pip ni requirements a mano. Después de cambiar dependencias, regenera `legacy/streamlit/requirements.txt` con el script.

## Invariantes (no romper)

- **CRS**: cálculos de distancia/buffer en `EPSG:25830` (UTM 30N, metros); entrada/salida en `EPSG:4326`. Constantes en `core/.../config.py`, nunca literales sueltos.
- **`core` no depende de ninguna UI** (ni Streamlit, ni FastAPI). La UI importa el core, nunca al revés.
- **Precios**: nunca inventar ni cachear más de 30 min sin avisar; si se usan datos de respaldo, la UI debe decir su antigüedad real (`MitecoResult.from_fallback`).
- **Servicios externos** (MITECO, OSRM, Nominatim): siempre con timeout y degradación elegante; la app no debe caerse si fallan. Ver ADR 0005.
- **Tests sin red**: los tests normales no tocan internet; los que sí, con `@pytest.mark.network`.
- **`legacy/streamlit/` está congelada**: solo correcciones de bugs. Nada de funcionalidades nuevas ahí.

## Convenciones

- **Idioma** (ADR 0004): código, identificadores y commits en **inglés**; textos de la interfaz, documentación y ADRs en **español**. El código heredado mezcla idiomas: no lo traduzcas en masa, solo lo que toques.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`).
- Una rama + un PR por tarea (`feat/...`, `fix/...`, `chore/...`). Nunca commitear directamente a `main`.
- Formateo: lo hace un hook automáticamente al editar (ruff). No discutas estilo; ruff manda.
- Tipos: anota funciones nuevas; pyright debe seguir en 0 errores.

## Definición de "hecho"

Una tarea está terminada solo cuando:
1. `./scripts/verify.sh` pasa en verde (usa la skill `/verificar`).
2. Hay tests para la lógica nueva o el bug corregido.
3. `docs/ROADMAP.md` está actualizado (tarea marcada; deuda nueva anotada).
4. Si se tomó una decisión de arquitectura, hay un ADR nuevo en `docs/decisions/`.

Si algo no se pudo verificar (p. ej. requiere el móvil o el despliegue), dilo explícitamente; no lo des por hecho.

## Despliegue actual

- `main` se despliega solo en Streamlit Community Cloud (archivo principal: `legacy/streamlit/app.py`). Todo lo que entra en `main` llega a producción: por eso PR + CI.
- Streamlit Cloud instala `legacy/streamlit/requirements.txt` y la app importa el core desde `core/src` (shim de `sys.path` en `app.py`). No quitar ese shim mientras exista el despliegue.
