@echo off
REM =============================================================================
REM Biomedical Troubleshooting Agent - Start Script
REM =============================================================================
REM This script starts LangGraph Studio for the AI agent (port 2024)
REM =============================================================================

echo ================================================
echo AI Agent Development Environment
echo ================================================
echo.

REM Check if venv exists
set "VENV_LANGGRAPH="
if exist "venv\Scripts\langgraph.exe" set "VENV_LANGGRAPH=venv\Scripts\langgraph.exe"

REM Start LangGraph Studio
echo Starting LangGraph Studio on port 2024...
if exist "venv\Scripts\langgraph.exe" (
    echo Using virtual environment...
    venv\Scripts\langgraph.exe dev --port 2024
) else (
    echo Using system Python...
    langgraph dev --port 2024
)
