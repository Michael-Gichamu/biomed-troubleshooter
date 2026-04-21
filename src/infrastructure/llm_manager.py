"""
LLM Manager - Self-Healing AI Infrastructure

Provides automatic API key, model, and **provider** rotation for resilience
against rate limits, 5xx errors, and other API failures.

Provider hierarchy:
    PRIMARY_LLM_PROVIDER  (default: "anthropic")  — Claude Opus by default
    FALLBACK_LLM_PROVIDER (default: "groq")       — existing Groq/OpenAI fleet

Rotation strategy for a provider slot:
    1) advance to next API key
    2) if no more keys, advance to next model (keys reset to 0)
    3) if no more models in this provider, switch to fallback provider

Both providers are optional. If only one is configured the manager degrades
gracefully to single-provider behaviour — existing Groq-only deployments keep
working unchanged.
"""

from __future__ import annotations

import os
import time
import json
import re
import logging
import threading
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from src.infrastructure.log_parser import LogParser, ErrorContext

# Load environment variables
load_dotenv()

# Module-level logger only. Do NOT call logging.basicConfig() here — that would
# hijack the root logger for every process that imports this module (library
# anti-pattern). The application entry point (CLI / LangGraph Studio / FastAPI)
# owns global handler configuration.
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-provider slot
# ---------------------------------------------------------------------------

@dataclass
class ProviderSlot:
    """Keys + models + cursor state for a single provider."""
    name: str                        # "anthropic" | "groq" | "openai"
    api_keys: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    key_index: int = 0
    model_index: int = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_keys) and bool(self.models)

    @property
    def active_key(self) -> str:
        return self.api_keys[self.key_index]

    @property
    def active_model(self) -> str:
        return self.models[self.model_index]

    def advance_key(self) -> bool:
        if self.key_index < len(self.api_keys) - 1:
            self.key_index += 1
            return True
        return False

    def advance_model(self) -> bool:
        if self.model_index < len(self.models) - 1:
            self.model_index += 1
            self.key_index = 0
            return True
        return False

    def reset(self) -> None:
        self.key_index = 0
        self.model_index = 0


# ---------------------------------------------------------------------------
# LLMManager
# ---------------------------------------------------------------------------

