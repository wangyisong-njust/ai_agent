# -*- coding: utf-8 -*-
"""
NUS 知识库爬虫
抓取 NUS 官网、研究生项目、NUSMods 等数据
"""
import httpx
import asyncio
import hashlib
from bs4 import BeautifulSoup
from typing import List, Dict
import json

NUS_SOURCES = [
    # 研究生项目
    {"url": "https://nusgs.nus.edu.sg/programmes/", "category": "graduate_programs", "depth": 1},
    # NUS 注册处
    {"url": "https://www.nus.edu.sg/registrar/academic-information-policies/graduate-studies", "category": "academic_policy", "depth": 0},
    # 校园生活
    {"url": "https://nus.edu.sg/osa/student-services/student-life", "category": "student_life", "depth": 0},
    # 就业指导
    {"url": "https://www.nus.edu.sg/cfg/students", "category": "career", "depth": 0},
    # 入学申请
    {"url": "https://www.nus.edu.sg/oam/apply-to-nus/graduate-admissions", "category": "admissions", "depth": 0},
]

NUSMODS_API = "https://api.nusmods.com/v2/2024-2025/moduleList.json"


async def fetch_url(url: str, timeout: int = 15) -> str:
    """抓取单个 URL 的 HTML 内容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NUSCampusBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        print(f"[Spider] Failed to fetch {url}: {e}")
        return ""


def parse_html(html: str, url: str) -> Dict:
    """解析 HTML，提取标题和正文"""
    soup = BeautifulSoup(html, "lxml")

    # 移除无用标签
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    title = soup.find("title")
    title_text = title.get_text(strip=True) if title else ""

    # 提取正文
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=lambda c: c and "content" in c.lower())
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # 清理空行
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 20]
    clean_text = "\n".join(lines[:200])  # 最多200行

    return {"title": title_text, "text": clean_text, "url": url}


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """将长文本切分为重叠的块"""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


async def scrape_nus_pages() -> List[Dict]:
    """爬取 NUS 官网页面"""
    documents = []

    for source in NUS_SOURCES:
        print(f"[Spider] Scraping {source['url']}...")
        html = await fetch_url(source["url"])
        if not html:
            continue

        parsed = parse_html(html, source["url"])
        chunks = chunk_text(parsed["text"])

        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{source['url']}_{i}".encode()).hexdigest()
            documents.append({
                "id": doc_id,
                "text": chunk,
                "metadata": {
                    "source_url": source["url"],
                    "title": parsed["title"],
                    "category": source["category"],
                    "chunk_index": i,
                }
            })

        await asyncio.sleep(1)  # 礼貌性延迟

    return documents


async def fetch_nusmods_data() -> List[Dict]:
    """获取 NUSMods 模块列表（公开 API）"""
    documents = []
    print("[Spider] Fetching NUSMods module list...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(NUSMODS_API)
            modules = resp.json()

        # 取前500个模块（demo 用）
        for mod in modules[:500]:
            code = mod.get("moduleCode", "")
            title = mod.get("title", "")
            text = f"Module {code}: {title}"

            doc_id = hashlib.md5(f"nusmods_{code}".encode()).hexdigest()
            documents.append({
                "id": doc_id,
                "text": text,
                "metadata": {
                    "source_url": f"https://nusmods.com/courses/{code}",
                    "title": f"{code} {title}",
                    "category": "module",
                    "module_code": code,
                }
            })

    except Exception as e:
        print(f"[Spider] NUSMods fetch failed: {e}")

    return documents


async def run_ingestion():
    """完整的知识库摄入流程"""
    from app.agents.knowledge_agent.vectorstore.chroma_client import add_documents

    all_docs = []

    # 1. 爬取 NUS 官网
    nus_docs = await scrape_nus_pages()
    all_docs.extend(nus_docs)
    print(f"[Spider] Scraped {len(nus_docs)} NUS page chunks")

    # 2. NUSMods 模块数据
    mod_docs = await fetch_nusmods_data()
    all_docs.extend(mod_docs)
    print(f"[Spider] Fetched {len(mod_docs)} NUSMods module entries")

    # 3. 存入 ChromaDB
    if all_docs:
        add_documents(all_docs)
        print(f"[Spider] Total: {len(all_docs)} documents ingested into ChromaDB")

    return len(all_docs)


if __name__ == "__main__":
    asyncio.run(run_ingestion())
