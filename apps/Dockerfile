FROM node:22-alpine

WORKDIR /app

# Copy dependency files first for layer caching
COPY package*.json ./

RUN npm ci --omit=dev

# Copy application source (configuration is supplied at runtime via environment variables)
COPY server.js ./
COPY public/ ./public/

# Create data directory for encrypted token store
RUN mkdir -p data

EXPOSE 3000

CMD ["node", "server.js"]
