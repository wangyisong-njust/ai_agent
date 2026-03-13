# -*- coding: utf-8 -*-
"""
Canvas LMS 数据抓取工具
使用 canvasapi 库与 NUS Canvas 交互
"""
import asyncio
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from datetime import datetime, timezone
from typing import List, Dict, Any
from app.config import get_settings

settings = get_settings()


def get_canvas_client(token: str | None = None) -> Canvas:
    access_token = token or settings.canvas_access_token
    return Canvas(settings.canvas_base_url, access_token)


async def fetch_active_courses(token: str | None = None) -> List[Dict]:
    """获取当前学期所有活跃课程"""
    # BUG-01 fix: canvasapi 是同步库，用 asyncio.to_thread 避免阻塞事件循环
    def _sync_fetch():
        canvas = get_canvas_client(token)
        user = canvas.get_current_user()
        courses = []
        try:
            for course in user.get_courses(enrollment_state="active", include=["total_scores"]):
                courses.append({
                    "id": course.id,
                    "name": getattr(course, "name", "Unknown"),
                    "course_code": getattr(course, "course_code", ""),
                    "semester": getattr(course, "term", {}).get("name", "") if hasattr(course, "term") and isinstance(course.term, dict) else "",
                })
        except CanvasException as e:
            raise ValueError(f"Canvas API error: {e}")
        return courses

    return await asyncio.to_thread(_sync_fetch)


async def fetch_upcoming_assignments(course_id: int, token: str | None = None) -> List[Dict]:
    """获取某门课的即将到期作业"""
    # BUG-01 fix: 同步阻塞调用移入线程
    def _sync_fetch():
        canvas = get_canvas_client(token)
        course = canvas.get_course(course_id)
        assignments = []
        try:
            for a in course.get_assignments(bucket="upcoming", order_by="due_at"):
                due = None
                if hasattr(a, "due_at") and a.due_at:
                    try:
                        due = datetime.fromisoformat(a.due_at.replace("Z", "+00:00"))
                    except Exception:
                        pass
                assignments.append({
                    "id": a.id,
                    "course_id": course_id,
                    "name": getattr(a, "name", ""),
                    "due_at": due,
                    "points_possible": getattr(a, "points_possible", 0) or 0,
                    "description": getattr(a, "description", "") or "",
                    "html_url": getattr(a, "html_url", ""),
                })
        except CanvasException:
            pass
        return assignments

    return await asyncio.to_thread(_sync_fetch)


async def fetch_announcements(course_id: int, token: str | None = None) -> List[Dict]:
    """获取某门课的最新公告"""
    # BUG-01 fix: 同步阻塞调用移入线程
    def _sync_fetch():
        canvas = get_canvas_client(token)
        course = canvas.get_course(course_id)
        announcements = []
        try:
            for ann in course.get_discussion_topics(only_announcements=True, per_page=10):
                posted = None
                if hasattr(ann, "posted_at") and ann.posted_at:
                    try:
                        posted = datetime.fromisoformat(ann.posted_at.replace("Z", "+00:00"))
                    except Exception:
                        pass
                announcements.append({
                    "id": ann.id,
                    "course_id": course_id,
                    "title": getattr(ann, "title", ""),
                    "message": getattr(ann, "message", "") or "",
                    "posted_at": posted,
                })
        except CanvasException:
            pass
        return announcements

    return await asyncio.to_thread(_sync_fetch)


async def fetch_all_data(token: str | None = None) -> Dict[str, Any]:
    """全量同步：课程 + 作业 + 公告"""
    courses = await fetch_active_courses(token)
    all_assignments = []
    all_announcements = []

    for course in courses:
        cid = course["id"]
        assignments = await fetch_upcoming_assignments(cid, token)
        for a in assignments:
            a["course_name"] = course["name"]
        all_assignments.extend(assignments)

        announcements = await fetch_announcements(cid, token)
        for ann in announcements:
            ann["course_name"] = course["name"]
        all_announcements.extend(announcements)

    return {
        "courses": courses,
        "assignments": all_assignments,
        "announcements": all_announcements,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
