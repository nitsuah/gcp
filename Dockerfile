# Multi-stage Dockerfile for gcp-drive-tools

FROM python:3.12-slim-bookworm AS deps
WORKDIR /app

# Install the packaged project so the console script entrypoint is available.
COPY pyproject.toml requirements.txt ./
COPY gcp ./gcp
RUN pip install --no-cache-dir .

FROM python:3.12-slim-bookworm AS app
WORKDIR /app

# Create non-root user
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

# Copy installed packages and console scripts
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Ensure runtime output path exists and is writable by the app user
RUN mkdir -p /app/outputs && chown -R appuser:appgroup /app

USER appuser

ENTRYPOINT ["drive-copy"]
CMD ["--help"]