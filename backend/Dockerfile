# Build stage
FROM python:3.11-slim AS builder

# Set the working directory in the container
WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install requirements
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy source code
COPY --chown=appuser:appuser api ./api
COPY --chown=appuser:appuser agent ./agent
COPY --chown=appuser:appuser services ./services
COPY --chown=appuser:appuser utils ./utils
COPY --chown=appuser:appuser tools ./tools
COPY --chown=appuser:appuser config ./config

# Switch to non-root user
USER appuser

# Environment variables for configuration
ENV PORT=8000
ENV WORKERS=1
ENV HOST=0.0.0.0

# Expose port
EXPOSE ${PORT}

# Command to run the application
CMD ["sh", "-c", "uvicorn api.lead_generation_api:create_app --host ${HOST} --port ${PORT} --workers ${WORKERS}"] 