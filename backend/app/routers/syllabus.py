# -*- coding: utf-8 -*-
import os
import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from app.agents.syllabus_agent.agent import (
    run_syllabus_extract,
    run_syllabus_sync,
    get_syllabus_events,
)

router = APIRouter(prefix="/api/syllabus", tags=["Syllabus Agent"])

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".pdf"}


def _pdf_to_images(pdf_path: str) -> list[str]:
    """将 PDF 每页转为 PNG，返回图片路径列表"""
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    image_paths = []
    for i, page in enumerate(doc):
        mat = fitz.Matrix(2.0, 2.0)  # 2x 放大保证清晰度
        pix = page.get_pixmap(matrix=mat)
        img_path = pdf_path.replace(".pdf", f"_page{i+1}.png")
        pix.save(img_path)
        image_paths.append(img_path)
    doc.close()
    return image_paths


@router.post("/upload")
async def upload_syllabus(file: UploadFile = File(...)):
    """
    上传 Syllabus 图片或 PDF，调用 WaveSpeed Vision 提取事件
    PDF 会自动转换为图片（每页单独分析，结果合并）
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Accepted formats: image (JPG/PNG/WEBP) or PDF")

    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, f"syllabus_{safe_name}")

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        if ext == ".pdf":
            # PDF → 逐页转图片 → 分别提取事件 → 合并去重
            image_paths = _pdf_to_images(file_path)
            if not image_paths:
                raise HTTPException(status_code=400, detail="PDF has no pages")

            all_events = []
            all_db_ids = []
            for img_path in image_paths:
                page_result = await run_syllabus_extract(img_path)
                all_events.extend(page_result.get("events", []))
                all_db_ids.extend(page_result.get("db_ids", []))

            return {"events": all_events, "db_ids": all_db_ids, "pages": len(image_paths)}
        else:
            result = await run_syllabus_extract(file_path)
            return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SyncRequest(BaseModel):
    event_ids: List[int]
    gcal_credentials: dict


@router.post("/sync-to-calendar")
async def sync_to_calendar(req: SyncRequest):
    """
    用户确认事件后，将选定事件推送到 Google Calendar
    """
    if not req.event_ids:
        raise HTTPException(status_code=400, detail="No event IDs provided")
    try:
        result = await run_syllabus_sync(req.event_ids, req.gcal_credentials)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def list_events(confirmed_only: bool = False):
    """获取所有已提取的 Syllabus 事件"""
    return await get_syllabus_events(confirmed_only=confirmed_only)
