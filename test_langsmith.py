#!/usr/bin/env python
"""
Test script to verify LangSmith configuration and run agent with tracing.

Usage:
    python test_langsmith.py
"""

import os
import sys

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Test LangSmith connection
def test_langsmith():
    """Verify LangSmith is configured correctly."""
    print("=" * 60)
    print("Testing LangSmith Configuration")
    print("=" * 60)
    
    api_key = os.getenv("LANGCHAIN_API_KEY")
    project = os.getenv("LANGCHAIN_PROJECT")
    tracing = os.getenv("LANGCHAIN_TRACING")
    
    print(f"API Key: {'✓ Set' if api_key else '✗ Missing'}")
    print(f"Project: {project}")
    print(f"Tracing: {tracing}")
    
    if not api_key:
        print("\n⚠️  LANGCHAIN_API_KEY not set!")
        print("Get your API key at: https://smith.langchain.com/settings")
        return False
    
    try:
        from langsmith import Client
        client = Client()
        project_url = client.get_project_url(project)
        print(f"\n✓ Connected to LangSmith!")
        print(f"  Project URL: {project_url}")
        return True
    except Exception as e:
        print(f"\n✗ LangSmith connection failed: {e}")
        return False


# Test agent execution
def test_agent():
    """Run the agent in mock mode."""
    print("\n" + "=" * 60)
    print("Running Agent in Mock Mode")
    print("=" * 60)
    
    try:
        from src.interfaces.cli import run_mock_mode
        
        # Run with default scenario
        result = run_mock_mode("cctv-psu-output-rail")
        
        print("\n" + "=" * 60)
        print("Agent Execution Complete!")
        print("=" * 60)
        print(f"\n✓ Traces sent to LangSmith!")
        print(f"  View at: https://smith.langchain.com/projects/{os.getenv('LANGCHAIN_PROJECT')}/runs")
        return result
        
    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        return None
    except Exception as e:
        print(f"\n✗ Agent error: {e}")
        return None


if __name__ == "__main__":
    # Test LangSmith first
    if test_langsmith():
        # Run agent if LangSmith is configured
        result = test_agent()
        if result:
            print("\n✓ Success! Check LangSmith for detailed traces.")
        else:
            print("\n⚠️  Agent run failed. Check errors above.")
    else:
        print("\n⚠️  Please configure LangSmith before running the agent.")
        sys.exit(1)
