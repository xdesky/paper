FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
RUN npm install -g pnpm@11.25.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN node node_modules/typescript/bin/tsc -b && node node_modules/vite/bin/vite.js build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/ backend/
COPY papercraft-v1.2/ papercraft-v1.2/
COPY --from=frontend /app/frontend/dist frontend/dist/
ENV PPM_DATA_DIR=/app/data MPLCONFIGDIR=/app/data/.mpl-cache
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
