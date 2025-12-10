# Use a multi-stage build to reduce the final image size
# ================================
# Stage 1: Dependencies
# ================================
FROM python:3.12-slim-bookworm AS deps
WORKDIR /app

# Copy requirements file first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ================================
# Stage 2: Application
# ================================
FROM python:3.12-slim-bookworm AS app

WORKDIR /app

# Create non-root user
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

# Copy application source code
COPY . .

# Copy dependencies from the previous stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Define environment variable (if needed)
ENV FLASK_APP=main.py  # Or whatever your main application file is

# Health check (basic example - adjust based on your app's health endpoint)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import http.client; conn = http.client.HTTPConnection('localhost', 8000); conn.request('GET', '/'); r1 = conn.getresponse(); exit(0 if r1.status == 200 else 1)"

# Command to run the application
CMD ["python", "main.py"] # Or whatever command starts your app