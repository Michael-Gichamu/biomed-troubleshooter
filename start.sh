#!/bin/bash
# =============================================================================
# Biomedical Troubleshooting Agent - Start LangGraph Studio
# =============================================================================
# Simply run: ./start.sh
# =============================================================================

echo "Starting LangGraph Studio..."
echo ""

# Check if venv exists
if [ -f "venv/bin/langgraph" ]; then
    echo "Using virtual environment..."
    venv/bin/langgraph dev --port 2024
elif command -v langgraph &> /dev/null; then
    echo "Using system Python..."
    langgraph dev --port 2024
else
    echo "Error: langgraph not found. Run: pip install langgraph"
    exit 1
fi
