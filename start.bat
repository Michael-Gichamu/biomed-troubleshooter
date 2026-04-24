@echo off
REM =============================================================================
REM Biomedical Troubleshooting Agent - Start Script
REM =============================================================================
REM This script brings up the full local dev stack, in order:
REM   1. Starts the local Postgres container (docker-compose, service: db).
REM   2. Waits for Postgres to become healthy (pg_isready).
REM   3. Seeds the equipment catalogue from data/equipment/*.yaml (idempotent).
REM   4. Starts LangGraph Studio on port 2024.
REM
REM The equipment store backend (YAML vs Postgres) is controlled by
REM EQUIPMENT_STORE in .env — this script doesn't care which one is set,
REM it just ensures the DB is available so either path works.
REM =============================================================================

setlocal

echo ================================================
echo AI Agent Development Environment
echo ================================================
echo.

REM ---------------------------------------------------------------------------
REM [1/4] Start local Postgres via docker-compose.
REM ---------------------------------------------------------------------------
echo [1/4] Starting local Postgres (docker compose up -d db)...
docker compose up -d db
if errorlevel 1 (
    echo.
    echo ERROR: docker compose failed. Is Docker Desktop running?
    echo        Open Docker Desktop, wait until the whale icon says "running",
    echo        then re-run start.bat.
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM [2/4] Wait for Postgres to accept connections. Up to ~60 s.
REM ---------------------------------------------------------------------------
echo [2/4] Waiting for Postgres health check...
set /a RETRIES=0
:waitpg
docker exec biomed-postgres pg_isready -U biomed -d biomed >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    if %RETRIES% GEQ 30 (
        echo ERROR: Postgres did not become healthy within 60s.
        echo        Check logs: docker compose logs db
        exit /b 1
    )
    timeout /t 2 /nobreak >nul
    goto waitpg
)
echo       Postgres is ready.

REM ---------------------------------------------------------------------------
REM [3/4] Seed / upsert the equipment catalogue (idempotent, safe on restart).
REM ---------------------------------------------------------------------------
echo [3/4] Seeding equipment catalogue from YAML...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\seed_equipment.py
) else (
    python scripts\seed_equipment.py
)
if errorlevel 1 (
    echo WARNING: seed_equipment.py failed. The agent will still start, but the
    echo          Postgres backend may fall back to YAML on a cache miss.
)

REM ---------------------------------------------------------------------------
REM [4/4] Start LangGraph Studio.
REM ---------------------------------------------------------------------------
echo [4/4] Starting LangGraph Studio on port 2024...
if exist "venv\Scripts\langgraph.exe" (
    echo       Using virtual environment...
    venv\Scripts\langgraph.exe dev --port 2024
) else (
    echo       Using system Python...
    langgraph dev --port 2024
)

endlocal
