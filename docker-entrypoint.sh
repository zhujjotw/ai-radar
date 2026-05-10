#!/bin/bash
set -e

# Initialize database if needed
if [ ! -f /app/data/ai_radar.db ]; then
    echo "Initializing database..."
    cd /app && uv run python scripts/init_db.py
fi

# Start FastAPI backend
echo "Starting FastAPI backend on port 8000..."
cd /app && PYTHONPATH=backend uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start Streamlit frontend
echo "Starting Streamlit frontend on port 8501..."
cd /app && uv run streamlit run src/app.py --server.headless true --server.port 8501 --server.address 0.0.0.0 &
STREAMLIT_PID=$!

# Wait for any process to exit
wait -n $BACKEND_PID $STREAMLIT_PID

# Exit with status of process that exited first
exit $?
