# -*- coding: utf-8 -*-
"""
Google Calendar 推送工具
将 Canvas 作业截止日期同步到 Google Calendar
"""
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from app.config import get_settings

settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_oauth_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [settings.google_redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=settings.google_redirect_uri)


def get_calendar_service(credentials_dict: dict):
    creds = Credentials(**credentials_dict)
    return build("calendar", "v3", credentials=creds)


async def push_assignment_to_calendar(
    service,
    assignment: Dict,
    calendar_id: str = "primary",
) -> Optional[str]:
    """将单个作业推送为 Google Calendar 事件，返回 event_id"""
    if not assignment.get("due_at"):
        return None

    due_at: datetime = assignment["due_at"]
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)

    event = {
        "summary": f"[{assignment.get('course_name', 'Canvas')}] {assignment['name']}",
        "description": (
            f"Points: {assignment.get('points_possible', 0)}\n"
            f"Course: {assignment.get('course_name', '')}\n"
            f"{assignment.get('html_url', '')}"
        ),
        "start": {"dateTime": due_at.isoformat(), "timeZone": "Asia/Singapore"},
        "end": {"dateTime": (due_at + timedelta(hours=1)).isoformat(), "timeZone": "Asia/Singapore"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ],
        },
        "colorId": "11",  # Red for deadlines
    }

    try:
        result = service.events().insert(calendarId=calendar_id, body=event).execute()
        return result.get("id")
    except HttpError as e:
        print(f"Calendar push error for {assignment['name']}: {e}")
        return None


async def push_all_assignments(
    credentials_dict: dict,
    assignments: List[Dict],
    existing_event_ids: Dict[int, str],  # assignment_id -> gcal_event_id
) -> Dict[int, str]:
    """批量推送作业到日历，跳过已存在的，返回 {assignment_id: gcal_event_id}"""
    service = get_calendar_service(credentials_dict)
    results = {}

    for assignment in assignments:
        aid = assignment["id"]
        if aid in existing_event_ids and existing_event_ids[aid]:
            # 已同步，跳过
            results[aid] = existing_event_ids[aid]
            continue
        event_id = await push_assignment_to_calendar(service, assignment)
        if event_id:
            results[aid] = event_id

    return results
