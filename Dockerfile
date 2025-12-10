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
COPY copy_folder.py .

# Copy dependencies from the previous stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Command to run the Google Drive copy utility
CMD ["python", "copy_folder.py"]