# -*- coding: utf-8 -*-
"""
Job Agent - OpenClaw 协作 Agent 之一
职责：简历解析 → JD 匹配分析 → 自动投递
由 OpenClaw Orchestrator 调度
"""
from typing import Dict, Any, List
from app.agents.job_agent.tools.resume_parser import parse_resume_file
from app.agents.job_agent.tools.linkedin_browser import LinkedInApplicator
from app.services.wavespeed_service import analyze_jd_resume
from app.database import AsyncSessionLocal
from app.models.job_application import JobApplication


async def run_job_analysis(resume_path: str, job_url: str, jd_text: str) -> Dict[str, Any]:
    """
    分析阶段（不提交）：解析简历 + 分析 JD 匹配度
    用于让用户在提交前确认
    """
    print(f"[JobAgent] Analyzing resume vs JD...")

    resume_data = await parse_resume_file(resume_path)
    analysis = await analyze_jd_resume(jd_text, resume_data)

    return {
        "resume": resume_data,
        "analysis": analysis,
        "job_url": job_url,
        "recommendation": analysis.get("recommendation", "skip"),
        "match_score": analysis.get("score", 0),
        "cover_letter": analysis.get("cover_letter", ""),
    }


async def run_job_apply(
    resume_path: str,
    job_url: str,
    platform: str,
    linkedin_credentials: Dict | None = None,
    cover_letter: str = "",
    match_score: float = 0.0,
) -> Dict[str, Any]:
    """
    提交阶段：执行实际投递（需用户已确认）
    """
    print(f"[JobAgent] Applying to {job_url} on {platform}...")

    result = {
        "platform": platform,
        "job_url": job_url,
        "status": "failed",
        "company": "",
        "role": "",
    }

    if platform == "linkedin" and linkedin_credentials:
        applicator = LinkedInApplicator()
        await applicator.start(headless=False)
        try:
            logged_in = await applicator.login(
                linkedin_credentials["email"],
                linkedin_credentials["password"],
            )
            if not logged_in:
                result["status"] = "login_failed"
                return result

            apply_result = await applicator.apply_easy_apply(job_url, {"file_path": resume_path})
            result.update(apply_result)
        finally:
            await applicator.stop()

    # 记录到数据库
    async with AsyncSessionLocal() as db:
        app_record = JobApplication(
            platform=platform,
            company=result.get("company", ""),
            role=result.get("role", ""),
            job_url=job_url,
            status=result.get("status", "failed"),
            match_score=match_score,
            cover_letter=cover_letter,
            notes=result.get("error", ""),
        )
        db.add(app_record)
        await db.commit()
        await db.refresh(app_record)
        result["db_id"] = app_record.id

    return result


async def get_application_history() -> List[Dict]:
    """获取所有申请记录"""
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        records = await db.scalars(
            select(JobApplication).order_by(JobApplication.applied_at.desc())
        )
        return [
            {
                "id": r.id,
                "platform": r.platform,
                "company": r.company,
                "role": r.role,
                "job_url": r.job_url,
                "status": r.status,
                "match_score": r.match_score,
                "applied_at": r.applied_at.isoformat() if r.applied_at else None,
            }
            for r in records.all()
        ]