class LLMManager:
    """
    Self-healing LLM router.

    Supports primary + fallback providers. Anthropic (Claude) is the default
    primary; Groq is the default fallback. Rotation walks keys → models within
    the current provider, then switches providers when that slot is exhausted.
    """

    _instance: Optional['LLMManager'] = None
    _initialized: bool = False
    _lock: threading.RLock = threading.RLock()

    # Default models per provider when env overrides are absent.
    _DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-6"
    _DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

    def __new__(cls):
        # Double-checked locking: fast path avoids the lock once created.
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if LLMManager._initialized:
            return
        with LLMManager._lock:
            if LLMManager._initialized:
                return
            self._load_config()
            self._initialize_llm()
            LLMManager._initialized = True

    # -----------------------------------------------------------------------
    # Config / initialization
    # -----------------------------------------------------------------------

    def _load_config(self):
        """Load provider slots and global retry config from environment."""
        primary_name = (os.getenv("PRIMARY_LLM_PROVIDER", "anthropic") or "").strip().lower()
        fallback_name = (os.getenv("FALLBACK_LLM_PROVIDER", "groq") or "").strip().lower()

        self._slots: Dict[str, ProviderSlot] = {}

        # Anthropic slot
        anthropic_slot = self._build_anthropic_slot()
        if anthropic_slot.is_configured:
            self._slots["anthropic"] = anthropic_slot

        # Groq slot (preserves existing env contract: GROQ_API_KEYS / LLM_MODELS)
        groq_slot = self._build_groq_slot()
        if groq_slot.is_configured:
            self._slots["groq"] = groq_slot

        # Optional OpenAI slot — only materialised if its own env is set so we
        # don't silently steal GROQ_API_KEYS. Backwards-compat: existing
        # deployments that route via LLM_MODELS with an "openai/" prefix still
        # work through the Groq slot (see _initialize_llm).
        openai_slot = self._build_openai_slot()
        if openai_slot.is_configured:
            self._slots["openai"] = openai_slot

        if not self._slots:
            raise ValueError(
                "No LLM provider is configured. Set at least one of "
                "ANTHROPIC_API_KEY(S) or GROQ_API_KEY(S)."
            )

        # Resolve primary / fallback — fall back to whichever slot exists.
        self._primary_name = primary_name if primary_name in self._slots else next(iter(self._slots))
        if fallback_name in self._slots and fallback_name != self._primary_name:
            self._fallback_name = fallback_name
        else:
            # Pick any other configured slot as fallback, or None if only one.
            others = [n for n in self._slots if n != self._primary_name]
            self._fallback_name = others[0] if others else None

        self._active_provider: str = self._primary_name

        # Global retry config (unchanged env contract)
        self.max_retries_per_key = int(os.getenv("MAX_RETRIES_PER_KEY", "2"))
        self.max_retries_per_model = int(os.getenv("MAX_RETRIES_PER_MODEL", "2"))
        self.base_backoff = float(os.getenv("BACKOFF_BASE_SECONDS", "1.0"))
        self.max_backoff = float(os.getenv("BACKOFF_MAX_SECONDS", "16.0"))

        # Rotation counters
        self.key_retry_count = 0
        self.model_retry_count = 0

        # Active LLM instance (lazy)
        self._current_llm: Optional[Any] = None

        logger.info(
            "LLMManager initialized: primary=%s, fallback=%s, configured=%s",
            self._primary_name, self._fallback_name, list(self._slots.keys()),
        )
        for name, slot in self._slots.items():
            logger.info("  %s: %d key(s), models=%s", name, len(slot.api_keys), slot.models)

    @staticmethod
    def _split_env_list(value: str) -> List[str]:
        return [v.strip() for v in (value or "").split(",") if v.strip()]

    def _build_anthropic_slot(self) -> ProviderSlot:
        keys_str = os.getenv("ANTHROPIC_API_KEYS", os.getenv("ANTHROPIC_API_KEY", ""))
        models_str = os.getenv("ANTHROPIC_MODELS", self._DEFAULT_ANTHROPIC_MODEL)
        return ProviderSlot(
            name="anthropic",
            api_keys=self._split_env_list(keys_str),
            models=self._split_env_list(models_str),
        )

    def _build_groq_slot(self) -> ProviderSlot:
        keys_str = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
        models_str = os.getenv("LLM_MODELS", self._DEFAULT_GROQ_MODEL)
        return ProviderSlot(
            name="groq",
            api_keys=self._split_env_list(keys_str),
            models=self._split_env_list(models_str),
        )

    def _build_openai_slot(self) -> ProviderSlot:
        keys_str = os.getenv("OPENAI_API_KEYS", os.getenv("OPENAI_API_KEY", ""))
        models_str = os.getenv("OPENAI_MODELS", "")
        return ProviderSlot(
            name="openai",
            api_keys=self._split_env_list(keys_str),
            models=self._split_env_list(models_str),
        )

    def _initialize_llm(self):
        """Materialise a concrete LangChain chat model for the active slot."""
        slot = self._slots[self._active_provider]
        model = slot.active_model
        api_key = slot.active_key

        if self._active_provider == "anthropic":
            # Lazy import so deployments without langchain-anthropic installed
            # degrade with a clear error message rather than a cold ImportError.
            try:
                from langchain_anthropic import ChatAnthropic
            except ImportError as e:
                raise RuntimeError(
                    "langchain-anthropic is required for the Anthropic provider. "
                    "Install via `pip install langchain-anthropic`."
                ) from e
            self._current_llm = ChatAnthropic(
                model=model,
                api_key=api_key,
                temperature=0.0,
                max_tokens=4096,
                timeout=60,
            )
            provider_label = "anthropic"

        elif self._active_provider == "openai":
            # True OpenAI (not Groq-hosted). Model names are raw (e.g., gpt-4o).
            self._current_llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                temperature=0.0,
                max_tokens=2048,
                timeout=60,
            )
            provider_label = "openai"

        else:
            # "groq" slot — preserves legacy model-prefix routing:
            # `openai/<name>` (without gpt- prefix) was historically mapped to
            # OpenAI. gpt-oss-* stays on Groq (Groq hosts that family).
            if model.startswith("openai/") and not model.startswith("gpt-"):
                model_name = model.replace("openai/", "")
                self._current_llm = ChatOpenAI(
                    model=model_name,
                    api_key=api_key,
                    temperature=0.0,
                    max_tokens=2048,
                    timeout=60,
                )
                provider_label = "groq→openai"
            else:
                self._current_llm = ChatGroq(
                    model=model,
                    api_key=api_key,
                    temperature=0.0,
                    max_tokens=2048,
                    timeout=60,
                )
                provider_label = "groq"

        logger.info(
            "Active LLM: provider=%s, model=%s, key_index=%d",
            provider_label, model, slot.key_index,
        )

    # -----------------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------------

    @property
    def current_llm(self) -> Any:
        if self._current_llm is None:
            self._initialize_llm()
        return self._current_llm

    @property
    def active_provider(self) -> str:
        return self._active_provider

    @property
    def active_model(self) -> str:
        return self._slots[self._active_provider].active_model

    @property
    def active_key_index(self) -> int:
        return self._slots[self._active_provider].key_index

    # Back-compat shim — a handful of older modules read these directly.
    @property
    def api_keys(self) -> List[str]:
        return self._slots[self._active_provider].api_keys

    @property
    def models(self) -> List[str]:
        return self._slots[self._active_provider].models

    @property
    def current_key_index(self) -> int:
        return self._slots[self._active_provider].key_index

    @property
    def current_model_index(self) -> int:
        return self._slots[self._active_provider].model_index

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "active_provider": self._active_provider,
            "active_model": self.active_model,
            "active_key_index": self.active_key_index,
            "primary_provider": self._primary_name,
            "fallback_provider": self._fallback_name,
            "configured_providers": list(self._slots.keys()),
            "total_keys": len(self._slots[self._active_provider].api_keys),
            "total_models": len(self._slots[self._active_provider].models),
            "key_retry_count": self.key_retry_count,
            "model_retry_count": self.model_retry_count,
        }

    # -----------------------------------------------------------------------
    # Rotation
    # -----------------------------------------------------------------------

    def should_rotate(self, exception: Exception) -> bool:
        error_context = LogParser.parse_error(exception)
        if not error_context.retryable:
            logger.warning("Non-retryable error: %s", error_context.error_type)
            return False
        if self.key_retry_count >= self.max_retries_per_key:
            logger.warning("Key retry limit reached (%d)", self.max_retries_per_key)
            return True
        if self.model_retry_count >= self.max_retries_per_model:
            logger.warning("Model retry limit reached (%d)", self.max_retries_per_model)
            return True
        return True

    def rotate(self) -> bool:
        """Advance one step along the rotation ladder.

        key → model → fallback provider. Returns False only when every
        configured provider is exhausted.
        """
        slot = self._slots[self._active_provider]

        # 1) next key within the same provider+model
        if slot.advance_key():
            self.key_retry_count = 0
            logger.info(
                "Rotating to next API key on %s: key_index=%d",
                self._active_provider, slot.key_index,
            )
            self._initialize_llm()
            return True

        # 2) next model within the same provider
        if slot.advance_model():
            self.model_retry_count = 0
            self.key_retry_count = 0
            logger.info(
                "Rotating to next model on %s: %s",
                self._active_provider, slot.active_model,
            )
            self._initialize_llm()
            return True

        # 3) switch to fallback provider (if configured and we haven't used it)
        if self._fallback_name and self._active_provider != self._fallback_name:
            logger.warning(
                "Provider %s exhausted — switching to fallback provider %s",
                self._active_provider, self._fallback_name,
            )
            self._active_provider = self._fallback_name
            self._slots[self._active_provider].reset()
            self.key_retry_count = 0
            self.model_retry_count = 0
            self._initialize_llm()
            return True

        logger.error("All providers exhausted — no further rotation possible.")
        return False

    def increment_retry(self):
        self.key_retry_count += 1
        logger.info("Key retry count: %d/%d", self.key_retry_count, self.max_retries_per_key)

    def increment_model_retry(self):
        self.model_retry_count += 1
        logger.info("Model retry count: %d/%d", self.model_retry_count, self.max_retries_per_model)

    def get_backoff_time(self) -> float:
        backoff = self.base_backoff * (2 ** self.key_retry_count)
        return min(backoff, self.max_backoff)

    def reset(self):
        """Reset back to primary provider, first key, first model."""
        for slot in self._slots.values():
            slot.reset()
        self._active_provider = self._primary_name
        self.key_retry_count = 0
        self.model_retry_count = 0
        self._initialize_llm()
        logger.info("LLMManager reset to primary provider: %s", self._primary_name)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_llm_manager: Optional[LLMManager] = None
