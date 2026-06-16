# ---------------------------------------------------------------------------
# Containerfile - Thoughts Dashboard Flask App
# ---------------------------------------------------------------------------

# ---- build stage: install dependencies into a clean prefix ----------------
FROM python:3.9-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage --------------------------------------------------------
FROM python:3.9-slim

# Non-root user for security
RUN useradd --uid 1001 --no-create-home --shell /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app.py .

# Runtime environment defaults (all overridable at run-time)
ENV DB_HOST=postgresql.thoughts-app.svc.cluster.local \
    DB_NAME=thoughts \
    DB_USER=thoughts \
    DB_PASSWORD=thoughts123 \
    DB_PORT=5432 \
    PORT=8080

USER 1001

EXPOSE 8080

CMD ["python", "app.py"]
