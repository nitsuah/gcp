FROM node:22-alpine

WORKDIR /app

# Listen on all interfaces inside the container; publish the port to loopback on the host
# and set APP_AUTH_TOKEN (required for a non-loopback bind).
ENV HOST=0.0.0.0

# Copy dependency files first for layer caching
COPY package*.json ./

RUN npm ci --omit=dev

# Copy application source
COPY server.js ./
COPY public/ ./public/
COPY .env ./

# Create data directory for encrypted token store
RUN mkdir -p data

EXPOSE 3000

CMD ["node", "server.js"]
