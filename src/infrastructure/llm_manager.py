"""
LLM Manager - Self-Healing AI Infrastructure

This module provides automatic API key and model rotation for resilience
against rate limits, 503 errors, and other API failures.

Features:
- Multiple API keys support (rotates on failure)
- Multiple models support (fallback strategy)
- Exponential backoff retry logic
- Comprehensive error detection
- Full logging of rotation events
- LLMClient for diagnostic reasoning with self-healing
"""

import os
import time
import json
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
        }
    }
    
    @staticmethod
    def parse_error(exception: Exception) -> ErrorContext:
        """
        Parse an exception and return structured error context.
        
        Args:
            exception: Any exception from LLM/API calls
            
        Returns:
            ErrorContext with type, message, and retryable flag
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


class LLMManager:
    """
    Core brain of LLM switching.
    
    Responsibilities:
    - Load ALL API keys from .env
    - Load ALL models from .env
    - Maintain active indices
    - Rotate on failure with exponential backoff
    """
    
    _instance: Optional['LLMManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not LLMManager._initialized:
            self._load_config()
            self._initialize_llm()
            LLMManager._initialized = True
    
    def _load_config(self):
        """Load API keys and models from environment variables."""
        # Load multiple API keys (comma-separated)
        api_keys_str = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
        self.api_keys: List[str] = [k.strip() for k in api_keys_str.split(",") if k.strip()]
        
        if not self.api_keys:
            raise ValueError("No Groq API keys found in GROQ_API_KEYS or GROQ_API_KEY")
        
        # Load multiple models (comma-separated)
        models_str = os.getenv("LLM_MODELS", "llama-3.3-70b-versatile")
        self.models: List[str] = [m.strip() for m in models_str.split(",") if m.strip()]
        
        if not self.models:
            raise ValueError("No models found in LLM_MODELS")
        
        # Configuration
        self.max_retries_per_key = int(os.getenv("MAX_RETRIES_PER_KEY", "2"))
        self.max_retries_per_model = int(os.getenv("MAX_RETRIES_PER_MODEL", "2"))
        self.base_backoff = float(os.getenv("BACKOFF_BASE_SECONDS", "1.0"))
        self.max_backoff = float(os.getenv("BACKOFF_MAX_SECONDS", "16.0"))
        
        # State tracking
        self.current_key_index = 0
        self.current_model_index = 0
        self.key_retry_count = 0
        self.model_retry_count = 0
        
        # Current active LLM
        self._current_llm: Optional[Any] = None
        
        logger.info(f"LLMManager initialized with {len(self.api_keys)} keys, {len(self.models)} models")
        logger.info(f"Models: {self.models}")
    
    def _initialize_llm(self):
        """Initialize the LLM with current key and model."""
        api_key = self.api_keys[self.current_key_index]
        model = self.models[self.current_model_index]
        
        # Determine provider from model name
        if model.startswith("gpt-") or model.startswith("openai/"):
            # OpenAI model
            provider = "openai"
            model_name = model.replace("openai/", "")
            self._current_llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                temperature=0.0,
                max_tokens=2048,
                timeout=60
            )
        else:
            # Default to Groq
            provider = "groq"
            self._current_llm = ChatGroq(
                model=model,
                api_key=api_key,
                temperature=0.0,
                max_tokens=2048,
                timeout=60
            )
        
        logger.info(f"Active LLM: provider={provider}, model={model}, key_index={self.current_key_index}")
    
    @property
    def current_llm(self) -> Any:
        """Get the current active LLM instance."""
        if self._current_llm is None:
            self._initialize_llm()
        return self._current_llm
    
    @property
    def active_model(self) -> str:
        """Get the name of the currently active model."""
        return self.models[self.current_model_index]
    
    @property
    def active_key_index(self) -> int:
        """Get the index of the currently active API key."""
        return self.current_key_index
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get current manager status."""
        return {
            "active_model": self.active_model,
            "active_key_index": self.active_key_index,
            "total_keys": len(self.api_keys),
            "total_models": len(self.models),
            "key_retry_count": self.key_retry_count,
            "model_retry_count": self.model_retry_count
        }
    
    def should_rotate(self, exception: Exception) -> bool:
        """
        Determine if we should rotate to a different key/model based on the error.
        
        Args:
            exception: The exception from the failed LLM call
            
        Returns:
            True if rotation is recommended
        """
        error_context = LogParser.parse_error(exception)
        
        # Don't rotate for non-retryable errors
        if not error_context.retryable:
            logger.warning(f"Non-retryable error: {error_context.error_type}")
            return False
        
        # Check retry counts
        if self.key_retry_count >= self.max_retries_per_key:
            logger.warning(f"Key retry limit reached ({self.max_retries_per_key})")
            return True
        
        if self.model_retry_count >= self.max_retries_per_model:
            logger.warning(f"Model retry limit reached ({self.max_retries_per_model})")
            return True
        
        return True
    
    def rotate(self) -> bool:
        """
        Rotate to next API key or model.
        
        Returns:
            True if rotation was successful, False if no more options
        """
        # First, try switching to next API key
        if self.current_key_index < len(self.api_keys) - 1:
            self.current_key_index += 1
            self.key_retry_count = 0
            logger.info(f"Rotating to API key index: {self.current_key_index}")
            self._initialize_llm()
            return True
        
        # If all keys exhausted, try switching to next model
        if self.current_model_index < len(self.models) - 1:
            self.current_model_index += 1
            self.current_key_index = 0  # Reset to first key
            self.model_retry_count = 0
            self.key_retry_count = 0
            logger.info(f"Rotating to model: {self.models[self.current_model_index]}")
            self._initialize_llm()
            return True
        
        # No more options
        logger.error("All API keys and models exhausted!")
        return False
    
    def increment_retry(self):
        """Increment retry count for current key."""
        self.key_retry_count += 1
        logger.info(f"Key retry count: {self.key_retry_count}/{self.max_retries_per_key}")
    
    def increment_model_retry(self):
        """Increment retry count for current model."""
        self.model_retry_count += 1
        logger.info(f"Model retry count: {self.model_retry_count}/{self.max_retries_per_model}")
    
    def get_backoff_time(self) -> float:
        """Calculate exponential backoff time."""
        # Exponential backoff: 1s, 2s, 4s, 8s, 16s...
        backoff = self.base_backoff * (2 ** self.key_retry_count)
        return min(backoff, self.max_backoff)
    
    def reset(self):
        """Reset to initial state (first key, first model)."""
        self.current_key_index = 0
        self.current_model_index = 0
        self.key_retry_count = 0
        self.model_retry_count = 0
        self._initialize_llm()
        logger.info("LLMManager reset to initial state")


