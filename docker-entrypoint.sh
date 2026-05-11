#!/bin/bash
set -e

# Initialize database if needed
if [ ! -f /app/data/ai_radar.db ]; then
    echo "Initializing database..."
    cd /app && .venv/bin/python -c "import sys; sys.path.insert(0, '/app/src'); from scripts.init_db import main; main()"
fi

# Start FastAPI backend (serves Vue frontend)
echo "Starting FastAPI backend on port 8000..."
cd /app/backend && PYTHONPATH=/app/src uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait for the backend process
wait $!
