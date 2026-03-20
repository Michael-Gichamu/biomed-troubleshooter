#!/bin/bash
# =============================================================================
# Biomedical Troubleshooting Agent - Start Script
# =============================================================================
# This script starts LangGraph Studio for the AI agent (port 2024)
# =============================================================================

echo "================================================"
echo "AI Agent Development Environment"
echo "================================================"
echo ""

# Check if virtual environment exists
if [ -f "venv/bin/python" ]; then
    VENV_LANGGRAPH="venv/bin/langgraph"
elif command -v langgraph &> /dev/null; then
    VENV_LANGGRAPH="langgraph"
else
    echo "Error: langgraph not found. Please install LangGraph CLI"
    exit 1
fi

# Function to check if port is in use
check_port() {
    if command -v lsof &> /dev/null; then
        lsof -i:$1 > /dev/null 2>&1
    elif command -v netstat &> /dev/null; then
        netstat -tuln | grep -q ":$1 "
    else
        return 1
    fi
}

# Start LangGraph Studio
echo "Starting LangGraph Studio on port 2024..."

# Check if port 2024 is already in use
if check_port 2024; then
    echo "      Port 2024 already in use - LangGraph Studio may be running"
else
    $VENV_LANGGRAPH dev --port 2024
fi
