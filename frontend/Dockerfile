# Frontend Next.js — client HTTP pur du backend Python (aucun calcul côté serveur/navigateur).
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Doit être joignable depuis le NAVIGATEUR de l'utilisateur final, pas seulement depuis ce
# conteneur — voir docker-compose.yml et le README racine pour l'explication de ce piège classique.
ARG NEXT_PUBLIC_PALLETIZER_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_JOB_POLL_INTERVAL_MS=2000
ARG NEXT_PUBLIC_API_REQUEST_TIMEOUT_MS=15000
ENV NEXT_PUBLIC_PALLETIZER_API_URL=${NEXT_PUBLIC_PALLETIZER_API_URL} \
    NEXT_PUBLIC_JOB_POLL_INTERVAL_MS=${NEXT_PUBLIC_JOB_POLL_INTERVAL_MS} \
    NEXT_PUBLIC_API_REQUEST_TIMEOUT_MS=${NEXT_PUBLIC_API_REQUEST_TIMEOUT_MS}
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
