"""
Log Parser - Structured error signal extraction from LLM/API logs.

Provides parsing for error strings and exceptions to extract structured 
error signals such as over capacity, rate limits, and timeouts.
"""

import logging
from typing import Optional
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ErrorContext:
    """Structured error information from runtime exceptions."""
    error_type: str
    message: str
    retryable: bool
    status_code: Optional[int] = None

class LogParser:
    """
    Parses error strings and exceptions to extract structured error signals.
    
    Detects patterns:
    - HTTP 503 (over capacity)
    - Rate limit / quota exceeded
    - Timeout errors
    - Invalid API key
    - Model unavailable
    """
    
    # Error patterns to detect
    ERROR_PATTERNS = {
        "over_capacity": {
            "patterns": ["503", "over capacity", "service unavailable", "server error"],
            "retryable": True,
            "type": "over_capacity"
        },
        "rate_limit": {
            "patterns": ["rate limit", "quota exceeded", "too many requests", "429"],
            "retryable": True,
            "type": "rate_limit"
        },
        "timeout": {
            "patterns": ["timeout", "timed out", "connection timeout", "read timeout"],
            "retryable": True,
            "type": "timeout"
        },
        "invalid_api_key": {
            "patterns": ["invalid api key", "unauthorized", "authentication failed", "401"],
            "retryable": False,
            "type": "invalid_api_key"
        },
        "model_unavailable": {
            "patterns": ["model not found", "model unavailable", "does not exist"],
            "retryable": True,
            "type": "model_unavailable"
        },
        "rate_limit_free_tier": {
            "patterns": ["free tier", "free trial", "daily limit"],
            "retryable": True,
            "type": "rate_limit_free_tier"
        },
        "connection_error": {
            "patterns": ["connection error", "connection refused", "network error"],
            "retryable": True,
            "type": "connection_error"
        },
        "payload_too_large": {
            "patterns": ["413", "payload too large", "request too large"],
            "retryable": True,
            "type": "payload_too_large"
        },
        "tool_call_error": {
            "patterns": ["tool call validation failed", "parameters for tool"],
            "retryable": True,
            "type": "tool_call_error"
        }
    }
    
    @staticmethod
    def parse_error(exception: Exception) -> ErrorContext:
        """
        Parse an exception and return structured error context.
        """
        error_str = str(exception).lower()
        exception_type = type(exception).__name__.lower()
        full_message = f"{exception_type}: {str(exception)}".lower()
        
        # Check each error pattern
        for pattern_key, pattern_info in LogParser.ERROR_PATTERNS.items():
            for pattern in pattern_info["patterns"]:
                if pattern in error_str or pattern in full_message:
                    logger.warning(f"Detected error: {pattern_key} - {str(exception)[:100]}")
                    return ErrorContext(
                        error_type=pattern_info["type"],
                        message=str(exception),
                        retryable=pattern_info["retryable"],
                        status_code=LogParser._extract_status_code(exception)
                    )
        
        # Default: unknown but potentially retryable
        logger.warning(f"Unknown error type: {str(exception)[:100]}")
        return ErrorContext(
            error_type="unknown",
            message=str(exception),
            retryable=True,  # Assume retryable by default
            status_code=LogParser._extract_status_code(exception)
        )
    
    @staticmethod
    def _extract_status_code(exception: Exception) -> Optional[int]:
        """Extract HTTP status code from exception if available."""
        error_str = str(exception)
        
        # Look for status codes in error message
        for code in [500, 503, 502, 504, 429, 401, 403, 404, 400]:
            if f" {code} " in error_str or f"'{code}'" in error_str:
                return code
        
        return None
