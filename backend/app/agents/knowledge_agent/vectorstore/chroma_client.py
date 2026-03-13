# -*- coding: utf-8 -*-
"""
ChromaDB 向量存储客户端
NUS 知识库的持久化存储
"""
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from functools import lru_cache
from pathlib import Path

CHROMA_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "nus_knowledge"
EMBED_MODEL = "all-MiniLM-L6-v2"  # 本地免费模型，384 维


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.PersistentClient:
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_documents(docs: list[dict]):
    """
    批量添加文档到向量库
    docs: [{"id": str, "text": str, "metadata": dict}]
    """
    collection = get_collection()
    model = get_embedding_model()

    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    metadatas = [d.get("metadata", {}) for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print(f"[ChromaDB] Upserted {len(docs)} documents")


def query_similar(query_text: str, n_results: int = 5) -> list[dict]:
    """
    语义相似度搜索
    返回 [{"text": str, "metadata": dict, "distance": float}]
    """
    collection = get_collection()
    model = get_embedding_model()

    query_embedding = model.encode([query_text]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []
    dists = results["distances"][0] if results["distances"] else []

    for text, meta, dist in zip(docs, metas, dists):
        output.append({"text": text, "metadata": meta, "distance": dist})

    return output


def get_collection_count() -> int:
    return get_collection().count()
