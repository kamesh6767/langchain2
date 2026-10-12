@echo off
echo ========================================================
echo       Starting DocuMind - Local RAG Assistant
echo ========================================================
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and run this script again.
    pause
    exit /b 1
)

echo [1/3] Building and starting Docker container...
docker compose up -d --build

if %errorlevel% neq 0 (
    echo [ERROR] Failed to launch DocuMind container.
    pause
    exit /b 1
)

echo.
echo [2/3] Waiting for server initialization...
timeout /t 3 /nobreak >nul

echo [3/3] Opening browser at http://localhost:8000 ...
start http://localhost:8000

echo.
echo ========================================================
echo  DocuMind is running at http://localhost:8000
echo  To stop: run 'docker compose down' in this folder.
echo ========================================================
echo.
pause
