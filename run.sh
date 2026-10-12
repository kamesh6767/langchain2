#!/usr/bin/env bash
set -e

echo "========================================================"
echo "      Starting DocuMind - Local RAG Assistant"
echo "========================================================"
echo ""

if ! docker info >/dev/null 2>&1; then
    echo "[ERROR] Docker is not running!"
    echo "Please launch Docker and try again."
    exit 1
fi

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
