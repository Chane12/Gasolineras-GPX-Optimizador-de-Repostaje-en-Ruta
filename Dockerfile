# API de Gasolineras en Ruta (FastAPI + gasolineras_core). Contenedor estándar: Cloud Run, Render… (ADR 0002).
#   docker build -t gasolineras-api .
#   docker run -p 8080:8080 gasolineras-api      → http://localhost:8080/docs
# Variables: PORT (8080), GASOLINERAS_TRUSTED_PROXY_HOPS (1 detrás de Cloud Run), GASOLINERAS_LOG_LEVEL (INFO).

FROM python:3.11-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# 1) Dependencias (capa cacheada mientras no cambie uv.lock). uv necesita ver todos los miembros del workspace.
COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/README.md core/
COPY api/pyproject.toml api/CLAUDE.md api/
COPY legacy/streamlit/pyproject.toml legacy/streamlit/
RUN uv sync --frozen --no-dev --package gasolineras-api --no-install-workspace

# 2) Código del motor y de la API, instalados en el entorno (no editables).
COPY core/src core/src
COPY api/src api/src
RUN uv sync --frozen --no-dev --package gasolineras-api --no-editable

FROM python:3.11-slim
RUN useradd --create-home --uid 10001 app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GASOLINERAS_DATA_DIR=/tmp
USER app
WORKDIR /app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn gasolineras_api.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
