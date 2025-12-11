"""
RAG (Retrieval-Augmented Generation) Module

ChromaDB-based knowledge base for coaching insights.
"""

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


class CoachingKnowledgeBase:
    """
    ChromaDB-based knowledge base for Valorant coaching.

    Stores and retrieves tactical knowledge, communication best practices,
    and round-specific strategies.
    """

    COLLECTION_NAME = "valorant_coaching"

    def __init__(
        self,
        persist_directory: Path,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize knowledge base.

        Args:
            persist_directory: Directory to store ChromaDB data
            embedding_model: Sentence transformer model for embeddings
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))

        # Use sentence-transformers for embeddings
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"description": "Valorant coaching knowledge base"},
        )

        logger.info(
            f"Knowledge base initialized with {self.collection.count()} documents"
        )

    def add_document(
        self,
        content: str,
        doc_id: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Add a document to the knowledge base.

        Args:
            content: Document text content
            doc_id: Unique document identifier
            metadata: Optional metadata (category, map, etc.)
        """
        self.collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata or {}],
        )
        logger.debug(f"Added document: {doc_id}")

    def add_documents_from_directory(self, docs_dir: Path) -> int:
        """
        Bulk load documents from directory.

        Supports .txt and .md files.

        Args:
            docs_dir: Directory containing knowledge documents

        Returns:
            Number of documents loaded
        """
        count = 0

        for file_path in docs_dir.glob("**/*.txt"):
            self._load_document_file(file_path)
            count += 1

        for file_path in docs_dir.glob("**/*.md"):
            self._load_document_file(file_path)
            count += 1

        logger.info(f"Loaded {count} documents from {docs_dir}")
        return count

    def _load_document_file(self, file_path: Path) -> None:
        """Load single document file."""
        content = file_path.read_text(encoding="utf-8")
        doc_id = file_path.stem

        # Extract metadata from filename pattern: category_topic.txt
        parts = doc_id.split("_")
        metadata = {
            "source": str(file_path),
            "category": parts[0] if len(parts) > 1 else "general",
        }

        self.add_document(content, doc_id, metadata)

    def query(
        self,
        question: str,
        n_results: int = 3,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        Query knowledge base for relevant documents.

        Args:
            question: Query text
            n_results: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of matching documents with metadata
        """
        results = self.collection.query(
            query_texts=[question],
            n_results=n_results,
            where=filter_metadata,
        )

        # Format results
        documents = []
        for i, doc in enumerate(results["documents"][0]):
            documents.append({
                "id": results["ids"][0][i],
                "content": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })

        return documents

    def query_for_round(
        self,
        round_context: str,
        transcript_summary: str,
        n_results: int = 3,
    ) -> list[dict]:
        """
        Query for round-specific coaching insights.

        Args:
            round_context: Round situation (e.g., "2v4 retake on Ascent A site")
            transcript_summary: Summary of communications
            n_results: Number of results

        Returns:
            Relevant coaching documents
        """
        combined_query = f"""
        Situation: {round_context}
        Communications: {transcript_summary}
        What coaching advice is relevant?
        """

        return self.query(combined_query, n_results)

    def get_document(self, doc_id: str) -> Optional[dict]:
        """Get specific document by ID."""
        result = self.collection.get(ids=[doc_id])

        if result["documents"]:
            return {
                "id": doc_id,
                "content": result["documents"][0],
                "metadata": result["metadatas"][0] if result["metadatas"] else {},
            }

        return None

    def delete_document(self, doc_id: str) -> None:
        """Delete document from knowledge base."""
        self.collection.delete(ids=[doc_id])
        logger.debug(f"Deleted document: {doc_id}")

    def clear(self) -> None:
        """Clear all documents from collection."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
        )
        logger.info("Knowledge base cleared")

    @property
    def document_count(self) -> int:
        """Number of documents in knowledge base."""
        return self.collection.count()


# Default knowledge content for bootstrapping
DEFAULT_COACHING_KNOWLEDGE = [
    {
        "id": "communication_basics",
        "content": """
# 良いコミュニケーションの基本

1. **即時性**: 敵を見た瞬間に報告する。「敵いる」ではなく「Aショート2人」のように具体的に。
2. **簡潔さ**: 長い説明より、「敵2、ショート」のような短いコール。
3. **位置情報**: 必ず場所を含める。「プッシュしてる」→「Bメイン、プッシュ」
4. **人数**: 可能な限り敵の人数を報告。
5. **アビリティ使用**: 重要なウルティメットやアビリティの使用を報告。
""",
        "category": "basics",
    },
    {
        "id": "common_mistakes",
        "content": """
# よくあるコミュニケーションミス

1. **報告の遅延**: 撃ち合い後に報告するのでは遅い
2. **曖昧な表現**: 「あっち」「こっち」は使わない
3. **パニック報告**: 叫ぶだけで情報がない
4. **過剰報告**: 同じ情報を何度も言う
5. **報告なしの行動**: 単独行動を報告しない
""",
        "category": "mistakes",
    },
    {
        "id": "number_advantage",
        "content": """
# 人数有利での立ち回り

**2v1, 3v1の場合:**
- 焦らずタイム管理を意識
- クロスを組んで同時ピーク
- 無理に詰めない、時間を使う

**人数有利なのに負けるパターン:**
1. 1人ずつ詰めてトレード負け
2. 慢心によるピーク
3. コミュニケーション断絶
4. スパイクを意識しない
""",
        "category": "tactics",
    },
]


def bootstrap_knowledge_base(kb: CoachingKnowledgeBase) -> None:
    """Initialize knowledge base with default coaching content."""
    for doc in DEFAULT_COACHING_KNOWLEDGE:
        kb.add_document(
            content=doc["content"],
            doc_id=doc["id"],
            metadata={"category": doc["category"]},
        )
    logger.info("Bootstrapped knowledge base with default content")
