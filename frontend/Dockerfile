# Frontend Next.js — build multi-étapes (#195 ; runtime standalone optimisé #200).
# Contexte de build attendu : racine du repo (cf. docker-compose.yml).
FROM node:20-bookworm-slim AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# NEXT_PUBLIC_* est inliné au build : on l'expose en ARG configurable.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

# --- Runtime minimal (sortie standalone Next, #200) ---
FROM node:20-bookworm-slim AS run
WORKDIR /app
ENV NODE_ENV=production
# server.js (standalone) écoute par défaut sur localhost : forcer 0.0.0.0 pour
# accepter les connexions depuis l'extérieur du conteneur.
ENV HOSTNAME=0.0.0.0 PORT=3000
# Proxy /api/* côté serveur Next vers le backend (surchargé en compose).
ENV BACKEND_URL=http://backend:8000

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
