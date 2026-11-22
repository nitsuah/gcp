FROM node:22-alpine

WORKDIR /app

# Listen on all interfaces inside the container; publish the port to loopback on the host
# and set APP_AUTH_TOKEN (required for a non-loopback bind).
ENV HOST=0.0.0.0

# Copy dependency files first for layer caching
COPY package*.json ./

RUN npm ci --omit=dev

# Runtime configuration (not baked into the image): pass ENCRYPTION_KEY (required), the OAuth
# client settings and any other variables from apps/.env.example with `docker run --env-file .env`.

# Copy application source (configuration is supplied at runtime via environment variables)
COPY server.js ./
COPY public/ ./public/

# Create data directory for encrypted token store
RUN mkdir -p data

EXPOSE 3000

CMD ["node", "server.js"]
