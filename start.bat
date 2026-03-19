@echo off
REM =============================================================================
REM Biomedical Troubleshooting Agent - Start LangGraph Studio
REM =============================================================================
REM Simply run this file to start the agent!
REM =============================================================================

echo Starting LangGraph Studio...
echo.

REM Check if venv exists
if exist "venv\Scripts\langgraph.exe" (
    echo Using virtual environment...
    venv\Scripts\langgraph.exe dev --port 2024
) else (
    echo Using system Python...
    langgraph dev --port 2024
)
