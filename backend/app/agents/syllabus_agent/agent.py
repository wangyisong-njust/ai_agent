# -*- coding: utf-8 -*-
"""
Syllabus Agent - OpenClaw 协作 Agent 之一
职责：课程大纲图片 → Vision 解析 → 结构化事件 → Google Calendar
由 OpenClaw Orchestrator 调度
"""
import base64
import os
from datetime import datetime
from typing import Dict, Any, List
from app.services.wavespeed_service import extract_syllabus_events
from app.agents.canvas_agent.tools.gcal_pusher import get_calendar_service, push_assignment_to_calendar
from app.database import AsyncSessionLocal
from app.models.syllabus_event import SyllabusEvent
from sqlalchemy import select


async def _upload_image_to_data_url(file_path: str) -> str:
    """
    将本地图片转换为 base64 data URL（供 Vision API 使用）
    WaveSpeed Vision 接受 URL，本地文件需转为 data URI
    """
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
    mime = mime_map.get(ext, "image/jpeg")

    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


async def run_syllabus_extract(image_path: str) -> Dict[str, Any]:
    """
    Step 1: 从 Syllabus 图片提取事件（不推送日历）
    返回提取结果供用户在前端确认
    """
    print(f"[SyllabusAgent] Extracting events from image: {image_path}")

    # 转换为 data URL
    image_url = await _upload_image_to_data_url(image_path)

    # WaveSpeed Vision API 解析
    events = await extract_syllabus_events(image_url)
    print(f"[SyllabusAgent] Extracted {len(events)} events via WaveSpeed Vision")

    # 存入数据库（未确认状态）
    saved_ids = []
    async with AsyncSessionLocal() as db:
        for ev in events:
            start = _parse_dt(ev.get("start_time"))
            end = _parse_dt(ev.get("end_time"))
            record = SyllabusEvent(
                event_name=ev.get("event_name", "Untitled Event"),
                start_time=start,
                end_time=end,
                description=ev.get("description", ""),
                event_type=ev.get("event_type", "other"),
                source_image=image_path,
                confirmed=False,
            )
            db.add(record)
            await db.flush()
            saved_ids.append(record.id)
        await db.commit()

    return {
        "status": "extracted",
        "event_count": len(events),
        "events": events,
        "db_ids": saved_ids,
        "image_path": image_path,
    }


async def run_syllabus_sync(
    event_ids: List[int],
    gcal_credentials: Dict,
) -> Dict[str, Any]:
    """
    Step 2: 用户确认后，将选定事件推送到 Google Calendar
    """
    print(f"[SyllabusAgent] Syncing {len(event_ids)} events to Google Calendar...")

    # 从数据库取出事件
    async with AsyncSessionLocal() as db:
        records = await db.scalars(
            select(SyllabusEvent).where(SyllabusEvent.id.in_(event_ids))
        )
        events = list(records.all())

    if not events:
        return {"status": "error", "message": "No events found for given IDs"}

    # 构建 Google Calendar service
    service = get_calendar_service(gcal_credentials)

    synced = 0
    errors = []
    async with AsyncSessionLocal() as db:
        for ev in events:
            # 构造与 gcal_pusher 兼容的 assignment dict
            assignment = {
                "id": ev.id,
                "name": ev.event_name,
                "course_name": _event_type_label(ev.event_type),
                "due_at": ev.start_time,
                "start_time": ev.start_time,
                "end_time": ev.end_time,
                "points_possible": 0,
                "html_url": "",
                "description": ev.description,
            }
            try:
                event_id = await _push_syllabus_event(service, assignment, ev)
                if event_id:
                    # 更新数据库
                    record = await db.scalar(select(SyllabusEvent).where(SyllabusEvent.id == ev.id))
                    if record:
                        record.gcal_event_id = event_id
                        record.confirmed = True
                    synced += 1
            except Exception as e:
                errors.append(f"{ev.event_name}: {str(e)}")

        await db.commit()

    print(f"[SyllabusAgent] Synced {synced} events to Google Calendar")
    return {
        "status": "success",
        "synced_count": synced,
        "errors": errors,
    }


async def _push_syllabus_event(service, assignment: dict, ev: SyllabusEvent) -> str | None:
    """推送单个 Syllabus 事件到 Google Calendar（复用 gcal_pusher 逻辑）"""
    from datetime import timedelta, timezone
    from googleapiclient.errors import HttpError

    start = ev.start_time
    end = ev.end_time

    if start is None:
        return None

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is None:
        end = start + timedelta(hours=1)
    elif end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    # 颜色按类型区分
    color_map = {"exam": "11", "deadline": "4", "quiz": "5", "project": "2", "other": "8"}
    color = color_map.get(ev.event_type, "8")

    event = {
        "summary": f"[{_event_type_label(ev.event_type)}] {ev.event_name}",
        "description": ev.description or f"Type: {ev.event_type}",
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Singapore"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Singapore"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ],
        },
        "colorId": color,
    }

    try:
        result = service.events().insert(calendarId="primary", body=event).execute()
        return result.get("id")
    except HttpError as e:
        print(f"[SyllabusAgent] Calendar error for {ev.event_name}: {e}")
        return None


def _parse_dt(dt_str: str | None) -> datetime | None:
    """解析 ISO 8601 时间字符串"""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


def _event_type_label(event_type: str) -> str:
    labels = {
        "exam": "Exam", "deadline": "Deadline",
        "quiz": "Quiz", "project": "Project", "other": "Event",
    }
    return labels.get(event_type, "Event")


async def get_syllabus_events(confirmed_only: bool = False) -> List[Dict]:
    """获取所有已提取的 Syllabus 事件"""
    async with AsyncSessionLocal() as db:
        query = select(SyllabusEvent).order_by(SyllabusEvent.start_time)
        if confirmed_only:
            query = query.where(SyllabusEvent.confirmed == True)
        records = await db.scalars(query)
        return [
            {
                "id": r.id,
                "event_name": r.event_name,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "description": r.description,
                "event_type": r.event_type,
                "gcal_synced": bool(r.gcal_event_id),
                "confirmed": r.confirmed,
            }
            for r in records.all()
        ]
