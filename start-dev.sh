#!/bin/bash
# =============================================================================
# AI Agent - Start Image Server + LangGraph Studio
# =============================================================================
# This script starts both:
#   1. Local HTTP server for test point images (port 8000)
#   2. LangGraph Studio for the AI agent (port 2024)
# =============================================================================

echo "================================================"
echo "AI Agent Development Environment"
echo "================================================"
echo ""

# Check if virtual environment exists
if [ -f "venv/bin/python" ]; then
    VENV_PYTHON="venv/bin/python"
    VENV_LANGGRAPH="venv/bin/langgraph"
elif command -v python &> /dev/null; then
    VENV_PYTHON="python"
    VENV_LANGGRAPH="langgraph"
else
    echo "Error: Python not found. Please install Python 3.10+"
    exit 1
fi

# Function to check if port is in use
check_port() {
    if command -v lsof &> /dev/null; then
        lsof -i:$1 > /dev/null 2>&1
    elif command -v netstat &> /dev/null; then
        netstat -tuln | grep -q ":$1 "
    else
        # If we can't check, assume it's OK
        return 1
    fi
}

# Start Image Server in background
echo "[1/2] Starting local image server on port 8000..."

# Check if port 8000 is already in use
if check_port 8000; then
    echo "      Port 8000 already in use - skipping image server"
else
    $VENV_PYTHON -m http.server 8000 --directory data/equipment > /dev/null 2>&1 &
    IMAGE_PID=$!
    echo "      Image server started (PID: $IMAGE_PID): http://localhost:8000"
fi
echo ""

# Wait a moment for the image server to start
sleep 2

# Start LangGraph Studio in background
echo "[2/2] Starting LangGraph Studio on port 2024..."

# Check if port 2024 is already in use
if check_port 2024; then
    echo "      Port 2024 already in use - LangGraph Studio may be running"
else
    $VENV_LANGGRAPH dev --port 2024 > /dev/null 2>&1 &
    LANGGRAPH_PID=$!
    echo "      LangGraph Studio started (PID: $LANGGRAPH_PID): http://localhost:2024"
fi

echo ""
echo "================================================"
echo "Both servers are starting..."
echo ""
echo "Access points:"
echo "  - Image Server:       http://localhost:8000"
echo "  - LangGraph Studio:  http://localhost:2024"
echo ""
echo "Press Ctrl+C to stop all servers"
echo "================================================"

# Wait for user interrupt
trap 'echo ""; echo "Stopping servers..."; kill $IMAGE_PID $LANGGRAPH_PID 2>/dev/null; exit 0' INT TERM

# Keep script running
wait
