"""
LLM Client for Biomedical Troubleshooting Agent

Uses Groq (free tier) for intelligent reasoning with self-healing capabilities
via LLMManager for automatic key/model rotation on failures.
"""

import os
import json
import re
import logging
from typing import Optional
from dataclasses import dataclass

from .llm_manager import LLMManager, get_llm_manager, invoke_with_retry

logger = logging.getLogger(__name__)


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
