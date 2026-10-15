@echo off
echo ========================================================
echo       Starting DocuMind - Local RAG Assistant
echo ========================================================
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [NOTICE] Docker Desktop is not running or not found.
    echo Launching DocuMind directly with Python...
    echo.
    python -c "import uvicorn" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python environment is missing dependencies.
        echo Please run: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo Starting server at http://127.0.0.1:8000 ...
    start http://127.0.0.1:8000
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
    pause
    exit /b 0
)

if not exist "data\chroma" mkdir "data\chroma"
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\config" mkdir "data\config"

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
