# -*- coding: utf-8 -*-
"""
Schedule Agent Router
统一处理 Canvas + Syllabus 的本地日历同步和邮件提醒
"""
import os
import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from app.agents.canvas_agent.agent import run_canvas_sync
from app.agents.syllabus_agent.agent import run_syllabus_extract
from app.agents.schedule_agent.ics_builder import build_ics
from app.agents.schedule_agent.email_reminder import send_schedule_email
from app.agents.schedule_agent import gcal_pusher
from app.database import AsyncSessionLocal
from app.models.canvas_sync import CanvasAssignment, CanvasAnnouncement
from app.models.syllabus_event import SyllabusEvent
from sqlalchemy import select
from app.config import get_settings
settings = get_settings()

router = APIRouter(prefix="/api/schedule", tags=["Schedule Agent"])

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── 从数据库读取所有待同步事件 ──────────────────────────────

async def _get_all_events() -> List[dict]:
    """合并 Canvas 作业 + Syllabus 事件，统一格式"""
    events = []
    async with AsyncSessionLocal() as db:
        # Canvas 作业
        assignments = await db.scalars(
            select(CanvasAssignment).order_by(CanvasAssignment.due_at)
        )
        for a in assignments.all():
            if a.due_at:
                events.append({
                    "title": f"[{a.course_name}] {a.name}",
                    "start": a.due_at,
                    "end": a.due_at + timedelta(hours=1),
                    "description": f"Course: {a.course_name}\nPoints: {a.points_possible}",
                    "event_type": "assignment",
                    "source": "canvas",
                    "url": "",
                })

        # Syllabus 事件
        syllabus_events = await db.scalars(
            select(SyllabusEvent).order_by(SyllabusEvent.start_time)
        )
        for s in syllabus_events.all():
            if s.start_time:
                events.append({
                    "title": s.event_name,
                    "start": s.start_time,
                    "end": s.end_time or (s.start_time + timedelta(hours=1)),
                    "description": s.description or "",
                    "event_type": s.event_type,
                    "source": "syllabus",
                    "url": "",
                })

    return events


# ── API ────────────────────────────────────────────────────

@router.get("/events")
async def get_all_events():
    """获取所有 Canvas + Syllabus 合并后的事件列表"""
    events = await _get_all_events()
    return [
        {
            **e,
            "start": e["start"].isoformat() if e["start"] else None,
            "end": e["end"].isoformat() if e["end"] else None,
        }
        for e in events
    ]


@router.get("/download-ics")
async def download_ics():
    """下载合并后的 .ics 日历文件（可直接导入本地日历）"""
    events = await _get_all_events()
    if not events:
        raise HTTPException(status_code=404, detail="No events to export. Sync Canvas or upload a syllabus first.")

    ics_bytes = build_ics(events)
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="nus_schedule.ics"'},
    )


class SyncRequest(BaseModel):
    canvas_token: str


@router.post("/sync-canvas")
async def sync_canvas_and_export(req: SyncRequest):
    """Canvas 同步 → 生成 .ics → 准备就绪供下载/邮件"""
    try:
        result = await run_canvas_sync(
            canvas_token=req.canvas_token,
            push_to_calendar=False,  # 不再依赖 Google Calendar OAuth
        )
        events = await _get_all_events()
        return {
            **result,
            "total_events": len(events),
            "ics_ready": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"}


@router.post("/upload-syllabus")
async def upload_syllabus(file: UploadFile = File(...)):
    """上传课表图片/PDF → Vision 解析 → 存入数据库 → 准备就绪供下载/邮件"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Accepted: image (JPG/PNG/WEBP) or PDF")

    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, f"syllabus_{safe_name}")
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(await file.read())

    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(file_path)
            all_events, all_ids = [], []
            for i, page in enumerate(doc):
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                img_path = file_path.replace(".pdf", f"_p{i+1}.png")
                pix.save(img_path)
                r = await run_syllabus_extract(img_path)
                all_events.extend(r.get("events", []))
                all_ids.extend(r.get("db_ids", []))
            doc.close()
            result = {"events": all_events, "db_ids": all_ids}
        else:
            result = await run_syllabus_extract(file_path)

        total_events = await _get_all_events()
        return {
            **result,
            "total_events": len(total_events),
            "ics_ready": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class EmailRequest(BaseModel):
    to_email: str
    event_ids: Optional[List[str]] = None  # None = 全部


@router.post("/send-email")
async def send_reminder_email(req: EmailRequest):
    """发送 .ics 附件 + HTML 日程摘要到指定邮箱"""
    events = await _get_all_events()
    if not events:
        raise HTTPException(status_code=404, detail="No events to send. Sync Canvas or upload a syllabus first.")

    ics_bytes = build_ics(events)
    result = await send_schedule_email(
        to_email=req.to_email,
        events=events,
        ics_bytes=ics_bytes,
        source_label="Canvas + Syllabus",
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Email failed: {result['error']}")

    return {"success": True, "sent_to": req.to_email, "event_count": len(events)}


# ── Google Calendar OAuth + Auto-Push ─────────────────────────────────────

@router.get("/gcal/status")
async def gcal_status():
    """Check if Google Calendar is authorized"""
    return {"authorized": gcal_pusher.is_authorized()}


@router.get("/gcal/auth-url")
async def gcal_auth_url():
    """Return the OAuth URL for user to authorize Google Calendar access"""
    url = gcal_pusher.get_auth_url(
        client_id=settings.google_client_id,
        redirect_uri=settings.google_gcal_redirect_uri,
    )
    return {"url": url}


@router.get("/gcal/callback")
async def gcal_oauth_callback(code: str):
    """Handle OAuth callback, exchange code for tokens, then redirect to frontend"""
    from fastapi.responses import HTMLResponse
    try:
        await gcal_pusher.exchange_code(
            code=code,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_gcal_redirect_uri,
        )
        # Return HTML that closes the popup and notifies the opener
        return HTMLResponse("""
        <html><body>
        <script>
          if (window.opener) {
            window.opener.postMessage({type: 'gcal_authorized'}, '*');
            window.close();
          } else {
            document.body.innerHTML = '<h3>✅ Google Calendar connected! You can close this tab.</h3>';
          }
        </script>
        <h3>✅ Google Calendar connected! Closing...</h3>
        </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"<h3>❌ Authorization failed: {e}</h3>")


@router.post("/gcal/push")
async def push_to_gcal():
    """Agent 自动推送所有事件到 Google Calendar"""
    if not gcal_pusher.is_authorized():
        raise HTTPException(status_code=401, detail="Google Calendar not authorized. Please connect first.")

    events = await _get_all_events()
    if not events:
        raise HTTPException(status_code=404, detail="No events to push. Sync Canvas or upload a syllabus first.")

    pushed, skipped, errors = await gcal_pusher.push_events_to_gcal(
        events=events,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return {
        "success": True,
        "pushed": pushed,
        "skipped": skipped,
        "total": len(events),
        "errors": errors[:5],  # 最多返回5条错误信息
    }


@router.post("/gcal/disconnect")
async def gcal_disconnect():
    """Revoke Google Calendar authorization"""
    gcal_pusher.clear_token()
    return {"disconnected": True}
