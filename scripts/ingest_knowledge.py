"""
一键运行 NUS 知识库摄入
在 backend/ 目录下执行: python ../scripts/ingest_knowledge.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.agents.knowledge_agent.ingestion.nus_spider import run_ingestion

if __name__ == "__main__":
    count = asyncio.run(run_ingestion())
    print(f"\nIngestion complete! {count} documents in ChromaDB.")