_llm_manager_lock = threading.Lock()


def get_llm_manager() -> LLMManager:
    """Get the singleton LLMManager instance (thread-safe)."""
    global _llm_manager
    if _llm_manager is None:
        with _llm_manager_lock:
            if _llm_manager is None:
                _llm_manager = LLMManager()
    return _llm_manager


def get_active_llm() -> Any:
    return get_llm_manager().current_llm


# ---------------------------------------------------------------------------
# Invocation helpers with retry + rotation
# ---------------------------------------------------------------------------

def invoke_with_retry(messages: List[Dict[str, str]], max_full_retries: int = 3) -> Any:
    """Invoke the active LLM with automatic retry and rotation."""
    manager = get_llm_manager()

    for full_retry in range(max_full_retries):
        llm = manager.current_llm
        try:
            return llm.invoke(messages)
        except Exception as e:
            logger.warning("LLM call failed: %s", str(e)[:200])

            if manager.should_rotate(e):
                backoff_time = manager.get_backoff_time()
                logger.info("Retrying after %.2fs...", backoff_time)
                time.sleep(backoff_time)

                if manager.rotate():
                    manager.increment_retry()
                    continue

            logger.error("All retries exhausted after %d attempts", full_retry + 1)
            raise


def invoke_with_tools_and_retry(messages: List[Any], tools: List[Any], max_full_retries: int = 3) -> Any:
    """Invoke LLM with tools bound, with automatic retry and rotation."""
    manager = get_llm_manager()

    for full_retry in range(max_full_retries):
        llm = manager.current_llm
        try:
            llm_with_tools = llm.bind_tools(tools)
            return llm_with_tools.invoke(messages)
        except Exception as e:
            logger.warning("LLM call with tools failed: %s", str(e)[:200])

            if manager.should_rotate(e):
                backoff_time = manager.get_backoff_time()
                logger.info("Retrying after %.2fs...", backoff_time)
                time.sleep(backoff_time)

                if manager.rotate():
                    manager.increment_retry()
                    continue

            logger.error("All retries exhausted after %d attempts", full_retry + 1)
            raise


