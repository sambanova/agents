FROM python:3.11-slim-bookworm AS dependencies

# Install system dependencies for uv and weasyprint
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libglib2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Copy ONLY dependency files (not source code yet)
COPY pyproject.toml uv.lock* ./

# Install all dependencies (external + project)
RUN /root/.local/bin/uv sync --no-dev --no-install-project

FROM python:3.11-slim-bookworm

# Install runtime dependencies for weasyprint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the large venv from dependencies stage (CACHED LAYER - 275MB)
COPY --from=dependencies /app/.venv ./.venv

# Copy UV binary (CACHED LAYER - 36MB) 
COPY --from=dependencies /root/.local/bin/uv /usr/local/bin/uv

# Copy project config (needed for local package install)
COPY pyproject.toml ./

# Copy source code LAST (SMALL LAYER - only ~360KB - rebuilds on code changes)
COPY src/ ./src/

# Install the local package into the existing venv (TINY operation)
RUN /usr/local/bin/uv pip install --no-deps -e .

# Clean up
RUN find /app/src -name "*.pyc" -delete \
    && find /app/src -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && rm -rf /app/src/*.egg-info 2>/dev/null || true

# Set PATH to use the venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8000
EXPOSE ${PORT}

ENTRYPOINT ["sh", "-c", "uvicorn src.agents.api.main:app --host 0.0.0.0 --port $PORT --no-access-log"]
