"""
ChromaDB Vector Database

Manages the ChromaDB vector store for troubleshooting documentation.
Follows infrastructure layer patterns.
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Lazy import for sentence-transformers to avoid import errors
_embedding_function = None

def _get_embedding_function():
    """Get or create the sentence-transformers embedding function."""
    global _embedding_function
    if _embedding_function is None:
        from sentence_transformers import SentenceTransformer
        # Use the same model that's already cached
        _embedding_function = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_function


@dataclass
class ChromaDBConfig:
    """Configuration for ChromaDB."""
    persist_directory: str = "data/chromadb"
    collection_name: str = "troubleshooting"
    embedding_function: str = "default"  # default, openai, sentence-transformers


class ChromaDBClient:
    """
    Client for ChromaDB operations.

    Design:
    - Lazy initialization
    - Configurable persistence
    - Safe fallback to in-memory
    """

    def __init__(self, config: Optional[ChromaDBConfig] = None):
        self.config = config or ChromaDBConfig()
        self._client = None
        self._collection = None

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._client is not None and self._collection is not None

    def initialize(self) -> None:
        """Initialize ChromaDB client and collection."""
        # Create persistence directory
        import os
        Path(self.config.persist_directory).mkdir(parents=True, exist_ok=True)
        
        # Try local PersistentClient first (no Docker needed!)
        try:
            import chromadb
            from chromadb.config import Settings
            self._client = chromadb.PersistentClient(
                path=self.config.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            print(f"[ChromaDB] Using local persistent storage at {self.config.persist_directory}")
        except Exception as local_err:
            # Fall back to in-memory if local fails
            print(f"[ChromaDB] Local storage failed: {local_err}")
            try:
                import chromadb
                self._client = chromadb.EphemeralClient()
                print("[ChromaDB] Using in-memory client")
            except OSError as ephemeral_err:
                raise RuntimeError(f"ChromaDB unavailable: {ephemeral_err}")

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.config.collection_name,
            metadata={
                "description": "Troubleshooting documentation for biomedical equipment",
                "version": "1.0"
            }
        )

    def reset(self) -> None:
        """Reset the collection (for testing)."""
        if self._client:
            self._client.delete_collection(self.config.collection_name)
            self._collection = None

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str]
    ) -> None:
        """
        Add documents to the collection.

        Args:
            documents: List of text documents
            metadatas: List of metadata dicts
            ids: List of unique document IDs
        """
        if not self.is_initialized:
            self.initialize()

        # Pre-compute embeddings using sentence-transformers (avoids ONNX download issues)
        embedding_fn = _get_embedding_function()
        embeddings = embedding_fn.encode(documents).tolist()

        self._collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )

    def query(
        self,
        query_texts: list[str],
        n_results: int = 5,
        where: Optional[dict] = None
    ) -> dict:
        """
        Query the collection.

        Args:
            query_texts: List of query strings
            n_results: Number of results to return
            where: Optional filter

        Returns:
            Query results dict
        """
        if not self.is_initialized:
            self.initialize()

        # Pre-compute query embeddings using sentence-transformers
        embedding_fn = _get_embedding_function()
        query_embeddings = embedding_fn.encode(query_texts).tolist()

        return self._collection.query(
            query_texts=query_texts,
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

    def get_collection_stats(self) -> dict:
        """Get collection statistics."""
        if not self.is_initialized:
            return {"count": 0}

        return {
            "count": self._collection.count(),
            "name": self.config.collection_name
        }


def create_chromadb_client(persist_directory: str = "data/chromadb") -> ChromaDBClient:
    """Factory function to create ChromaDB client."""
    config = ChromaDBConfig(persist_directory=persist_directory)
    return ChromaDBClient(config)
