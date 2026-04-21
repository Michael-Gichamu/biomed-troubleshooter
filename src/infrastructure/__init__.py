"""
Infrastructure Layer

External services, data access, and adapters.
Contains RAG implementation, equipment configuration, and integrations.
"""

from src.infrastructure.config import (
    get_app_config,
    get_chromadb_config,
    get_embedding_config,
    get_langsmith_config,
    get_llm_config,
)
from src.infrastructure.equipment_config import (
    EquipmentConfig,
    EquipmentConfigLoader,
    FaultConfig,
    ImageConfig,
    SignalConfig,
    ThresholdConfig,
    get_equipment_config,
)

# LLM exports
from src.infrastructure.llm_manager import get_llm_manager, invoke_with_retry
from src.infrastructure.rag_repository import (
    DocumentSnippet,
    EvidenceAggregator,
    RAGRepository,
    StaticRuleRepository,
)

# Public API — re-exported for convenient `from src.infrastructure import X`.
__all__ = [
    "DocumentSnippet",
    "EquipmentConfig",
    "EquipmentConfigLoader",
    "EvidenceAggregator",
    "FaultConfig",
    "ImageConfig",
    "RAGRepository",
    "SignalConfig",
    "StaticRuleRepository",
    "ThresholdConfig",
    "get_app_config",
    "get_chromadb_config",
    "get_embedding_config",
    "get_equipment_config",
    "get_langsmith_config",
    "get_llm_config",
    "get_llm_manager",
    "invoke_with_retry",
]
