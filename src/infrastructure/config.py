"""
Configuration Loader

Loads environment variables from .env file.
Supports development and production configurations.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


def load_env_file(env_path: Optional[str] = None) -> None:
    """
    Load environment variables from .env file.

    Args:
        env_path: Path to .env file (default: project root/.env)
    """
    if env_path is None:
        env_path = Path(__file__).parent.parent.parent / ".env"

    env_file = Path(env_path)

    if not env_file.exists():
        return

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


# Load .env on module import
load_env_file()


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: str = "openai"  # openai, anthropic, ollama
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create from environment variables."""
        return cls(
            provider=os.environ.get("LLM_PROVIDER", "openai"),
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=os.environ.get("OLLAMA_BASE_URL"),
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini")
        )


@dataclass
class EmbeddingConfig:
    """Embedding configuration."""
    provider: str = "openai"  # openai, huggingface
    model: str = "text-embedding-3-small"
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """Create from environment variables."""
        return cls(
            provider=os.environ.get("EMBEDDING_PROVIDER", "openai"),
            model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
            api_key=os.environ.get("OPENAI_API_KEY")
        )


@dataclass
class ChromaDBConfig:
    """ChromaDB configuration."""
    persist_directory: str = "data/chromadb"
    collection_name: str = "troubleshooting"

    @classmethod
    def from_env(cls) -> "ChromaDBConfig":
        """Create from environment variables."""
        return cls(
            persist_directory=os.environ.get("CHROMADB_PERSIST_DIRECTORY", "data/chromadb"),
            collection_name=os.environ.get("CHROMADB_COLLECTION", "troubleshooting")
        )


@dataclass
class LangSmithConfig:
    """LangSmith configuration."""
    api_key: Optional[str] = None
    project: str = "biomed-troubleshooter"
    endpoint: str = "https://api.smith.langchain.com"
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "LangSmithConfig":
        """Create from environment variables."""
        return cls(
            api_key=os.environ.get("LANGCHAIN_API_KEY"),
            project=os.environ.get("LANGCHAIN_PROJECT", "biomed-troubleshooter"),
            endpoint=os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
            enabled=os.environ.get("LANGCHAIN_TRACING", "true").lower() == "true"
        )


@dataclass
class AppConfig:
    """Application configuration."""
    env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create from environment variables."""
        return cls(
            env=os.environ.get("APP_ENV", "development"),
            debug=os.environ.get("DEBUG", "true").lower() == "true",
            log_level=os.environ.get("LOG_LEVEL", "INFO")
        )


# =============================================================================
# Configuration Factory
# =============================================================================

def get_llm_config() -> LLMConfig:
    """Get LLM configuration."""
    return LLMConfig.from_env()


def get_embedding_config() -> EmbeddingConfig:
    """Get embedding configuration."""
    return EmbeddingConfig.from_env()


def get_chromadb_config() -> ChromaDBConfig:
    """Get ChromaDB configuration."""
    return ChromaDBConfig.from_env()


def get_langsmith_config() -> LangSmithConfig:
    """Get LangSmith configuration."""
    return LangSmithConfig.from_env()


def get_app_config() -> AppConfig:
    """Get application configuration."""
    return AppConfig.from_env()


# =============================================================================
# Environment Variable Setup
# =============================================================================

def setup_environment() -> None:
    """
    Setup all environment variables from .env file.

    Call this at application startup:
        from src.infrastructure.config import setup_environment
        setup_environment()
    """
    load_env_file()
