@echo off
REM =============================================================================
REM AI Agent - Start Image Server + LangGraph Studio
REM =============================================================================
REM This script starts both:
REM   1. Local HTTP server for test point images (port 8000)
REM   2. LangGraph Studio for the AI agent (port 2024)
REM =============================================================================

echo ================================================
echo AI Agent Development Environment
echo ================================================
echo.

REM Check if virtual environment exists
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
if defined VENV_LANGGRAPH (
    start "LangGraphStudio" cmd /c "%VENV_LANGGRAPH% dev --port 2024"
) else (
    start "LangGraphStudio" cmd /c "langgraph dev --port 2024"
)
timeout /t 3 /nobreak >nul
echo       LangGraph Studio: http://localhost:2024
echo.

echo ================================================
echo Both servers are starting...
echo.
echo Access points:
echo   - Image Server:  http://localhost:8000
echo   - LangGraph Studio: http://localhost:2024
echo.
echo Press any key to exit (servers will continue running)
echo ================================================
pause >nul