# Convenience function for getting the active LLM
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get the singleton LLMManager instance."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager


def get_active_llm() -> Any:
    """Get the current active LLM instance."""
    return get_llm_manager().current_llm


def invoke_with_retry(messages: List[Dict[str, str]], max_full_retries: int = 3) -> Any:
    """
    Invoke LLM with automatic retry and rotation logic.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        max_full_retries: Maximum full rotation cycles
        
    Returns:
        LLM response
        
    Raises:
        Exception: If all retries exhausted
    """
    manager = get_llm_manager()
    
    for full_retry in range(max_full_retries):
        llm = manager.current_llm
        
        try:
            response = llm.invoke(messages)
            return response
        
        except Exception as e:
            logger.warning(f"LLM call failed: {str(e)[:100]}")
            
            if manager.should_rotate(e):
                # Calculate backoff
                backoff_time = manager.get_backoff_time()
                logger.info(f"Retrying after {backoff_time}s...")
                time.sleep(backoff_time)
                
                # Try to rotate
                if manager.rotate():
                    manager.increment_retry()
                    continue
                else:
                    # Try next model if available
                    if manager.current_model_index < len(manager.models) - 1:
                        manager.increment_model_retry()
                        manager.rotate()
                        continue
            
            # If we get here, all options exhausted
            logger.error(f"All retries exhausted after {full_retry + 1} attempts")
            raise


def invoke_with_tools_and_retry(messages: List[Any], tools: List[Any], max_full_retries: int = 3) -> Any:
    """
    Invoke LLM with tools bound and automatic retry/rotation logic.
    
    This function handles RateLimitError, APIError, and other errors by:
    1. Retrying with exponential backoff
    2. Rotating to next API key if available
    3. Rotating to next model if all keys exhausted
    
    Args:
        messages: List of message objects (SystemMessage, HumanMessage, etc.)
        tools: List of LangChain tools to bind to the LLM
        max_full_retries: Maximum full rotation cycles
        
    Returns:
        LLM response with tool calls
        
    Raises:
        Exception: If all retries exhausted
    """
    manager = get_llm_manager()
    
    for full_retry in range(max_full_retries):
        llm = manager.current_llm
        
        try:
            # Bind tools to the LLM
            llm_with_tools = llm.bind_tools(tools)
            response = llm_with_tools.invoke(messages)
            return response
        
        except Exception as e:
            logger.warning(f"LLM call with tools failed: {str(e)[:100]}")
            
            if manager.should_rotate(e):
                # Calculate backoff
                backoff_time = manager.get_backoff_time()
                logger.info(f"Retrying after {backoff_time}s...")
                time.sleep(backoff_time)
                
                # Try to rotate
                if manager.rotate():
                    manager.increment_retry()
                    continue
                else:
                    # Try next model if available
                    if manager.current_model_index < len(manager.models) - 1:
                        manager.increment_model_retry()
                        manager.rotate()
                        continue
            
            # If we get here, all options exhausted
            logger.error(f"All retries exhausted after {full_retry + 1} attempts")
            raise


