# Gasolineras en Ruta

Encuentra las gasolineras más baratas a lo largo de tu ruta por España. Cruza tu trayecto (archivo GPX u origen y destino) con los precios oficiales del Ministerio para la Transición Ecológica (MITECO), tiene en cuenta el desvío real por carretera y avisa de los tramos en los que tu moto o coche podría quedarse sin combustible.

> **Estado**: la app actual (Streamlit) está en producción. Se está construyendo una web nueva (FastAPI + Next.js). Ver [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Estructura

| Carpeta | Contenido |
|---|---|
| [`core/`](core/) | Motor geoespacial `gasolineras_core` (ingesta MITECO, GPX, corredor espacial, optimizador) y CLI |
| [`legacy/streamlit/`](legacy/streamlit/) | App Streamlit actual (en producción, congelada) |
| [`docs/`](docs/) | [Roadmap](docs/ROADMAP.md), [arquitectura](docs/architecture.md) y [decisiones](docs/decisions/) |
| [`scripts/`](scripts/) | Verificación y utilidades |

## Puesta en marcha

Requisitos: Python 3.11+ y [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
git clone https://github.com/Chane12/Gasolineras-GPX-Optimizador-de-Repostaje-en-Ruta.git
cd Gasolineras-GPX-Optimizador-de-Repostaje-en-Ruta
uv sync --all-packages
```

## Uso

```bash
# App web actual
uv run streamlit run legacy/streamlit/app.py

# CLI (por defecto usa la ruta de demo de la Sierra de Gredos)
uv run gasolineras --fuel "Precio Gasolina 95 E5" --top 10 --segment-km 50
uv run gasolineras --help
```

## Desarrollo

```bash
./scripts/verify.sh          # lint, formato, tipos, tests y dependencias (lo mismo que el CI)
./scripts/verify.sh --smoke  # además arranca la app con la demo (necesita internet)
```

El proyecto se desarrolla con ayuda de IA (Claude Code): las instrucciones para los agentes están en [`CLAUDE.md`](CLAUDE.md) y las skills del proyecto en `.claude/skills/`.

## Licencia

Software propietario, todos los derechos reservados: el código se publica solo para su consulta. Ver [`LICENSE`](LICENSE) y el [ADR 0006](docs/decisions/0006-licencia-propietaria.md). Datos de precios: © Ministerio para la Transición Ecológica y el Reto Demográfico. Mapas y rutas: © colaboradores de OpenStreetMap.
