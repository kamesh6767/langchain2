#!/usr/bin/env bash
set -e

echo "========================================================"
echo "      Starting DocuMind - Local RAG Assistant"
echo "========================================================"
echo ""

if ! docker info >/dev/null 2>&1; then
    echo "[NOTICE] Docker is not running or not installed."
    echo "Launching DocuMind directly with Python..."
    if ! python3 -c "import uvicorn" >/dev/null 2>&1; then
        echo "[ERROR] Python environment is missing dependencies."
        echo "Please run: pip install -r requirements.txt"
        exit 1
    fi
    echo "Starting server at http://127.0.0.1:8000 ..."
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:8000" &
    elif command -v open >/dev/null 2>&1; then
        open "http://localhost:8000" &
    fi
    python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
    exit 0
fi

mkdir -p data/chroma data/uploads data/config

echo "[1/3] Building and starting Docker container..."
docker compose up -d --build

echo ""
echo "[2/3] Waiting for server initialization..."
sleep 3

echo "[3/3] DocuMind is ready!"
echo "Open your browser at: http://localhost:8000"

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:8000"
elif command -v open >/dev/null 2>&1; then
    open "http://localhost:8000"
fi
