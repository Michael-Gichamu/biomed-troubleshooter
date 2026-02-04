"""
RAG Repository

Evidence retrieval from ChromaDB.
Strictly limited to evidence retrieval - no freeform reasoning.
"""

from dataclasses import dataclass
from typing import Optional
import json
from pathlib import Path


@dataclass
class DocumentSnippet:
    """A retrieved document snippet."""
    doc_id: str
    title: str
    section: Optional[str]
    content: str
    relevance_score: float

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "section": self.section,
            "content": self.content,
            "relevance_score": self.relevance_score
        }


class RAGRepository:
    """
    Repository for retrieving troubleshooting documentation.

    Design Principles:
    - Deterministic retrieval based on embeddings
    - No reasoning - just evidence retrieval
    - Fallback to static rules if RAG unavailable
    """

    def __init__(
        self,
        chromadb_path: Optional[str] = None,
        namespace: str = "troubleshooting"
    ):
        self.chromadb_path = chromadb_path
        self.namespace = namespace
        self._client = None
        self._collection = None

    def initialize(self) -> None:
        """Initialize the ChromaDB connection."""
        try:
            import chromadb
            if self.chromadb_path:
                self._client = chromadb.PersistentClient(path=self.chromadb_path)
            else:
                self._client = chromadb.InMemoryClient()
            self._collection = self._client.get_or_create_collection(
                name=self.namespace,
                metadata={"description": "Troubleshooting documentation"}
            )
        except ImportError:
            raise RuntimeError("ChromaDB not installed. Run: pip install chromadb")

    def is_available(self) -> bool:
        """Check if RAG is available."""
        return self._collection is not None

    def retrieve(
        self,
        query: str,
        equipment_model: str,
        top_k: int = 5
    ) -> list[DocumentSnippet]:
        """
        Retrieve relevant documentation snippets.

        Args:
            query: Natural language query (symptom description)
            equipment_model: Equipment model to filter by
            top_k: Maximum number of results

        Returns:
            List of relevant document snippets
        """
        if not self.is_available():
            # Fallback to empty results if RAG unavailable
            return []

        try:
            # Add equipment filter to query for better results
            filtered_query = f"{query} {equipment_model}"

            results = self._collection.query(
                query_texts=[filtered_query],
                n_results=top_k,
                where={"equipment_model": equipment_model},
                include=["documents", "metadatas", "distances"]
            )

            return self._parse_results(results)

        except Exception as e:
            # Log error but don't fail - RAG is auxiliary
            print(f"RAG retrieval error: {e}")
            return []

    def _parse_results(self, results: dict) -> list[DocumentSnippet]:
        """Parse ChromaDB results into DocumentSnippets."""
        snippets = []

        if not results.get("ids") or len(results["ids"]) == 0:
            return []

        for i in range(len(results["ids"][0])):
            # Calculate relevance score from distance
            distance = results.get("distances", [[1.0]])[0][i]
            relevance = max(0.0, 1.0 - distance)

            snippet = DocumentSnippet(
                doc_id=results["ids"][0][i],
                title=results["metadatas"][0][i].get("title", "Unknown"),
                section=results["metadatas"][0][i].get("section"),
                content=results["documents"][0][i],
                relevance_score=relevance
            )
            snippets.append(snippet)

        return snippets


class StaticRuleRepository:
    """
    Fallback repository for static diagnostic rules.

    Used when RAG is unavailable or returns no results.
    Provides deterministic rule-based fallback.
    """

    def __init__(self, rules_path: Optional[str] = None):
        self.rules_path = rules_path or self._default_rules_path()
        self._rules_cache: Optional[list[dict]] = None

    def _default_rules_path(self) -> str:
        """Get default rules file path."""
        return str(Path(__file__).parent / "static_rules.json")

    def get_rules(self, equipment_model: str) -> list[dict]:
        """
        Get static rules for an equipment model.

        Returns deterministic rules - no AI involved.
        """
        if self._rules_cache is None:
            self._rules_cache = self._load_rules()

        return [
            r for r in self._rules_cache
            if r.get("equipment_model") == equipment_model
        ]

    def _load_rules(self) -> list[dict]:
        """Load rules from JSON file."""
        try:
            with open(self.rules_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def find_matching_rules(
        self,
        equipment_model: str,
        signal_patterns: list[dict]
    ) -> list[dict]:
        """
        Find rules matching signal patterns.

        Pattern matching is deterministic - no AI involved.
        """
        rules = self.get_rules(equipment_model)
        matches = []

        for rule in rules:
            if self._matches_pattern(rule, signal_patterns):
                matches.append(rule)

        return matches

    def _matches_pattern(self, rule: dict, patterns: list[dict]) -> bool:
        """Check if a rule matches signal patterns."""
        required_signals = rule.get("required_signals", [])

        for req in required_signals:
            tp_id = req.get("test_point_id")
            expected_state = req.get("state")

            # Check if pattern matches
            found = False
            for p in patterns:
                if p.get("test_point_id") == tp_id and p.get("state") == expected_state:
                    found = True
                    break

            if not found:
                return False

        return True


class EvidenceAggregator:
    """
    Aggregates evidence from multiple sources.

    Combines RAG retrieval with static rules.
    No reasoning - just aggregation.
    """

    def __init__(
        self,
        rag_repo: RAGRepository,
        static_repo: StaticRuleRepository
    ):
        self.rag_repo = rag_repo
        self.static_repo = static_repo

    def retrieve_evidence(
        self,
        query: str,
        equipment_model: str,
        signal_patterns: list[dict]
    ) -> dict:
        """
        Retrieve evidence from all sources.

        Returns:
            Dict with 'documents' and 'rules' keys
        """
        # Parallel retrieval from both sources
        docs = self.rag_repo.retrieve(query, equipment_model)
        rules = self.static_repo.find_matching_rules(equipment_model, signal_patterns)

        return {
            "documents": [d.to_dict() for d in docs],
            "rules": rules,
            "sources_retrieved": len(docs) + len(rules)
        }
