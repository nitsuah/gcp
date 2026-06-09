FROM node:22-alpine

WORKDIR /app

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
