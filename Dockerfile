FROM node:22-slim AS frontend-build
WORKDIR /frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
COPY vite.config.js ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY alembic.ini ./
COPY --from=frontend-build /frontend/dist ./dist
RUN useradd --create-home --uid 10001 kotoba && chown -R kotoba:kotoba /app
USER kotoba
EXPOSE 8000
CMD ["sh", "-c", ".venv/bin/alembic upgrade head && exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
