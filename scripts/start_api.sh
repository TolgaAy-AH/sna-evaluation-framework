#!/bin/bash

# Start the evaluation framework API service
# This allows other applications to send evaluation requests

set -e

# Change to script directory
cd "$(dirname "$0")/.."

echo "🚀 Starting SNA Evaluation Framework API"
echo "========================================"
echo ""
echo "📍 Service will run on: http://localhost:8000"
echo "📖 API docs available at: http://localhost:8000/docs"
echo ""

# Activate virtual environment
if [ -f ".venv-eval/bin/activate" ]; then
    source .venv-eval/bin/activate
else
    echo "❌ Error: Virtual environment not found at .venv-eval/"
    echo "   Please run: python3.10 -m venv .venv-eval && source .venv-eval/bin/activate && pip install -e ."
    exit 1
fi

# Load environment variables
if [ -f ".env" ]; then
    echo "✅ Loading environment from .env"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  Warning: .env file not found"
    echo "   Create one from .env.template if you need Azure credentials"
fi

echo ""
echo "Starting API server..."
echo ""

# Start the FastAPI application with the virtual environment's Python
.venv-eval/bin/python -m uvicorn eval.api:app --host 0.0.0.0 --port 8000 --reload
