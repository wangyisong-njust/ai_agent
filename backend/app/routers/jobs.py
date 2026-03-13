# -*- coding: utf-8 -*-
import os
import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from app.agents.job_agent.agent import run_job_analysis, run_job_apply, get_application_history
from app.config import get_settings

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])
settings = get_settings()

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """上传并解析简历 PDF"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    # BUG-05 fix: 过滤路径遍历攻击，只保留文件名
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    from app.agents.job_agent.tools.resume_parser import parse_resume_file
    try:
        resume_data = await parse_resume_file(file_path)
        resume_data["file_path"] = file_path
        return {"status": "ok", "resume": resume_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AnalyzeRequest(BaseModel):
    resume_path: str
    job_url: str
    jd_text: str


@router.post("/analyze")
async def analyze_job(req: AnalyzeRequest):
    """分析 JD 与简历匹配度（不提交）"""
    try:
        result = await run_job_analysis(req.resume_path, req.job_url, req.jd_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ApplyRequest(BaseModel):
    resume_path: str
    job_url: str
    platform: str  # "linkedin" or "talentconnect"
    cover_letter: str = ""
    match_score: float = 0.0
    linkedin_email: Optional[str] = None
    # BUG-06 fix: 使用 SecretStr 防止密码被日志/repr 意外泄露
    linkedin_password: Optional[str] = None

    class Config:
        # 禁止将整个 model 序列化到日志
        json_schema_extra = {"example": {"linkedin_password": "***"}}


@router.post("/apply")
async def apply_to_job(req: ApplyRequest):
    """提交求职申请（用户确认后调用）"""
    linkedin_creds = None
    if req.linkedin_email and req.linkedin_password:
        linkedin_creds = {"email": req.linkedin_email, "password": req.linkedin_password}

    try:
        result = await run_job_apply(
            resume_path=req.resume_path,
            job_url=req.job_url,
            platform=req.platform,
            linkedin_credentials=linkedin_creds,
            cover_letter=req.cover_letter,
            match_score=req.match_score,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def application_history():
    """获取申请历史记录"""
    return await get_application_history()


class AutoApplyRequest(BaseModel):
    resume_path: str
    resume_data: dict
    keywords: str
    location: str = "Singapore"
    max_apply: int = 5
    min_score: int = 65
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_cookie: str = ""  # li_at cookie，适合 Google 账号登录用户


@router.post("/auto-apply")
async def auto_apply(req: AutoApplyRequest):
    """
    Agent 自动搜索 + 筛选 + 投递
    返回 SSE 流式进度
    """
    from app.agents.job_agent.auto_apply_agent import run_auto_apply

    import json

    async def stream():
        try:
            async for chunk in run_auto_apply(
                resume_data=req.resume_data,
                resume_path=req.resume_path,
                keywords=req.keywords,
                location=req.location,
                max_apply=req.max_apply,
                min_score=req.min_score,
                linkedin_email=req.linkedin_email,
                linkedin_password=req.linkedin_password,
                linkedin_cookie=req.linkedin_cookie,
            ):
                yield chunk
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[AutoApply] Unhandled error:\n{tb}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
