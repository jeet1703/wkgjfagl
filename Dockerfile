# Single image: build the React app, then serve it + the API from FastAPI.

# ---- 1. Frontend build ----
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Python runtime ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/scripts ./scripts
# Data snapshot (if committed). If absent, the app fetches from Elexon on first start.
COPY backend/data ./data
COPY --from=web /web/dist ./static
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
# Heroku/Render inject $PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
