"""
LLM Client for Biomedical Troubleshooting Agent

Uses Groq (free tier) for intelligent reasoning.
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for LLM."""
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    api_key: str = ""


class LLMClient:
    """
    LLM client for diagnostic reasoning.
    
    Uses Groq for free tier inference.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or self._load_config()
        self._client = None
    
    def _load_config(self) -> LLMConfig:
        """Load configuration from environment."""
        return LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "groq"),
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY", "")
        )
    
    def is_available(self) -> bool:
        """Check if LLM is configured."""
        return bool(self.config.api_key)
    
    def initialize(self) -> None:
        """Initialize the LLM client."""
        if not self.is_available:
            raise RuntimeError("LLM API key not configured")
        
        try:
            from langchain_groq import ChatGroq
            self._client = ChatGroq(
                model=self.config.model,
                api_key=self.config.api_key,
                temperature=0.1
            )
        except ImportError:
            raise RuntimeError("langchain-groq not installed. Run: pip install langchain-groq")
    
    def diagnose(
        self,
        equipment_model: str,
        symptom_description: str,
        measurements: list[dict],
        evidence: str
    ) -> dict:
        """
        Use LLM to generate diagnostic hypothesis.
        
        Args:
            equipment_model: Equipment model identifier
            symptom_description: Description of the problem
            measurements: List of measurement dictionaries
            evidence: Retrieved evidence from knowledge base
            
        Returns:
            Dict with diagnosis, confidence, and reasoning
        """
        if not self._client:
            self.initialize()
        
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
            response = self._client.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON from response
            import json
            # Try to extract JSON from response
            try:
                # First try direct parse
                result = json.loads(content)
            except json.JSONDecodeError:
                # Try to find JSON in response
                import re
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
            
            return result
            
        except Exception as e:
            return {
                "primary_cause": f"LLM error: {str(e)}",
                "confidence": 0.0,
                "severity": "unknown",
                "error": str(e)
            }
    
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


def create_llm_client() -> Optional[LLMClient]:
    """Factory function to create LLM client."""
    try:
        return LLMClient()
    except Exception as e:
        print(f"[WARN] Could not create LLM client: {e}")
        return None
