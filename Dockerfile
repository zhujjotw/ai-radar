# Stage 1: Build Vue frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY backend/ ./backend/
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY index.html ./

# Copy built Vue frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose ports
# 8000: FastAPI backend
# 8501: Streamlit frontend
EXPOSE 8000 8501

# Default environment variables
ENV PYTHONPATH=/app/backend
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Start script
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
