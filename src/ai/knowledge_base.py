"""
Coaching Knowledge Base.

ChromaDB-based RAG system for Valorant coaching knowledge.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Default coaching knowledge to bootstrap the knowledge base
DEFAULT_COACHING_KNOWLEDGE = [
    {
        "id": "comms_basics",
        "content": """
        効果的なコミュニケーションの基本:
        - 情報は簡潔に、5W1Hを意識して伝える
        - 敵の位置報告は具体的な場所名を使う（「ショートに1人」「ロング2人」）
        - 報告のタイミングは見た瞬間に行う（遅れると情報の価値が下がる）
        - 報告後は静かにして他のメンバーの情報を聞く
        - ラウンド開始前に作戦を共有する
        """,
        "tags": ["basics", "communication", "reporting"],
    },
    {
        "id": "callouts_timing",
        "content": """
        報告タイミングの重要性:
        - 敵を見た瞬間に報告 → チームが対応可能
        - 遅延報告（3秒以上） → 敵が移動済みの可能性
        - フラッシュ/スモーク使用の事前告知 → チームが準備可能
        - キル報告は人数と残りを明確に（「1キル、残り4」）
        """,
        "tags": ["timing", "callouts", "information"],
    },
    {
        "id": "economy_comms",
        "content": """
        エコノミー関連のコミュニケーション:
        - ラウンド開始前にチームの経済状況を共有
        - 「フルバイ」「セーブ」「ボーナス」を明確に
        - 武器リクエストは早めに行う
        - オペレーターの有無を共有（戦術に影響）
        """,
        "tags": ["economy", "buy", "coordination"],
    },
    {
        "id": "retake_comms",
        "content": """
        リテイク時のコミュニケーション:
        - 人数を確認してからリテイクを開始
        - 入るタイミングを合わせる（「3、2、1で入る」）
        - アビリティの使用順序を決める
        - 敵の位置を最新情報で共有
        - 残り時間を意識した判断
        """,
        "tags": ["retake", "coordination", "spike"],
    },
    {
        "id": "rotation_comms",
        "content": """
        ローテーション時のコミュニケーション:
        - ローテの意思を早めに共有
        - カバーの確認（「誰かミッド見てる？」）
        - 移動中の情報収集と共有
        - 到着予定時間の共有（「10秒で着く」）
        """,
        "tags": ["rotation", "movement", "coordination"],
    },
    {
        "id": "post_plant_comms",
        "content": """
        設置後のコミュニケーション:
        - 設置場所の報告
        - ポジションの共有（「俺はヘブン」）
        - 残り時間のカウントダウン
        - 敵の侵入方向の予測と共有
        - 解除音を聞いたら即報告
        """,
        "tags": ["post_plant", "spike", "defense"],
    },
    {
        "id": "negative_patterns",
        "content": """
        避けるべきコミュニケーションパターン:
        - 感情的な発言（責める、怒る）
        - 長すぎる説明（他の情報が聞こえない）
        - 曖昧な報告（「なんかいる」「あっちにいた」）
        - 死後の長い解説（生存者の邪魔）
        - 作戦の後出し批判
        """,
        "tags": ["negative", "avoid", "patterns"],
    },
    {
        "id": "clutch_comms",
        "content": """
        クラッチ状況でのコミュニケーション:
        - 静かにして音を聞かせる
        - 必要な情報のみ簡潔に
        - 敵の位置情報を優先
        - プレイヤーの判断を尊重
        - プレッシャーをかけない
        """,
        "tags": ["clutch", "silence", "support"],
    },
]


class CoachingKnowledgeBase:
    """
    ChromaDB-based knowledge base for coaching insights.
    
    Stores and retrieves coaching knowledge using semantic search.
    """
    
    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        collection_name: str = "coaching_knowledge",
    ):
        """
        Initialize knowledge base.
        
        Args:
            persist_directory: Directory for persistent storage
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        
        logger.info(f"CoachingKnowledgeBase initialized: {collection_name}")
    
    def _get_client(self):
        """Lazy load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
                
                if self.persist_directory:
                    self.persist_directory.mkdir(parents=True, exist_ok=True)
                    self._client = chromadb.PersistentClient(
                        path=str(self.persist_directory),
                        settings=Settings(anonymized_telemetry=False),
                    )
                else:
                    self._client = chromadb.Client(
                        Settings(anonymized_telemetry=False),
                    )
                
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                
                logger.info(f"ChromaDB initialized with {self._collection.count()} documents")
                
            except ImportError:
                logger.error("chromadb not installed. Run: pip install chromadb")
                raise
        
        return self._client, self._collection
    
    @property
    def document_count(self) -> int:
        """Get number of documents in collection."""
        try:
            _, collection = self._get_client()
            return collection.count()
        except:
            return 0
    
    def bootstrap(self) -> int:
        """
        Bootstrap knowledge base with default coaching knowledge.
        
        Returns:
            Number of documents added
        """
        _, collection = self._get_client()
        
        # Check if already bootstrapped
        if collection.count() > 0:
            logger.info("Knowledge base already has documents, skipping bootstrap")
            return 0
        
        # Add default knowledge
        ids = []
        documents = []
        metadatas = []
        
        for item in DEFAULT_COACHING_KNOWLEDGE:
            ids.append(item["id"])
            documents.append(item["content"].strip())
            metadatas.append({"tags": json.dumps(item["tags"])})
        
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        
        logger.info(f"Bootstrapped knowledge base with {len(ids)} documents")
        return len(ids)
    
    def add_document(
        self,
        doc_id: str,
        content: str,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Add a document to the knowledge base.
        
        Args:
            doc_id: Unique document ID
            content: Document content
            tags: Optional list of tags
            
        Returns:
            True if successful
        """
        try:
            _, collection = self._get_client()
            
            collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[{"tags": json.dumps(tags or [])}],
            )
            
            logger.info(f"Added document: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return False
    
    def query(
        self,
        query_text: str,
        n_results: int = 3,
        tags_filter: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Query the knowledge base.
        
        Args:
            query_text: Query text for semantic search
            n_results: Number of results to return
            tags_filter: Optional tags to filter by
            
        Returns:
            List of matching documents with content and metadata
        """
        try:
            _, collection = self._get_client()
            
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
            )
            
            documents = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    
                    documents.append({
                        "id": results["ids"][0][i],
                        "content": doc,
                        "metadata": metadata,
                        "relevance": 1 - distance,  # Convert distance to similarity
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def query_for_round(
        self,
        round_context: str,
        transcript_summary: str,
        n_results: int = 3,
    ) -> list[dict]:
        """
        Query for coaching insights relevant to a specific round.
        
        Args:
            round_context: Context about the round (result, economy, etc.)
            transcript_summary: Summary of communications
            n_results: Number of results
            
        Returns:
            List of relevant coaching documents
        """
        query = f"""
        ラウンド状況: {round_context}
        コミュニケーション: {transcript_summary}
        
        このラウンドに関連するコーチングアドバイスを検索
        """
        
        return self.query(query, n_results=n_results)
    
    def add_match_learning(
        self,
        match_id: str,
        round_number: int,
        transcript: str,
        analysis: str,
    ) -> bool:
        """
        Add learning from a specific match round.
        
        Args:
            match_id: Match ID
            round_number: Round number
            transcript: Round transcript
            analysis: AI analysis of the round
            
        Returns:
            True if successful
        """
        doc_id = f"match_{match_id}_r{round_number}"
        content = f"""
        [マッチ分析] Round {round_number}
        
        会話:
        {transcript}
        
        分析:
        {analysis}
        """
        
        return self.add_document(
            doc_id=doc_id,
            content=content,
            tags=["match_learning", f"round_{round_number}"],
        )

