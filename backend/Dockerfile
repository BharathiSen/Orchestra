# syntax=docker/dockerfile:1

# --- build stage -------------------------------------------------------------
# Compilers and headers live here and never reach the runtime image. Everything
# is installed into a virtualenv so the result is a single directory to copy.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- runtime stage -----------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# libpq5 is the runtime half of libpq-dev; curl backs the healthcheck below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# A fixed uid/gid keeps ownership predictable when a host volume is mounted.
RUN groupadd --gid 1001 orchestra \
    && useradd --uid 1001 --gid 1001 --create-home --shell /usr/sbin/nologin orchestra

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=orchestra:orchestra . .

# Uploads are written at runtime, so the directory must exist and be owned by
# the unprivileged user before the process drops into it.
RUN mkdir -p /app/uploads && chown -R orchestra:orchestra /app/uploads

USER orchestra

EXPOSE 8000

# Liveness only. Readiness depends on Postgres and Redis, which the container
# runtime should not restart this process over — the orchestrator polls
# /health/ready separately to decide about routing traffic.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
