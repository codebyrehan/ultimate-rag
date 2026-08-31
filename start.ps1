@echo off
setlocal enabledelayedexpansion

echo === Ultimate RAG Platform - One-Command Startup ===

REM 1. Check prerequisites
echo Checking prerequisites...
where docker >nul 2>&1
if errorlevel 1 (
    echo ERROR: docker not found
    exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERROR: docker compose not found
    exit /b 1
)
echo [OK] Prerequisites OK

REM 2. Create .env if needed
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env >nul
    echo [OK] .env created (edit it to customize)
)

REM 3. Start services
echo Starting Docker Compose...
docker compose up -d

REM 4. Wait for backend
echo Waiting for services to be ready...
set ATTEMPTS=0
:waitloop
set /a ATTEMPTS+=1
if !ATTEMPTS! GTR 60 (
    echo   Backend did not become ready in 3 minutes
    goto :summary
)
curl -sf http://localhost:8000/health >nul 2>&1
if not errorlevel 1 (
    echo [OK] Backend ready
    goto :migrations
)
echo   Waiting... (!ATTEMPTS!/60)
timeout /t 3 /nobreak >nul
goto :waitloop

:migrations
REM 5. Run migrations
echo Running database migrations...
docker compose exec -T api python -m alembic upgrade head 2>nul
if errorlevel 1 (
    echo   (migrations skipped)
)

REM 6. Pull Ollama model
echo Pre-pulling Ollama model...
docker compose exec -T ollama ollama pull qwen3:4b 2>nul
if errorlevel 1 (
    echo   (Ollama model pull deferred - can be done later)
)

:summary
echo.
echo === Startup Summary ===
curl -sf http://localhost:8000/health 2>nul | python -m json.tool 2>nul

echo.
echo Frontend:  http://localhost:3000
echo Backend:   http://localhost:8000
echo Docs:      http://localhost:8000/docs
echo Health:    http://localhost:8000/health
echo Metrics:   http://localhost:8000/metrics
echo.
echo [OK] Ultimate RAG Platform is running.

endlocal
