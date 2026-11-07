# MatatuPulse: one container serving the React app and the Django API on $PORT (default 8080).

# --- 1. Build the React app -------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same origin as the API, so no VITE_API_URL: the app calls /api/...
RUN npm run build

# --- 2. Django + the built app ---------------------------------------------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    FRONTEND_DIST=/app/frontend_dist
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=frontend /frontend/dist /app/frontend_dist
# collectstatic only needs throwaway values at build time
RUN DEBUG=false SECRET_KEY=build-only ALLOWED_HOSTS=localhost python manage.py collectstatic --noinput

RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8080
CMD ["./start.sh"]
