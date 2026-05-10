#!/bin/bash
# Start the FastAPI backend for development
cd "$(dirname "$0")"
PYTHONPATH=backend uv run uvicorn app.main:app --reload --port 8000
