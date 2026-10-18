# FastAPI backend image. Build context is ./backend (see the root
# docker-compose.yml), so the paths below are relative to backend/.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The slim image ships no HTTP client; curl backs the container healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Dependencies first so editing source does not reinstall the wheels.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# app/ is the service. scripts/, datasets/ and models/ are shipped because the
# maintenance jobs (train_model, evaluate_model_accuracy, seed, and the
# data.gov.in fetchers) are run inside this same image. models/ holds the
# depletion model that app/services/forecasting.py loads from ./models.
COPY app ./app
COPY scripts ./scripts
COPY datasets ./datasets
COPY models ./models
COPY pyproject.toml ./

# Run unprivileged; nothing in the image needs to write inside /app.
# The eRaktKosh scraper derives its output dirs from the package location
# (PROJECT_ROOT = four parents up, which resolves to / in this image) and writes
# to <root>/data/eraktkosh, so those paths must exist and be writable.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /data/eraktkosh /frontend/public/data/eraktkosh \
 && chown -R appuser:appuser /app /data /frontend
USER appuser

EXPOSE 8000

# /health lives under the API prefix (app/api/system.py, mounted at /api/v1).
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
