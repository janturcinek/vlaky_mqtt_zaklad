# ── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Build deps (needed for scipy wheels on some platforms)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Persistent data directories (mounted as volumes)
RUN mkdir -p db data_storage

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
