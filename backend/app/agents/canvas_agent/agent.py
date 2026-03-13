# -*- coding: utf-8 -*-
"""
Canvas Agent - OpenClaw 协作 Agent 之一
职责：Canvas 数据同步 → AI 摘要 → 推送日历
由 OpenClaw Orchestrator 调度
"""
import asyncio
from typing import Dict, Any
from app.agents.canvas_agent.tools.canvas_fetcher import fetch_all_data
from app.agents.canvas_agent.tools.gcal_pusher import push_all_assignments
from app.services.wavespeed_service import summarize_announcement
from app.database import AsyncSessionLocal
from app.models.canvas_sync import CanvasCourse, CanvasAssignment, CanvasAnnouncement
from sqlalchemy import select


async def run_canvas_sync(
    canvas_token: str,
    gcal_credentials: Dict | None = None,
    push_to_calendar: bool = True,
) -> Dict[str, Any]:
    """
    Canvas Agent 主入口
    1. 从 Canvas 拉取数据
    2. 用 WaveSpeed AI 总结公告
    3. 存入数据库
    4. 推送到 Google Calendar（如已授权）
    """
    print("[CanvasAgent] Starting Canvas sync...")

    # Step 1: 拉取 Canvas 数据
    data = await fetch_all_data(canvas_token)
    courses = data["courses"]
    assignments = data["assignments"]
    announcements = data["announcements"]

    print(f"[CanvasAgent] Fetched {len(courses)} courses, {len(assignments)} assignments, {len(announcements)} announcements")

    # Step 2: WaveSpeed AI 总结公告（并发处理）
    async def summarize(ann: dict) -> dict:
        if ann.get("message"):
            ann["summary"] = await summarize_announcement(ann["message"], ann.get("course_name", ""))
        else:
            ann["summary"] = ann.get("title", "")
        return ann

    if announcements:
        # BUG-04 fix: Semaphore 限制并发为 5，return_exceptions=True 隔离单条失败
        sem = asyncio.Semaphore(5)

        async def summarize_limited(ann: dict) -> dict:
            async with sem:
                return await summarize(ann)

        results = await asyncio.gather(
            *[summarize_limited(ann) for ann in announcements],
            return_exceptions=True,
        )
        announcements = [r for r in results if not isinstance(r, Exception)]
        print(f"[CanvasAgent] Summarized {len(announcements)} announcements via WaveSpeed AI")

    # Step 3: 存入数据库
    async with AsyncSessionLocal() as db:
        # 存课程
        for c in courses:
            existing = await db.scalar(select(CanvasCourse).where(CanvasCourse.canvas_id == c["id"]))
            if not existing:
                db.add(CanvasCourse(
                    canvas_id=c["id"],
                    name=c["name"],
                    course_code=c["course_code"],
                    semester=c["semester"],
                ))

        # 存作业
        for a in assignments:
            existing = await db.scalar(select(CanvasAssignment).where(CanvasAssignment.canvas_id == a["id"]))
            if not existing:
                db.add(CanvasAssignment(
                    canvas_id=a["id"],
                    course_id=a["course_id"],
                    course_name=a.get("course_name", ""),
                    name=a["name"],
                    due_at=a.get("due_at"),
                    points_possible=int(a.get("points_possible", 0)),
                    description=a.get("description", "")[:2000],
                ))

        # 存公告
        for ann in announcements:
            existing = await db.scalar(select(CanvasAnnouncement).where(CanvasAnnouncement.canvas_id == ann["id"]))
            if not existing:
                db.add(CanvasAnnouncement(
                    canvas_id=ann["id"],
                    course_id=ann["course_id"],
                    course_name=ann.get("course_name", ""),
                    title=ann["title"],
                    message=ann.get("message", "")[:5000],
                    summary=ann.get("summary", ""),
                    posted_at=ann.get("posted_at"),
                ))

        await db.commit()

    # Step 4: 推送到 Google Calendar
    gcal_results = {}
    if push_to_calendar and gcal_credentials:
        # BUG-10 fix: 只查询本批次涉及的 canvas_id，避免全表扫描
        current_ids = [a["id"] for a in assignments]
        async with AsyncSessionLocal() as db:
            existing = await db.scalars(
                select(CanvasAssignment).where(CanvasAssignment.canvas_id.in_(current_ids))
            )
            existing_event_ids = {a.canvas_id: a.gcal_event_id for a in existing.all()}

        gcal_results = await push_all_assignments(gcal_credentials, assignments, existing_event_ids)

        # 更新数据库中的 gcal_event_id
        async with AsyncSessionLocal() as db:
            for canvas_id, event_id in gcal_results.items():
                assignment = await db.scalar(
                    select(CanvasAssignment).where(CanvasAssignment.canvas_id == canvas_id)
                )
                if assignment:
                    assignment.gcal_event_id = event_id
            await db.commit()

        print(f"[CanvasAgent] Pushed {len(gcal_results)} events to Google Calendar")

    return {
        "status": "success",
        "courses_synced": len(courses),
        "assignments_synced": len(assignments),
        "announcements_synced": len(announcements),
        "calendar_events_created": len(gcal_results),
    }
