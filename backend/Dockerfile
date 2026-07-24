# Backend headless (FastAPI + moteur de palettisation). Déployable indépendamment du frontend.
FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv==0.11.32

WORKDIR /app

# Étape séparée pour profiter du cache Docker sur les dépendances (change moins souvent que le code).
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}" \
    APP_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "palletizer.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
