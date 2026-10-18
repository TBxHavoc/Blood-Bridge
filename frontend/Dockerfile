# Frontend image: Vite bundles the SPA, nginx serves it and proxies /api.
# Build context is ./frontend (see the root docker-compose.yml).

# --- build: typecheck + bundle ----------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Dependencies first so editing source does not reinstall node_modules.
COPY package.json package-lock.json ./
RUN npm ci

# tsconfig.json declares no project references, so this is the whole input.
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

# --- serve: static files + /api reverse proxy -------------------------------
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=5 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