# Backwards compatibility: get_llm() returns the active LLM
def get_llm() -> Any:
    """Backwards compatible function to get LLM instance."""
    return get_active_llm()


# =============================================================================
# LLMClient - Application-level wrapper for diagnostic reasoning
# =============================================================================

@dataclass
class LLMConfig:
    """Configuration for LLM."""
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    api_key: str = ""


class LLMClient:
    """
    LLM client for diagnostic reasoning with self-healing.
    
    Uses Groq for free tier inference with automatic key/model rotation.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or self._load_config()
        self._manager: Optional[LLMManager] = None
    
    def _load_config(self) -> LLMConfig:
        """Load configuration from environment."""
        return LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "groq"),
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY", "")
        )
    
    @property
    def manager(self) -> LLMManager:
        """Get or create the LLMManager instance."""
        if self._manager is None:
            self._manager = get_llm_manager()
        return self._manager
    
    def is_available(self) -> bool:
        """Check if LLM is configured."""
        return bool(self.config.api_key) or len(self.manager.api_keys) > 0
    
    def initialize(self) -> None:
        """Initialize the LLM client."""
        # LLMManager handles initialization automatically
        if not self.is_available():
            raise RuntimeError("LLM API key not configured")
        logger.info("LLMClient initialized with LLMManager")
    
    def diagnose(
        self,
        equipment_model: str,
        symptom_description: str,
        measurements: list[dict],
        evidence: str
    ) -> dict:
        """
        Use LLM to generate diagnostic hypothesis with self-healing.
        
        Args:
            equipment_model: Equipment model identifier
            symptom_description: Description of the problem
            measurements: List of measurement dictionaries
            evidence: Retrieved evidence from knowledge base
            
        Returns:
            Dict with diagnosis, confidence, and reasoning
        """
        # Build prompt
        prompt = f"""You are a biomedical equipment troubleshooting expert. Analyze the following case:

EQUIPMENT: {equipment_model}
SYMPTOM: {symptom_description}

MEASUREMENTS:
{self._format_measurements(measurements)}

EVIDENCE FROM KNOWLEDGE BASE:
{evidence}

Provide your diagnosis in JSON format:
{{
    "primary_cause": "Brief description of the root cause",
    "confidence": 0.0-1.0,
    "severity": "low/medium/high/critical",
    "supporting_evidence": ["list of evidence supporting diagnosis"],
    "recommended_actions": ["step 1", "step 2"]
}}

Return ONLY the JSON, no other text."""

        try:
            # Use invoke_with_retry for automatic retry/rotation
            response = invoke_with_retry([{"role": "user", "content": prompt}])
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON from response
            try:
                # First try direct parse
                result = json.loads(content)
            except json.JSONDecodeError:
                # Try to find JSON in response
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {
                        "primary_cause": "Could not parse LLM response",
                        "confidence": 0.0,
                        "severity": "unknown",
                        "error": content[:200]
                    }
            
            # Add manager status for debugging
            result["_manager_status"] = self.manager.status
            
            return result
            
        except Exception as e:
            logger.error(f"LLM diagnosis failed after retries: {str(e)}")
            return {
                "primary_cause": f"LLM error after all retries: {str(e)}",
                "confidence": 0.0,
                "severity": "unknown",
                "error": str(e)
            }
    
    def get_status(self) -> dict:
        """Get current LLMManager status."""
        return self.manager.status
    
    def reset_manager(self) -> None:
        """Reset the LLMManager to initial state."""
        self.manager.reset()
        logger.info("LLMManager reset")
    
    def _format_measurements(self, measurements: list[dict]) -> str:
        """Format measurements for prompt."""
        lines = []
        for m in measurements:
            tp = m.get("test_point", "Unknown")
            val = m.get("value", "?")
            unit = m.get("unit", "")
            anomaly = m.get("anomaly")
            if anomaly:
                lines.append(f"  - {tp}: {val} {unit} [ANOMALY: {anomaly.get('type', 'unknown')}]")
            else:
                lines.append(f"  - {tp}: {val} {unit}")
        return "\n".join(lines) if lines else "No measurements available"


# Backwards compatibility: create_llm_client factory function
def create_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """Create an LLMClient instance (backwards compatibility)."""
    return LLMClient(config)
