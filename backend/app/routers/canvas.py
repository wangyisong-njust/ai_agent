# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from app.agents.canvas_agent.agent import run_canvas_sync
from app.agents.canvas_agent.tools.gcal_pusher import get_oauth_flow
from app.database import AsyncSessionLocal
from app.models.canvas_sync import CanvasCourse, CanvasAssignment, CanvasAnnouncement
from app.config import get_settings

router = APIRouter(prefix="/api/canvas", tags=["Canvas"])
settings = get_settings()


class SyncRequest(BaseModel):
    canvas_token: str
    push_to_calendar: bool = False
    gcal_credentials: Optional[dict] = None


@router.post("/sync")
async def sync_canvas(req: SyncRequest):
    """触发 Canvas 数据同步（Canvas Agent）"""
    try:
        result = await run_canvas_sync(
            canvas_token=req.canvas_token,
            gcal_credentials=req.gcal_credentials,
            push_to_calendar=req.push_to_calendar,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/courses")
async def get_courses():
    async with AsyncSessionLocal() as db:
        courses = await db.scalars(select(CanvasCourse))
        return [{"id": c.canvas_id, "name": c.name, "code": c.course_code} for c in courses.all()]


@router.get("/assignments")
async def get_assignments():
    async with AsyncSessionLocal() as db:
        assignments = await db.scalars(
            select(CanvasAssignment).order_by(CanvasAssignment.due_at)
        )
        return [
            {
                "id": a.canvas_id,
                "course": a.course_name,
                "name": a.name,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "points": a.points_possible,
                "gcal_synced": bool(a.gcal_event_id),
            }
            for a in assignments.all()
        ]


@router.get("/announcements")
async def get_announcements():
    async with AsyncSessionLocal() as db:
        announcements = await db.scalars(
            select(CanvasAnnouncement).order_by(CanvasAnnouncement.posted_at.desc())
        )
        return [
            {
                "id": a.canvas_id,
                "course": a.course_name,
                "title": a.title,
                "summary": a.summary,
                "posted_at": a.posted_at.isoformat() if a.posted_at else None,
                "is_read": a.is_read,
            }
            for a in announcements.all()
        ]


@router.get("/gcal/auth")
async def start_gcal_auth():
    """发起 Google Calendar OAuth2 授权"""
    flow = get_oauth_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    return {"auth_url": auth_url, "state": state}


@router.get("/oauth2callback")
async def gcal_oauth_callback(code: str = Query(...), state: str = Query("")):
    """Google OAuth2 回调"""
    flow = get_oauth_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
    }