# Backwards compatibility
def get_llm() -> Any:
    return get_active_llm()


# =============================================================================
# LLMClient - Application-level wrapper for diagnostic reasoning
# =============================================================================

@dataclass
class LLMConfig:
    """Configuration for LLM (kept for backwards compatibility)."""
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    api_key: str = ""


class LLMClient:
    """LLM client for diagnostic reasoning, backed by the self-healing manager."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or self._load_config()
        self._manager: Optional[LLMManager] = None

    def _load_config(self) -> LLMConfig:
        return LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "groq"),
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY", ""),
        )

    @property
    def manager(self) -> LLMManager:
        if self._manager is None:
            self._manager = get_llm_manager()
        return self._manager

    def is_available(self) -> bool:
        try:
            return len(self.manager.api_keys) > 0
        except Exception:
            return bool(self.config.api_key)

    def initialize(self) -> None:
        if not self.is_available():
            raise RuntimeError("LLM API key not configured")
        logger.info("LLMClient initialized with LLMManager")

    def diagnose(
        self,
        equipment_model: str,
        symptom_description: str,
        measurements: list[dict],
        evidence: str,
    ) -> dict:
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
            response = invoke_with_retry([{"role": "user", "content": prompt}])
            content = response.content if hasattr(response, 'content') else str(response)
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {
                        "primary_cause": "Could not parse LLM response",
                        "confidence": 0.0,
                        "severity": "unknown",
                        "error": content[:200],
                    }
            result["_manager_status"] = self.manager.status
            return result
        except Exception as e:
            logger.error("LLM diagnosis failed after retries: %s", str(e))
            return {
                "primary_cause": f"LLM error after all retries: {str(e)}",
                "confidence": 0.0,
                "severity": "unknown",
                "error": str(e),
            }

    def get_status(self) -> dict:
        return self.manager.status

    def reset_manager(self) -> None:
        self.manager.reset()
        logger.info("LLMManager reset")

    def _format_measurements(self, measurements: list[dict]) -> str:
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


def create_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    return LLMClient(config)
