# -*- coding: utf-8 -*-
"""
Auto Apply Agent - OpenClaw Job Agent 核心
完整流程：搜索职位 → AI 筛选匹配 → 自动投递 → 记录结果
通过 SSE 流式汇报每一步进度给前端
"""
import asyncio
import json
import random
from typing import AsyncGenerator, Dict, Any
from app.agents.job_agent.tools.linkedin_searcher import search_linkedin_jobs
from app.agents.job_agent.tools.linkedin_browser import LinkedInApplicator
from app.services.wavespeed_service import analyze_jd_resume
from app.database import AsyncSessionLocal
from app.models.job_application import JobApplication

# ── Demo job data (used when LinkedIn scraping is blocked) ────────────────
_DEMO_JOBS = [
    {
        "title": "Software Engineer Intern",
        "company": "Grab",
        "location": "Singapore",
        "url": "https://www.linkedin.com/jobs/view/demo-grab-swe",
        "jd_text": (
            "We are looking for a Software Engineer Intern to join Grab's engineering team. "
            "You will work on backend services using Python, Go, and Kubernetes. "
            "Requirements: Strong CS fundamentals, experience with REST APIs, "
            "familiarity with cloud platforms (AWS/GCP). Python or Go experience preferred."
        ),
    },
    {
        "title": "AI/ML Engineer Intern",
        "company": "Sea Group (Shopee)",
        "location": "Singapore",
        "url": "https://www.linkedin.com/jobs/view/demo-sea-ml",
        "jd_text": (
            "Join Sea Group's AI team to build recommendation systems and NLP pipelines. "
            "Requirements: Python, PyTorch or TensorFlow, experience with large-scale data. "
            "Knowledge of LLMs, RAG pipelines, or MLOps is a strong plus."
        ),
    },
    {
        "title": "Full Stack Developer Intern",
        "company": "Bytedance (TikTok)",
        "location": "Singapore",
        "url": "https://www.linkedin.com/jobs/view/demo-bytedance-fs",
        "jd_text": (
            "Build user-facing features for TikTok's creator platform. "
            "React/TypeScript for frontend, Python/FastAPI or Node.js for backend. "
            "Experience with WebSocket, SSE, or real-time systems is a plus."
        ),
    },
    {
        "title": "Data Analyst Intern",
        "company": "DBS Bank",
        "location": "Singapore",
        "url": "https://www.linkedin.com/jobs/view/demo-dbs-da",
        "jd_text": (
            "Support DBS's digital banking analytics team. "
            "SQL, Python (pandas, numpy), data visualisation (Tableau or PowerBI). "
            "Statistics background preferred. Experience with A/B testing is a plus."
        ),
    },
    {
        "title": "Backend Engineer Intern",
        "company": "Razer",
        "location": "Singapore",
        "url": "https://www.linkedin.com/jobs/view/demo-razer-be",
        "jd_text": (
            "Build gaming platform backend services at Razer. "
            "Java or Python microservices, PostgreSQL, Redis, Docker. "
            "Interest in gaming or e-sports products is a plus."
        ),
    },
]


def _sse(event_type: str, data: Any) -> str:
    """格式化 SSE 消息"""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


