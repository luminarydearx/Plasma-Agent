from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class VectorDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    embedding: Optional[list[float]] = None


class VectorSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    document: VectorDocument
    score: float = Field(ge=0.0, le=1.0)


class VectorStore:
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "plasma_memories",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        from chromadb import PersistentClient
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer

        if persist_directory:
            path = Path(persist_directory).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            self._client = PersistentClient(
                path=str(path),
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            from chromadb import Client
            self._client = Client()

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = SentenceTransformer(embedding_model)

    def add_document(
        self,
        content: str,
        metadata: Optional[dict] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        if doc_id is None:
            doc_id = str(uuid4())

        embedding = self._embedder.encode(content).tolist()

        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata or {}],
        )

        return doc_id

    def add_documents(
        self,
        documents: list[VectorDocument],
    ) -> list[str]:
        if not documents:
            return []

        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        embeddings = self._embedder.encode(contents).tolist()

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
        )

        return ids

    def search(
        self,
        query: str,
        limit: int = 10,
        where: Optional[dict] = None,
    ) -> list[VectorSearchResult]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        query_embedding = self._embedder.encode(query).tolist()

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i] if results["documents"] else ""
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0

                score = 1.0 - distance

                doc = VectorDocument(
                    id=doc_id,
                    content=content,
                    metadata=metadata,
                )
                search_results.append(VectorSearchResult(document=doc, score=score))

        return search_results

    def delete(self, doc_id: str) -> bool:
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def get_document(self, doc_id: str) -> Optional[VectorDocument]:
        try:
            results = self._collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            )
            if results["ids"]:
                content = results["documents"][0] if results["documents"] else ""
                metadata = results["metadatas"][0] if results["metadatas"] else {}
                return VectorDocument(
                    id=doc_id,
                    content=content,
                    metadata=metadata,
                )
            return None
        except Exception:
            return None

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        collection_name = self._collection.name
        self._client.delete_collection(collection_name)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        from plasmaagent.core.config import get_settings
        settings = get_settings()
        _vector_store = VectorStore(
            persist_directory=settings.vector_store_path,
            embedding_model=settings.embedding_model,
        )
    return _vector_store
