@echo off
echo ========================================================
echo       DocuMind - Local RAG Assistant (Python Mode)
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    pause
    exit /b 1
)

python -c "import uvicorn, fastapi, langchain" >nul 2>&1
if %errorlevel% neq 0 (
    echo [NOTICE] Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo [1/2] Waiting 2 seconds then opening browser...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000

echo [2/2] Starting DocuMind FastAPI server on http://127.0.0.1:8000 ...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause
