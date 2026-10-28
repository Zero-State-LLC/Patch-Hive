# Multi-stage build for optimized Python backend
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only (postgresql-client optional for ops shells)
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/patchhive/.local

# Copy application code
COPY . .

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin patchhive \
    && chmod +x /app/docker-entrypoint.sh 2>/dev/null || true \
    && chown -R patchhive:patchhive /app /home/patchhive

# Add .local/bin to PATH
ENV PATH=/home/patchhive/.local/bin:$PATH
ENV HOME=/home/patchhive

# Set Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check (DB readiness)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

USER patchhive

# Wait for the DB then run uvicorn. Startup migrations are opt-in (RUN_MIGRATIONS=true);
# deployed databases are migrated by the db-migrate workflow.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
