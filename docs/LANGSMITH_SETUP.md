# LangSmith Studio Setup Guide

This guide explains how to view your agent's execution traces in LangSmith Studio.

## Prerequisites

1. **LangSmith Account**: Sign up at https://smith.langchain.com
2. **API Key**: Get your API key from https://smith.langchain.com/settings
3. **Python Dependencies**: Install with `pip install -r requirements.txt`

## Setup Steps

### 1. Configure Environment Variables

Your `.env` file should have these settings:

```env
# LangSmith Observability
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=biomed-troubleshooter
LANGCHAIN_TRACING=true
```

**Current configuration detected:**
- Project: `biomed-troubleshooter`
- API Key: Already configured in `.env`

### 2. Verify LangSmith Connection

Run this test to verify LangSmith is configured correctly:

```python
from langsmith import Client

client = Client()
print(f"LangSmith Project: {client.get_project_url('biomed-troubleshooter')}")
```

### 3. Run Agent with Tracing

```bash
# Run in mock mode (generates traces)
python -m src.interfaces.cli --mock

# Or run specific scenario
python -m src.interfaces.cli --mock cctv-psu-overvoltage
```

### 4. View Traces in LangSmith Studio

1. Go to https://smith.langchain.com
2. Sign in with your account
3. Select project: `biomed-troubleshooter`
4. You'll see all agent executions with:
   - Node-by-node execution flow
   - Input/output of each LangGraph node
   - Timing and performance metrics
   - Reasoning chains and decisions

## What LangSmith Shows

| Component | Description |
|-----------|-------------|
| **Graph Visualization** | See how signals flow through the agent |
| **Node Execution** | Each LangGraph node (validate, interpret, analyze, recommend) |
| **State Changes** | How the agent state evolves |
| **LLM Calls** | Prompts sent to Groq/OpenAI and responses |
| **Errors** | Any exceptions during execution |

## Debugging with LangSmith

1. **Select a trace** from the runs list
2. **Click on a node** to see inputs/outputs
3. **Check timing** to identify bottlenecks
4. **View LLM prompts** to verify reasoning quality

## Project Structure for LangSmith

```
biomed-troubleshooter/
├── src/
│   ├── application/
│   │   └── agent.py          # Main LangGraph workflow
│   ├── domain/
│   │   └── models.py         # Data models
│   └── infrastructure/
│       └── rag_repository.py  # Knowledge base queries
├── data/
│   └── mock_signals/         # Test scenarios
└── docs/
    └── LANGSMITH_SETUP.md   # This file
```

## Common Issues

| Issue | Solution |
|-------|----------|
| No traces appearing | Check `LANGCHAIN_TRACING=true` in `.env` |
| API key error | Verify key at https://smith.langchain.com/settings |
| Wrong project | Set `LANGCHAIN_PROJECT=biomed-troubleshooter` |
| Missing nodes | Ensure all LangGraph nodes are properly defined |

## Best Practices

1. **Use descriptive session IDs** for debugging
2. **Tag runs** with scenario names for filtering
3. **Review traces** after each agent run
4. **Share traces** with team members for collaboration

## Next Steps

After viewing traces in LangSmith:

1. **Optimize slow nodes** based on timing data
2. **Improve prompts** based on LLM call analysis
3. **Add checkpoints** for complex state transitions
4. **Share insights** with your team via LangSmith sharing
