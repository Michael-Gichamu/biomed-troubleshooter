"""
LLM Client - Backwards Compatibility Module

This module re-exports all LLM functionality from llm_manager.py.
The LLMClient class and all utilities have been merged into llm_manager.py
for better code organization.

This file is kept for backwards compatibility with existing imports.
"""

# Re-export everything from llm_manager for backwards compatibility
from src.infrastructure.llm_manager import (
    LLMManager,
    LLMClient,
    LLMConfig,
    LogParser,
    ErrorContext,
    get_llm_manager,
    get_active_llm,
    invoke_with_retry,
    get_llm,
    create_llm_client,
)

# Backwards compatibility: get_llm was previously exported from here
__all__ = [
    "LLMManager",
    "LLMClient", 
    "LLMConfig",
    "LogParser",
    "ErrorContext",
    "get_llm_manager",
    "get_active_llm",
    "invoke_with_retry",
    "get_llm",
    "create_llm_client",
]
