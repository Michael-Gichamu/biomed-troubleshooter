@echo off
REM =============================================================================
REM Biomedical Troubleshooting Agent - Start Both Servers
REM =============================================================================
REM This script starts:
REM   1. Local HTTP server for test point images (port 8000)
REM   2. LangGraph Studio for the AI agent (port 2024)
REM =============================================================================

echo ================================================
echo AI Agent Development Environment
echo ================================================
echo.

REM Check if venv exists
set "VENV_LANGGRAPH="
set "VENV_PYTHON="
if exist "venv\Scripts\langgraph.exe" set "VENV_LANGGRAPH=venv\Scripts\langgraph.exe"
if exist "venv\Scripts\python.exe" set "VENV_PYTHON=venv\Scripts\python.exe"

REM Start Image Server in background
echo [1/2] Starting local image server on port 8000...
if defined VENV_PYTHON (
    start "ImageServer" cmd /c "%VENV_PYTHON% -m http.server 8000 --directory data\equipment"
) else (
    start "ImageServer" cmd /c "python -m http.server 8000 --directory data\equipment"
)
timeout /t 2 /nobreak >nul
echo       Image server started: http://localhost:8000
echo.

REM Start LangGraph Studio
echo [2/2] Starting LangGraph Studio on port 2024...
if exist "venv\Scripts\langgraph.exe" (
    echo Using virtual environment...
    venv\Scripts\langgraph.exe dev --port 2024
) else (
    echo Using system Python...
    langgraph dev --port 2024
)
