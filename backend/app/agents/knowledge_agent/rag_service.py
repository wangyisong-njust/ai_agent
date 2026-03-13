# -*- coding: utf-8 -*-
"""
RAG 服务 - NUS 知识问答核心
混合检索：ChromaDB 语义搜索 + BM25 关键词搜索
通过 WaveSpeed AI 生成流式答案
"""
from typing import AsyncGenerator, List, Dict
from rank_bm25 import BM25Okapi
from app.agents.knowledge_agent.vectorstore.chroma_client import query_similar, get_collection
from app.services.wavespeed_service import chat_stream

# 缓存 BM25 索引（按需构建）
_bm25_cache = None
_bm25_corpus = None
_bm25_doc_count = 0  # BUG-09 fix: 记录构建时的文档数，用于失效检测


def invalidate_bm25_cache():
    """BUG-09 fix: 知识库更新后调用此函数使 BM25 缓存失效"""
    global _bm25_cache, _bm25_corpus, _bm25_doc_count
    _bm25_cache = None
    _bm25_corpus = None
    _bm25_doc_count = 0


def _get_bm25():
    """懒加载 BM25 索引"""
    global _bm25_cache, _bm25_corpus, _bm25_doc_count
    if _bm25_cache is None:
        collection = get_collection()
        results = collection.get(include=["documents", "metadatas"])
        docs = results.get("documents", [])
        if docs:
            tokenized = [doc.lower().split() for doc in docs]
            _bm25_cache = BM25Okapi(tokenized)
            _bm25_corpus = list(zip(docs, results.get("metadatas", [{}] * len(docs))))
            _bm25_doc_count = len(docs)
    return _bm25_cache, _bm25_corpus


def _bm25_search(query: str, n: int = 5) -> List[Dict]:
    """BM25 关键词搜索"""
    bm25, corpus = _get_bm25()
    if not bm25 or not corpus:
        return []

    scores = bm25.get_scores(query.lower().split())
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]

    results = []
    for idx in top_indices:
        if idx < len(corpus) and scores[idx] > 0:
            text, meta = corpus[idx]
            results.append({"text": text, "metadata": meta, "bm25_score": scores[idx]})
    return results


def _hybrid_merge(semantic_results: List[Dict], bm25_results: List[Dict], k: int = 5) -> List[Dict]:
    """
    Reciprocal Rank Fusion (RRF) 融合语义和关键词搜索结果
    """
    rrf_scores = {}
    doc_map = {}
    constant = 60

    for rank, doc in enumerate(semantic_results):
        key = doc["text"][:100]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (rank + 1 + constant)
        doc_map[key] = doc

    for rank, doc in enumerate(bm25_results):
        key = doc["text"][:100]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (rank + 1 + constant)
        if key not in doc_map:
            doc_map[key] = doc

    # BUG-02 fix: lambda 参数改为 x，避免遮蔽外层参数 k
    sorted_keys = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys[:k]]


def _build_context(retrieved_docs: List[Dict]) -> str:
    """构建 RAG 上下文"""
    context_parts = []
    for i, doc in enumerate(retrieved_docs):
        meta = doc.get("metadata", {})
        source = meta.get("source_url", "")
        title = meta.get("title", "")
        context_parts.append(f"[Source {i+1}] {title}\n{doc['text']}\nURL: {source}")
    return "\n\n---\n\n".join(context_parts)


async def answer_question(
    question: str,
    chat_history: List[Dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    RAG 问答流程（流式输出）
    1. 混合检索相关文档
    2. 构建 prompt
    3. WaveSpeed AI 流式生成答案
    """
    # Step 1: 混合检索
    semantic_docs = query_similar(question, n_results=6)
    bm25_docs = _bm25_search(question, n=4)
    merged_docs = _hybrid_merge(semantic_docs, bm25_docs, k=5)

    # Step 2: 构建 prompt
    context = _build_context(merged_docs)
    sources = list({doc.get("metadata", {}).get("source_url", "") for doc in merged_docs if doc.get("metadata", {}).get("source_url")})

    system_prompt = """You are a friendly and intelligent NUS (National University of Singapore) campus assistant.

Rules:
- For greetings or casual conversation (hi, hello, how are you, etc.), respond naturally and warmly. Do NOT reference any documents.
- For NUS-related questions, answer based on the provided context. Cite source URLs when referencing specific information.
- If the context is not relevant to the question, ignore it and answer from general knowledge.
- If you genuinely don't know something NUS-specific, say so honestly instead of guessing."""

    messages = [{"role": "system", "content": system_prompt}]

    # 加入对话历史
    if chat_history:
        messages.extend(chat_history[-6:])  # 最近3轮对话

    # 只有检索到相关文档时才注入 context
    if merged_docs and context.strip():
        user_content = f"Reference context (use only if relevant to the question):\n{context}\n\nQuestion: {question}"
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})

    # Step 3: WaveSpeed AI 流式回答
    async for token in chat_stream(messages):
        yield token

    # 只有问 NUS 相关内容且有来源时才显示 Sources
    if sources and merged_docs:
        # 过滤掉相关性太低的来源（distance > 1.0 说明基本不相关）
        relevant_docs = [d for d in merged_docs if d.get("distance", 0) < 0.8]
        relevant_sources = list({d.get("metadata", {}).get("source_url", "") for d in relevant_docs if d.get("metadata", {}).get("source_url")})
        if relevant_sources:
            yield f"\n\n---\n**Sources:**\n" + "\n".join(f"- {s}" for s in relevant_sources[:3])


async def get_knowledge_stats() -> Dict:
    """获取知识库统计"""
    from app.agents.knowledge_agent.vectorstore.chroma_client import get_collection_count
    return {
        "total_documents": get_collection_count(),
        "embedding_model": "all-MiniLM-L6-v2",
        "llm": "WaveSpeed AI",
    }
