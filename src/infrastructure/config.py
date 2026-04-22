"""
Configuration Module

Centralized configuration management for the AI Agent.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    api_key: str | None = None
    temperature: float = 0.1
    max_tokens: int = 2048

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            provider=os.getenv("LLM_PROVIDER", "groq"),
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        )


@dataclass
class EmbeddingConfig:
    """Embedding model configuration."""

    provider: str = "local"
    model: str = "all-MiniLM-L6-v2"

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            provider=os.getenv("EMBEDDING_PROVIDER", "local"),
            model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        )


@dataclass
class ChromaDBConfig:
    """ChromaDB configuration."""

    host: str = "localhost"
    port: int = 8000
    collection: str = "biomed_equipment"

    @classmethod
    def from_env(cls) -> "ChromaDBConfig":
        return cls(
            host=os.getenv("CHROMADB_HOST", "localhost"),
            port=int(os.getenv("CHROMADB_PORT", "8000")),
            collection=os.getenv("CHROMADB_COLLECTION", "biomed_equipment"),
        )


@dataclass
class USBConfig:
    """USB Multimeter configuration."""

    port: str | None = None  # Auto-detect if None
    baud_rate: int = 2400
    timeout: float = 2.0

    @classmethod
    def from_env(cls) -> "USBConfig":
        return cls(
            port=os.getenv("USB_PORT") or None,
            baud_rate=int(os.getenv("USB_BAUD_RATE", "2400")),
            timeout=float(os.getenv("USB_TIMEOUT", "2.0")),
        )


@dataclass
class ImageConfig:
    """Image server configuration."""

    base_url: str = ""  # Default to empty - use full URLs from YAML

    @classmethod
    def from_env(cls) -> "ImageConfig":
        return cls(base_url=os.getenv("IMAGE_BASE_URL", ""))  # Default to empty string


@dataclass
class DatabaseConfig:
    """Postgres / SQLAlchemy configuration.

    An empty ``url`` means "no database configured" — downstream code falls back
    to in-memory alternatives (``MemorySaver`` for the LangGraph checkpointer,
    YAML loader for equipment). This keeps unit tests, local LangGraph Studio,
    and casual dev loops working with zero infrastructure.
    """

    url: str = ""  # e.g. "postgresql://user:pass@host:5432/db"
    equipment_store: str = "yaml"  # "yaml" | "postgres"
    pool_size: int = 5
    pool_max_overflow: int = 10
    pool_timeout: float = 30.0
    echo: bool = False  # SQLAlchemy engine echo — noisy, for debug

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            url=os.getenv("DATABASE_URL", "").strip(),
            equipment_store=os.getenv("EQUIPMENT_STORE", "yaml").strip().lower(),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            pool_max_overflow=int(os.getenv("DB_POOL_MAX_OVERFLOW", "10")),
            pool_timeout=float(os.getenv("DB_POOL_TIMEOUT", "30")),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
        )

    @property
    def is_configured(self) -> bool:
        """True if a DATABASE_URL was supplied."""
        return bool(self.url)


@dataclass
class AppConfig:
    """Main application configuration."""

    mode: str = "usb"  # "usb" (USB multimeter mode)
    debug: bool = False
    log_level: str = "INFO"

    # Sub-configurations
    llm: LLMConfig = field(default_factory=LLMConfig.from_env)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig.from_env)
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig.from_env)
    usb: USBConfig = field(default_factory=USBConfig.from_env)
    image: ImageConfig = field(default_factory=ImageConfig.from_env)
    database: DatabaseConfig = field(default_factory=DatabaseConfig.from_env)

    # Paths
    knowledge_path: Path = field(default_factory=lambda: Path("data/knowledge"))
    equipment_path: Path = field(default_factory=lambda: Path("data/equipment"))

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            mode=os.getenv("APP_MODE", "usb").lower(),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            llm=LLMConfig.from_env(),
            embedding=EmbeddingConfig.from_env(),
            chromadb=ChromaDBConfig.from_env(),
            usb=USBConfig.from_env(),
            image=ImageConfig.from_env(),
            database=DatabaseConfig.from_env(),
        )

    def is_usb_mode(self) -> bool:
        """Check if running in USB mode."""
        return self.mode == "usb"


# Global configuration instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config


def reload_config() -> AppConfig:
    """Reload configuration from environment."""
    global _config
    _config = AppConfig.from_env()
    return _config


# =============================================================================
# Convenience Functions for Backward Compatibility
# =============================================================================


def get_llm_config() -> LLMConfig:
    """Get LLM configuration."""
    return get_config().llm


def get_embedding_config() -> EmbeddingConfig:
    """Get embedding configuration."""
    return get_config().embedding


def get_chromadb_config() -> ChromaDBConfig:
    """Get ChromaDB configuration."""
    return get_config().chromadb


def get_langsmith_config() -> dict:
    """Get LangSmith configuration."""
    import os

    return {
        "api_key": os.getenv("LANGCHAIN_API_KEY"),
        "project": os.getenv("LANGCHAIN_PROJECT", "biomed-troubleshooter"),
        "tracing": os.getenv("LANGCHAIN_TRACING", "true").lower() == "true",
    }


def get_app_config() -> AppConfig:
    """Get application configuration."""
    return get_config()


def get_image_base_url() -> str:
    """Get the base URL for equipment images.

    Returns:
        The IMAGE_BASE_URL from environment, defaults to empty string
        (meaning full URLs from YAML will be used as-is)
    """
    return get_config().image.base_url


def get_database_config() -> DatabaseConfig:
    """Get Postgres / SQLAlchemy configuration."""
    return get_config().database


def get_equipment_store() -> str:
    """Backend for equipment config loads: ``"yaml"`` (default) or ``"postgres"``."""
    return get_config().database.equipment_store