async def run_auto_apply(
    resume_data: Dict,
    resume_path: str,
    keywords: str,
    location: str,
    max_apply: int,
    min_score: int,
    linkedin_email: str = "",
    linkedin_password: str = "",
    linkedin_cookie: str = "",
) -> AsyncGenerator[str, None]:
    """
    Agent 主流程，yield SSE 字符串给前端

    步骤：
    1. 搜索 LinkedIn 职位
    2. WaveSpeed AI 逐个分析匹配度
    3. 过滤低分职位
    4. Playwright 自动投递高匹配职位
    5. 记录结果到数据库
    """

    # ── Step 1: 搜索职位 ────────────────────────────────────
    yield _sse("step", {"step": 1, "message": f"🔍 正在搜索 LinkedIn: {keywords} in {location}..."})

    demo_mode = False
    try:
        jobs = await search_linkedin_jobs(keywords, location, max_results=max_apply * 3)
    except Exception as e:
        jobs = []

    if not jobs:
        # LinkedIn anti-bot triggered — switch to demo mode
        demo_mode = True
        yield _sse("step", {"step": 1, "message": "⚠️ LinkedIn 反爬虫拦截，切换 Demo 模式展示完整流程..."})
        await asyncio.sleep(0.5)
        jobs = _DEMO_JOBS[:max(max_apply * 2, 5)]
        # Shuffle and filter by keyword relevance
        kw_lower = keywords.lower()
        scored = [(j, sum(1 for w in kw_lower.split() if w in j["title"].lower() + j["jd_text"].lower())) for j in jobs]
        scored.sort(key=lambda x: x[1], reverse=True)
        jobs = [j for j, _ in scored]

    yield _sse("step", {"step": 1, "message": f"✅ 找到 {len(jobs)} 个 Easy Apply 职位{'（Demo 数据）' if demo_mode else ''}"})
    yield _sse("jobs_found", {"count": len(jobs), "jobs": [
        {"title": j["title"], "company": j["company"], "url": j["url"]} for j in jobs
    ]})

    # ── Step 2: AI 逐个分析匹配度 ───────────────────────────
    # 去重（按 URL）
    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        if job["url"] not in seen_urls:
            seen_urls.add(job["url"])
            unique_jobs.append(job)
    jobs = unique_jobs
    yield _sse("step", {"step": 2, "message": f"🤖 WaveSpeed AI 分析 {len(jobs)} 个职位匹配度..."})

    qualified = []
    for i, job in enumerate(jobs):
        # 没有 JD 文本时用标题+公司兜底
        if not job.get("jd_text"):
            job["jd_text"] = f"Position: {job['title']}\nCompany: {job['company']}\nLocation: {job.get('location', '')}"
        try:
            yield _sse("analyzing", {"index": i + 1, "total": len(jobs), "title": job["title"], "company": job["company"]})
            analysis = await analyze_jd_resume(job["jd_text"], resume_data)
            score = analysis.get("score", 0)
            job["analysis"] = analysis
            job["match_score"] = score
            job["cover_letter"] = analysis.get("cover_letter", "")

            yield _sse("analyzed", {
                "title": job["title"],
                "company": job["company"],
                "score": score,
                "recommendation": analysis.get("recommendation", "skip"),
            })

            if score >= min_score and analysis.get("recommendation") == "apply":
                qualified.append(job)
                if len(qualified) >= max_apply:
                    break

            # 避免 WaveSpeed API 429 限速，每次分析后稍作等待
            await asyncio.sleep(2)

        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg:
                yield _sse("warn", {"message": f"⚠ API 限速，等待 10 秒后继续..."})
                await asyncio.sleep(10)
                # 重试一次
                try:
                    analysis = await analyze_jd_resume(job["jd_text"], resume_data)
                    score = analysis.get("score", 0)
                    job["match_score"] = score
                    job["cover_letter"] = analysis.get("cover_letter", "")
                    yield _sse("analyzed", {"title": job["title"], "company": job["company"], "score": score, "recommendation": analysis.get("recommendation", "skip")})
                    if score >= min_score and analysis.get("recommendation") == "apply":
                        qualified.append(job)
                except Exception:
                    yield _sse("warn", {"message": f"跳过 {job['title']}（重试失败）"})
            else:
                yield _sse("warn", {"message": f"跳过 {job['title']}: {err_msg[:80]}"})
            continue

    yield _sse("step", {"step": 2, "message": f"✅ 筛选出 {len(qualified)} 个高匹配职位（≥{min_score}分）"})

    if not qualified:
        yield _sse("done", {
            "message": f"未找到匹配度 ≥{min_score} 的职位，建议降低分数要求或更换关键词",
            "applied": 0, "failed": 0, "results": []
        })
        return

    # ── Step 3: 自动投递 ────────────────────────────────────
    yield _sse("step", {"step": 3, "message": f"📤 开始自动投递 {len(qualified)} 个职位..."})

    applied = 0
    failed = 0
    results = []

    if demo_mode:
        # Demo mode: simulate apply without browser
        yield _sse("step", {"step": 3, "message": "🤖 Demo 模式：模拟 Playwright 自动填表投递..."})
        await asyncio.sleep(0.8)
        yield _sse("step", {"step": 3, "message": "✅ LinkedIn 登录成功（Demo）"})

        for job in qualified:
            yield _sse("applying", {"title": job["title"], "company": job["company"], "score": job["match_score"]})
            await asyncio.sleep(random.uniform(1.2, 2.5))
            # 90% success rate in demo
            status = "applied" if random.random() < 0.9 else "already_applied"
            async with AsyncSessionLocal() as db:
                record = JobApplication(
                    platform="linkedin",
                    company=job["company"],
                    role=job["title"],
                    job_url=job["url"],
                    status=status,
                    match_score=job["match_score"],
                    cover_letter=job.get("cover_letter", ""),
                    notes="demo mode" if demo_mode else "",
                )
                db.add(record)
                await db.commit()
            if status == "applied":
                applied += 1
                yield _sse("applied", {"title": job["title"], "company": job["company"], "score": job["match_score"]})
            else:
                failed += 1
                yield _sse("skipped", {"title": job["title"], "company": job["company"], "reason": "Already applied"})
            results.append({"title": job["title"], "company": job["company"], "score": job["match_score"], "status": status})
    else:
        applicator = LinkedInApplicator()
        await applicator.start(headless=True)
        try:
            yield _sse("step", {"step": 3, "message": "🔐 正在登录 LinkedIn..."})
            logged_in = await applicator.login(
                email=linkedin_email,
                password=linkedin_password,
                li_at_cookie=linkedin_cookie,
            )
            if not logged_in:
                yield _sse("error", {"message": "LinkedIn 登录失败，请检查账号密码或 li_at cookie"})
                return
            yield _sse("step", {"step": 3, "message": "✅ LinkedIn 登录成功"})

            for job in qualified:
                yield _sse("applying", {"title": job["title"], "company": job["company"], "score": job["match_score"]})
                try:
                    apply_result = await applicator.apply_easy_apply(
                        job["url"],
                        {"file_path": resume_path, "phone": resume_data.get("phone", "")},
                    )
                    status = apply_result.get("status", "failed")
                    async with AsyncSessionLocal() as db:
                        record = JobApplication(
                            platform="linkedin",
                            company=job["company"],
                            role=job["title"],
                            job_url=job["url"],
                            status=status,
                            match_score=job["match_score"],
                            cover_letter=job.get("cover_letter", ""),
                            notes=apply_result.get("error", ""),
                        )
                        db.add(record)
                        await db.commit()
                    if status == "applied":
                        applied += 1
                        yield _sse("applied", {"title": job["title"], "company": job["company"], "score": job["match_score"]})
                    else:
                        failed += 1
                        yield _sse("skipped", {"title": job["title"], "company": job["company"], "reason": apply_result.get("error", status)})
                    results.append({"title": job["title"], "company": job["company"], "score": job["match_score"], "status": status})
                    await asyncio.sleep(random.uniform(3, 6))
                except Exception as e:
                    failed += 1
                    yield _sse("warn", {"message": f"{job['title']} 投递出错: {str(e)}"})
        finally:
            await applicator.stop()

    yield _sse("done", {
        "message": f"✅ Agent 完成！成功投递 {applied} 个，跳过 {failed} 个",
        "applied": applied,
        "failed": failed,
        "results": results,
    })


