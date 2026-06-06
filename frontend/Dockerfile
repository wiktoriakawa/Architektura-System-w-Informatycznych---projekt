# ---------------------------------------------------------------------------
# Frontend Dockerfile — multi-stage build (dev + prod z jednego pliku).
#
# Stage `builder`  — instaluje pakiety i buduje produkcyjny bundle przez Vite.
# Stage `dev`      — uruchamia Vite dev server z hot-reload (port 5173).
# Stage `prod`     — serwuje gotowy bundle przez Nginx Alpine na porcie 80.
#
# Wybór stage'a przez docker-compose:
#   docker-compose.dev.yml   → build: { target: dev }
#   docker-compose.prod.yml  → build: { target: prod }
# ---------------------------------------------------------------------------

# === Stage 1: builder — kompilacja Vite ===
FROM node:20-alpine AS builder
WORKDIR /app

# Najpierw same manifesty pakietów — pozwala cache'ować warstwę z npm install,
# jeśli źródła się zmieniają, a zależności nie.
COPY package*.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build


# === Stage 2: dev — Vite dev server z hot-reload ===
FROM node:20-alpine AS dev
WORKDIR /app

# W dev nie chcemy `npm ci` (wymaga package-lock zgodnego z package.json),
# wystarczy `npm install` — wolniejsze, ale tolerancyjne na zmiany w trakcie pracy.
COPY package*.json ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173
# `--host 0.0.0.0` jest niezbędne, żeby dev server był osiągalny spoza kontenera
# (vite domyślnie nasłuchuje tylko na 127.0.0.1).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# === Stage 3: prod — Nginx serwujący statyki ===
FROM nginx:alpine AS prod

# Skopiuj bundle z buildera. Nginx domyślnie serwuje z /usr/share/nginx/html.
COPY --from=builder /app/dist /usr/share/nginx/html

# Lekka konfiguracja nginxa serwującego SPA — fallback wszystkich nieznanych
# ścieżek na index.html (potrzebne dla React Routera, gdyby został dodany).
RUN printf '%s\n' \
    'server {' \
    '    listen 80;' \
    '    server_name localhost;' \
    '    root /usr/share/nginx/html;' \
    '    index index.html;' \
    '    location / {' \
    '        try_files $uri $uri/ /index.html;' \
    '    }' \
    '    location ~* \.(?:js|css|svg|woff2?|ttf|eot|ico|png|jpe?g|gif)$ {' \
    '        expires 7d;' \
    '        add_header Cache-Control "public, no-transform";' \
    '    }' \
    '}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
